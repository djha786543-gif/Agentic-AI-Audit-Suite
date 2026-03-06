#!/usr/bin/env python3
"""
Compare two UAT report JSON files and print improvements/regressions.

Usage:
  python agents/compare_uat_reports.py
  python agents/compare_uat_reports.py --old uat_reports/old.json --new uat_reports/new.json
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_report(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_latest_two_reports(report_glob: str) -> Tuple[Path, Path]:
    paths = sorted(Path(p) for p in glob.glob(report_glob))
    if len(paths) < 2:
        raise SystemExit("Need at least 2 UAT reports to compare.")
    return paths[-2], paths[-1]


def endpoint_failures(report: Dict[str, Any]) -> Dict[str, int]:
    failures: Dict[str, int] = {}
    for step in report.get("steps", []):
        if not step.get("success"):
            key = f"{step.get('method', 'UNK')} {step.get('path', 'UNKNOWN')}"
            failures[key] = failures.get(key, 0) + 1
    return failures


def top_items(delta_map: Dict[str, int], top_n: int = 10) -> List[Tuple[str, int]]:
    return sorted(delta_map.items(), key=lambda x: abs(x[1]), reverse=True)[:top_n]


def pct(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare two ACAP UAT run reports")
    parser.add_argument("--old", help="Path to older report JSON")
    parser.add_argument("--new", help="Path to newer report JSON")
    parser.add_argument("--glob", default="uat_reports/uat_enterprise_report_*.json", help="Glob used when --old/--new are omitted")
    args = parser.parse_args()

    if args.old and args.new:
        old_path = Path(args.old)
        new_path = Path(args.new)
    else:
        old_path, new_path = get_latest_two_reports(args.glob)

    old = load_report(old_path)
    new = load_report(new_path)

    old_summary = old.get("summary", {})
    new_summary = new.get("summary", {})

    old_total = int(old_summary.get("total_steps", 0))
    new_total = int(new_summary.get("total_steps", 0))
    old_failed = int(old_summary.get("failed_steps", 0))
    new_failed = int(new_summary.get("failed_steps", 0))
    old_success = pct(old_summary.get("success_rate_pct", 0))
    new_success = pct(new_summary.get("success_rate_pct", 0))
    old_p95 = old_summary.get("p95_latency_ms")
    new_p95 = new_summary.get("p95_latency_ms")

    print("UAT Report Comparison")
    print(f"Old: {old_path}")
    print(f"New: {new_path}")
    print("")
    print("Summary")
    print(f"- Total steps: {old_total} -> {new_total} (delta {new_total - old_total:+d})")
    print(f"- Failed steps: {old_failed} -> {new_failed} (delta {new_failed - old_failed:+d})")
    print(f"- Success rate: {old_success:.2f}% -> {new_success:.2f}% (delta {new_success - old_success:+.2f}%)")
    print(f"- P95 latency: {old_p95} ms -> {new_p95} ms")

    old_failures = endpoint_failures(old)
    new_failures = endpoint_failures(new)
    all_keys = set(old_failures) | set(new_failures)
    deltas: Dict[str, int] = {}
    for key in all_keys:
        deltas[key] = new_failures.get(key, 0) - old_failures.get(key, 0)

    regressions = {k: v for k, v in deltas.items() if v > 0}
    improvements = {k: v for k, v in deltas.items() if v < 0}

    print("")
    print("Endpoint failure deltas")
    if not deltas:
        print("- No endpoint failures in either run.")
    else:
        if improvements:
            print("- Improvements (fewer failures):")
            for k, v in top_items(improvements):
                print(f"  {k}: {v}")
        else:
            print("- Improvements: none")

        if regressions:
            print("- Regressions (more failures):")
            for k, v in top_items(regressions):
                print(f"  {k}: +{v}")
        else:
            print("- Regressions: none")

    old_candidates = len(old.get("improvement_candidates", []))
    new_candidates = len(new.get("improvement_candidates", []))
    print("")
    print("Improvement candidates")
    print(f"- Count: {old_candidates} -> {new_candidates} (delta {new_candidates - old_candidates:+d})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
