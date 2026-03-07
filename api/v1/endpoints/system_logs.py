"""
api/v1/endpoints/system_logs.py
System and workflow log access endpoints for enterprise governance.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.context import AuthContext
from auth.rbac import Permission, require_permission
from db.async_session import get_async_db
from models.system_logs import SystemLog, WorkflowLog

router = APIRouter()

_TRACE_GROUP_EVENT_ALLOWED_FIELDS = {
    "id",
    "org_id",
    "user",
    "role",
    "resource",
    "method",
    "status_code",
    "request_id",
    "span_id",
    "created_at",
}

_TRACE_GROUP_VIEW_PRESETS: Dict[str, List[str]] = {
    "compact": ["status_code", "resource", "request_id", "created_at"],
    "ids": ["request_id", "span_id", "created_at"],
    "full": [
        "id",
        "org_id",
        "user",
        "role",
        "resource",
        "method",
        "status_code",
        "request_id",
        "span_id",
        "created_at",
    ],
}


def _group_error_logs_by_trace(records: List[SystemLog]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for record in records:
        metadata = record.metadata_json or {}
        trace_id = metadata.get("trace_id") or "untraced"
        request_id = metadata.get("request_id")

        entry = grouped.setdefault(
            str(trace_id),
            {
                "trace_id": trace_id,
                "request_ids": set(),
                "error_count": 0,
                "last_seen_at": None,
                "events": [],
            },
        )

        if request_id:
            entry["request_ids"].add(str(request_id))
        entry["error_count"] += 1

        created_at_iso = record.created_at.isoformat() if record.created_at else None
        if created_at_iso and (entry["last_seen_at"] is None or created_at_iso > entry["last_seen_at"]):
            entry["last_seen_at"] = created_at_iso

        entry["events"].append(
            {
                "id": str(record.id),
                "org_id": record.org_id,
                "user": record.user,
                "role": record.role,
                "resource": record.resource,
                "method": record.method,
                "status_code": record.status_code,
                "request_id": request_id,
                "span_id": metadata.get("span_id"),
                "created_at": created_at_iso,
            }
        )

    groups = []
    for group in grouped.values():
        group["request_ids"] = sorted(group["request_ids"])
        group["span_ids"] = sorted(
            {
                str(event.get("span_id"))
                for event in group["events"]
                if event.get("span_id")
            }
        )
        group["events"].sort(
            key=lambda event: (
                event.get("created_at") is None,
                event.get("created_at") or "",
            ),
            reverse=True,
        )
        groups.append(group)

    return groups


def _sort_and_paginate_groups(
    groups: List[Dict[str, Any]],
    *,
    sort_by: str,
    sort_order: str,
    offset: int,
    group_limit: int,
    relevance_scores: Dict[str, int] | None = None,
) -> List[Dict[str, Any]]:
    descending = sort_order.lower() != "asc"

    if relevance_scores:
        # Keep existing sort semantics as a stable fallback when scores are equal.
        if sort_by == "error_count":
            fallback_key = lambda item: int(item.get("error_count") or 0)
        else:
            fallback_key = lambda item: (
                item.get("last_seen_at") is None,
                item.get("last_seen_at") or "",
            )

        groups.sort(
            key=lambda item: (
                int(relevance_scores.get(str(item.get("trace_id") or ""), 0)),
                fallback_key(item),
            ),
            reverse=True,
        )

        start = max(offset, 0)
        end = start + max(group_limit, 1)
        return groups[start:end]

    if sort_by == "error_count":
        groups.sort(
            key=lambda item: int(item.get("error_count") or 0),
            reverse=descending,
        )
    else:
        groups.sort(
            key=lambda item: (
                item.get("last_seen_at") is None,
                item.get("last_seen_at") or "",
            ),
            reverse=descending,
        )

    start = max(offset, 0)
    end = start + max(group_limit, 1)
    return groups[start:end]


def _parse_include_event_fields(raw: str | None) -> List[str] | None:
    if raw is None:
        return None
    tokens = [item.strip() for item in raw.split(",") if item.strip()]
    if not tokens:
        return None

    projected: List[str] = []
    seen = set()
    for token in tokens:
        if token in _TRACE_GROUP_EVENT_ALLOWED_FIELDS and token not in seen:
            projected.append(token)
            seen.add(token)
    return projected or None


def _project_group_events(groups: List[Dict[str, Any]], include_fields: List[str] | None) -> None:
    if not include_fields:
        return

    for group in groups:
        projected_events = []
        for event in group.get("events", []):
            projected_events.append({field: event.get(field) for field in include_fields})
        group["events"] = projected_events


def _text_match_score(value: str | None, query: str) -> int:
    text = str(value or "").strip().lower()
    if not text or not query:
        return 0
    if text == query:
        return 100
    if text.startswith(query):
        return 70
    if query in text:
        return 40
    return 0


def _event_relevance_score(event: Dict[str, Any], query: str) -> int:
    # Weighted toward precise technical IDs for incident triage.
    trace_or_request_exactness = max(
        _text_match_score(event.get("request_id"), query),
        _text_match_score(event.get("span_id"), query),
    )
    resource_match = _text_match_score(event.get("resource"), query)
    user_match = _text_match_score(event.get("user"), query)
    status_weight = 10 if int(event.get("status_code") or 0) >= 500 else 0
    return (trace_or_request_exactness * 4) + (resource_match * 2) + user_match + status_weight


def _build_group_relevance_scores(groups: List[Dict[str, Any]], query: str) -> Dict[str, int]:
    scores: Dict[str, int] = {}
    normalized_query = query.strip().lower()
    if not normalized_query:
        return scores

    for group in groups:
        trace_id = str(group.get("trace_id") or "")
        base = _text_match_score(trace_id, normalized_query) * 5
        event_scores = [
            _event_relevance_score(event, normalized_query)
            for event in group.get("events", [])
        ]
        total = base + (max(event_scores) if event_scores else 0)
        scores[trace_id] = total

    return scores


def _resolve_projection_fields(view: str | None, include_event_fields: str | None) -> tuple[str | None, List[str] | None]:
    normalized_view = (view or "").strip().lower() or None
    if normalized_view and normalized_view not in _TRACE_GROUP_VIEW_PRESETS:
        normalized_view = None

    explicit_fields = _parse_include_event_fields(include_event_fields)
    if explicit_fields is not None:
        return normalized_view, explicit_fields

    if normalized_view:
        return normalized_view, list(_TRACE_GROUP_VIEW_PRESETS[normalized_view])

    return normalized_view, None


@router.get("/system", summary="List system audit logs")
async def list_system_logs(
    limit: int = 200,
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(SystemLog).order_by(desc(SystemLog.created_at)).limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "org_id": r.org_id,
            "user": r.user,
            "role": r.role,
            "action": r.action,
            "resource": r.resource,
            "method": r.method,
            "status_code": r.status_code,
            "ip_address": r.ip_address,
            "session_id": r.session_id,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "trace_id": (r.metadata_json or {}).get("trace_id"),
            "span_id": (r.metadata_json or {}).get("span_id"),
            "metadata": r.metadata_json,
        }
        for r in records
    ]


@router.get("/workflow", summary="List workflow approval logs")
async def list_workflow_logs(
    limit: int = 200,
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(WorkflowLog).order_by(desc(WorkflowLog.created_at)).limit(limit)
    )
    records = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "org_id": r.org_id,
            "user": r.user,
            "action": r.action,
            "workflow_name": r.workflow_name,
            "resource": r.resource,
            "stage_from": r.stage_from,
            "stage_to": r.stage_to,
            "approval_required": r.approval_required,
            "approved": r.approved,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "metadata": r.metadata_json,
        }
        for r in records
    ]


@router.get("/system/errors/trace-groups", summary="Group recent error logs by trace for triage")
async def system_error_trace_groups(
    limit: int = 500,
    group_limit: int = 100,
    offset: int = 0,
    sort_by: str = "last_seen_at",
    sort_order: str = "desc",
    event_limit_per_group: int = 25,
    view: str | None = None,
    include_event_fields: str | None = None,
    q: str | None = None,
    q_ranked: bool = False,
    trace_id_prefix: str | None = None,
    request_id_prefix: str | None = None,
    min_status: int = 400,
    since_minutes: int | None = None,
    resource_prefix: str | None = None,
    db: AsyncSession = Depends(get_async_db),
    _: AuthContext = Depends(require_permission(Permission.VIEW_AUDIT_LOGS)),
) -> Dict[str, Any]:
    """
    Return recent system log errors grouped by trace_id for incident triage.
    """
    result = await db.execute(
        select(SystemLog)
        .filter(SystemLog.status_code >= 400)
        .order_by(desc(SystemLog.created_at))
        .limit(limit)
    )
    records = result.scalars().all()

    if since_minutes is not None and since_minutes >= 0:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=since_minutes)
        records = [
            r for r in records
            if r.created_at is not None and r.created_at >= cutoff
        ]

    if min_status > 0:
        records = [r for r in records if int(r.status_code or 0) >= min_status]

    if resource_prefix:
        normalized_prefix = resource_prefix.strip().lower()
        if normalized_prefix:
            records = [
                r for r in records
                if str(r.resource or "").lower().startswith(normalized_prefix)
            ]

    if trace_id_prefix:
        normalized_trace_prefix = trace_id_prefix.strip().lower()
        if normalized_trace_prefix:
            records = [
                r for r in records
                if str((r.metadata_json or {}).get("trace_id") or "").lower().startswith(normalized_trace_prefix)
            ]

    if request_id_prefix:
        normalized_request_prefix = request_id_prefix.strip().lower()
        if normalized_request_prefix:
            records = [
                r for r in records
                if str((r.metadata_json or {}).get("request_id") or "").lower().startswith(normalized_request_prefix)
            ]

    if q:
        query = q.strip().lower()
        if query:
            records = [
                r for r in records
                if (
                    query in str((r.metadata_json or {}).get("trace_id") or "").lower()
                    or query in str((r.metadata_json or {}).get("request_id") or "").lower()
                    or query in str(r.resource or "").lower()
                    or query in str(r.user or "").lower()
                )
            ]

    groups = _group_error_logs_by_trace(records)

    query_text = (q or "").strip().lower()
    relevance_scores = _build_group_relevance_scores(groups, query_text) if q_ranked and query_text else None

    for group in groups:
        total_events = len(group["events"])
        group["total_events"] = total_events
        if event_limit_per_group > 0:
            group["events"] = group["events"][:event_limit_per_group]
        group["returned_events"] = len(group["events"])

    total_groups = len(groups)
    groups = _sort_and_paginate_groups(
        groups,
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        group_limit=group_limit,
        relevance_scores=relevance_scores,
    )
    normalized_view, parsed_include_fields = _resolve_projection_fields(view, include_event_fields)
    _project_group_events(groups, parsed_include_fields)

    return {
        "total_error_events": len(records),
        "total_trace_groups": total_groups,
        "returned_groups": len(groups),
        "filters": {
            "min_status": min_status,
            "since_minutes": since_minutes,
            "resource_prefix": resource_prefix,
            "q": q,
            "q_ranked": q_ranked,
            "trace_id_prefix": trace_id_prefix,
            "request_id_prefix": request_id_prefix,
        },
        "paging": {
            "offset": offset,
            "group_limit": group_limit,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "event_limit_per_group": event_limit_per_group,
            "view": normalized_view,
            "include_event_fields": parsed_include_fields,
            "q_ranked": q_ranked,
        },
        "groups": groups,
    }
