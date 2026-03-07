"""enterprise hardening tables

Revision ID: 20260307_enterprise_hardening
Revises:
Create Date: 2026-03-07
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260307_enterprise_hardening"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(length=50), nullable=False),
        sa.Column("decision_type", sa.String(length=80), nullable=False),
        sa.Column("resource", sa.String(length=255), nullable=True),
        sa.Column("decision_summary", sa.Text(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("source_data_reference", sa.JSON(), nullable=True),
        sa.Column("reasoning_trace", sa.Text(), nullable=True),
        sa.Column("model_used", sa.String(length=120), nullable=True),
        sa.Column("generated_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_decisions_org_id", "ai_decisions", ["org_id"])
    op.create_index("ix_ai_decisions_decision_type", "ai_decisions", ["decision_type"])
    op.create_index("ix_ai_decisions_resource", "ai_decisions", ["resource"])
    op.create_index("ix_ai_decisions_created_at", "ai_decisions", ["created_at"])

    op.create_table(
        "roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(length=50), nullable=False),
        sa.Column("role_key", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "role_key", name="uq_roles_org_role_key"),
    )
    op.create_index("ix_roles_org_id", "roles", ["org_id"])
    op.create_index("ix_roles_role_key", "roles", ["role_key"])

    op.create_table(
        "permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(length=50), nullable=False),
        sa.Column("permission_key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "permission_key", name="uq_permissions_org_permission_key"),
    )
    op.create_index("ix_permissions_org_id", "permissions", ["org_id"])
    op.create_index("ix_permissions_permission_key", "permissions", ["permission_key"])

    op.create_table(
        "role_permissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(length=50), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("permission_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "role_id", "permission_id", name="uq_role_permissions"),
    )
    op.create_index("ix_role_permissions_org_id", "role_permissions", ["org_id"])

    op.create_table(
        "user_role_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(length=100), nullable=False),
        sa.Column("role_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "user_id", "role_id", name="uq_user_role_assignments"),
    )
    op.create_index("ix_user_role_assignments_org_id", "user_role_assignments", ["org_id"])
    op.create_index("ix_user_role_assignments_user_id", "user_role_assignments", ["user_id"])

    op.create_table(
        "system_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(length=50), nullable=False),
        sa.Column("user", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=80), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("immutable", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_logs_org_id", "system_logs", ["org_id"])
    op.create_index("ix_system_logs_user", "system_logs", ["user"])
    op.create_index("ix_system_logs_role", "system_logs", ["role"])
    op.create_index("ix_system_logs_action", "system_logs", ["action"])
    op.create_index("ix_system_logs_resource", "system_logs", ["resource"])
    op.create_index("ix_system_logs_created_at", "system_logs", ["created_at"])

    op.create_table(
        "workflow_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("org_id", sa.String(length=50), nullable=False),
        sa.Column("user", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("workflow_name", sa.String(length=120), nullable=False),
        sa.Column("resource", sa.String(length=255), nullable=True),
        sa.Column("stage_from", sa.String(length=80), nullable=True),
        sa.Column("stage_to", sa.String(length=80), nullable=True),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_logs_org_id", "workflow_logs", ["org_id"])
    op.create_index("ix_workflow_logs_user", "workflow_logs", ["user"])
    op.create_index("ix_workflow_logs_action", "workflow_logs", ["action"])
    op.create_index("ix_workflow_logs_workflow_name", "workflow_logs", ["workflow_name"])
    op.create_index("ix_workflow_logs_created_at", "workflow_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_workflow_logs_created_at", table_name="workflow_logs")
    op.drop_index("ix_workflow_logs_workflow_name", table_name="workflow_logs")
    op.drop_index("ix_workflow_logs_action", table_name="workflow_logs")
    op.drop_index("ix_workflow_logs_user", table_name="workflow_logs")
    op.drop_index("ix_workflow_logs_org_id", table_name="workflow_logs")
    op.drop_table("workflow_logs")

    op.drop_index("ix_system_logs_created_at", table_name="system_logs")
    op.drop_index("ix_system_logs_resource", table_name="system_logs")
    op.drop_index("ix_system_logs_action", table_name="system_logs")
    op.drop_index("ix_system_logs_role", table_name="system_logs")
    op.drop_index("ix_system_logs_user", table_name="system_logs")
    op.drop_index("ix_system_logs_org_id", table_name="system_logs")
    op.drop_table("system_logs")

    op.drop_index("ix_user_role_assignments_user_id", table_name="user_role_assignments")
    op.drop_index("ix_user_role_assignments_org_id", table_name="user_role_assignments")
    op.drop_table("user_role_assignments")

    op.drop_index("ix_role_permissions_org_id", table_name="role_permissions")
    op.drop_table("role_permissions")

    op.drop_index("ix_permissions_permission_key", table_name="permissions")
    op.drop_index("ix_permissions_org_id", table_name="permissions")
    op.drop_table("permissions")

    op.drop_index("ix_roles_role_key", table_name="roles")
    op.drop_index("ix_roles_org_id", table_name="roles")
    op.drop_table("roles")

    op.drop_index("ix_ai_decisions_created_at", table_name="ai_decisions")
    op.drop_index("ix_ai_decisions_resource", table_name="ai_decisions")
    op.drop_index("ix_ai_decisions_decision_type", table_name="ai_decisions")
    op.drop_index("ix_ai_decisions_org_id", table_name="ai_decisions")
    op.drop_table("ai_decisions")
