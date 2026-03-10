"""
AuditAI Suite v9 - Comprehensive Enterprise Walkthrough
=======================================================
A resilient, scenario-driven Playwright walkthrough that simulates a realistic
senior auditor workflow across the public AuditAI portal pages.

Pages in workflow order:
1) index.html      - Landing portal and enterprise intake
2) app.html        - Command Center full audit execution and review
3) vault.html      - Evidence Vault filtering and integrity review
4) governance.html - Governance operations (alerts/policies/framework/risk/rules)
5) uat.html        - UAT checks and readiness review
6) help.html       - Documentation validation and navigation

Key upgrades vs basic walk scripts:
- Scenario profiles for real audit use-cases
- Structured action telemetry with pass/fail per step
- Automatic retries and fallback selectors
- Evidence package output (screenshots, optional video, manifest JSON)
- Run summary with timing and failure analytics

Quick start:
    pip install playwright
    playwright install chromium
    python scripts/run_enterprise_v9_comprehensive.py --scenario sox_ap

Example advanced run:
    python scripts/run_enterprise_v9_comprehensive.py \
      --base-url https://djha786543-gif.github.io/Agentic-AI-Audit-Suite \
      --scenario privileged_access \
      --headless \
      --max-retries 3 \
      --continue-on-error \
      --video
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Awaitable, Callable, Dict, List, Optional

from playwright.async_api import Locator, Page, async_playwright

DEFAULT_BASE_URL = "https://djha786543-gif.github.io/Agentic-AI-Audit-Suite"


@dataclass
class ScenarioProfile:
    key: str
    name: str
    company: str
    contact_name: str
    contact_email: str
    role: str
    business_context: str
    selected_agent: str
    sample_data_preference: str
    policy_id: str
    framework_id: str
    risk_id: str
    rule_id: str


SCENARIOS: Dict[str, ScenarioProfile] = {
    "sox_ap": ScenarioProfile(
        key="sox_ap",
        name="SOX AP Segregation of Duties",
        company="Public Storage Corporation",
        contact_name="Debra Jha",
        contact_email="audit.manager@publicstorage.example",
        role="IT Audit Lead",
        business_context=(
            "SOX 404 ITGC continuous testing for AP process, segregation conflicts, "
            "and quarterly evidence packaging for external audit."
        ),
        selected_agent="SOD Auditor",
        sample_data_preference="Full Audit",
        policy_id="POL-ITGC-SOD-001",
        framework_id="FW-SOX-404-2026",
        risk_id="RISK-ITGC-AP-2026-001",
        rule_id="RULE-SOD-CRIT-001",
    ),
    "privileged_access": ScenarioProfile(
        key="privileged_access",
        name="Privileged Access Review",
        company="Contoso Manufacturing",
        contact_name="Aria Patel",
        contact_email="aria.patel@contoso.example",
        role="Security Auditor",
        business_context=(
            "Quarterly privileged access certification for domain admins and ERP super users, "
            "including orphaned account detection and emergency access review."
        ),
        selected_agent="Logical Access Auditor",
        sample_data_preference="User Access List",
        policy_id="POL-IAM-PAM-006",
        framework_id="FW-NIST-AC-2026",
        risk_id="RISK-IAM-PAM-2026-014",
        rule_id="RULE-IAM-PRIV-THRESHOLD",
    ),
    "itgc_change": ScenarioProfile(
        key="itgc_change",
        name="ITGC Change Management",
        company="Northwind Retail Group",
        contact_name="Liam Chen",
        contact_email="liam.chen@northwind.example",
        role="Internal Auditor",
        business_context=(
            "Change management governance for production ERP deployments, unauthorized release checks, "
            "and CAB evidence traceability."
        ),
        selected_agent="Financial Reporting Risk",
        sample_data_preference="Full Audit",
        policy_id="POL-CHG-CONTROL-012",
        framework_id="FW-COBIT-BAI-2026",
        risk_id="RISK-CHG-ERP-2026-022",
        rule_id="RULE-CHG-UNAPPROVED-001",
    ),
}


@dataclass
class WalkthroughConfig:
    base_url: str
    output_dir: Path
    headless: bool
    slow_mo: int
    timeout_ms: int
    max_retries: int
    continue_on_error: bool
    record_video: bool
    seed: int
    scenario: ScenarioProfile
    include_landing: bool


@dataclass
class ActionRecord:
    page: str
    action: str
    status: str
    details: str
    started_at: str
    duration_ms: int


@dataclass
class RunState:
    started_at: str
    run_id: str
    config: Dict[str, Any]
    actions: List[ActionRecord] = field(default_factory=list)
    page_status: Dict[str, str] = field(default_factory=dict)
    screenshots: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    video_file: Optional[str] = None
    ended_at: Optional[str] = None


class EvidenceStore:
    def __init__(self, out_dir: Path, run_id: str) -> None:
        self.run_dir = out_dir / f"walkthrough_{run_id}"
        self.shots_dir = self.run_dir / "screenshots"
        self.log_file = self.run_dir / "run.log"
        self.manifest_file = self.run_dir / "manifest.json"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.shots_dir.mkdir(parents=True, exist_ok=True)

    def log(self, line: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        record = f"[{timestamp}] {line}"
        print(record)
        with self.log_file.open("a", encoding="utf-8") as f:
            f.write(record + "\n")

    async def screenshot(self, page: Page, name: str, state: RunState) -> str:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")
        path = self.shots_dir / f"{safe}.png"
        await page.screenshot(path=str(path), full_page=True)
        rel = str(path.relative_to(self.run_dir))
        state.screenshots.append(rel)
        self.log(f"SCREENSHOT {rel}")
        return rel

    def write_manifest(self, state: RunState) -> None:
        payload = {
            "started_at": state.started_at,
            "ended_at": state.ended_at,
            "run_id": state.run_id,
            "config": state.config,
            "page_status": state.page_status,
            "screenshots": state.screenshots,
            "video_file": state.video_file,
            "errors": state.errors,
            "actions": [asdict(a) for a in state.actions],
            "metrics": {
                "total_actions": len(state.actions),
                "passed_actions": sum(1 for a in state.actions if a.status == "PASS"),
                "failed_actions": sum(1 for a in state.actions if a.status == "FAIL"),
                "pages_completed": sum(1 for s in state.page_status.values() if s == "PASS"),
                "pages_failed": sum(1 for s in state.page_status.values() if s == "FAIL"),
            },
        }
        with self.manifest_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def pause(min_s: float = 0.3, max_s: float = 0.9) -> None:
    await asyncio.sleep(random.uniform(min_s, max_s))


async def highlight(locator: Locator) -> None:
    try:
        await locator.evaluate(
            """el => {
                const prevOutline = el.style.outline;
                const prevShadow = el.style.boxShadow;
                el.style.outline = '3px solid #f4b400';
                el.style.boxShadow = '0 0 10px rgba(244,180,0,0.9)';
                setTimeout(() => {
                    el.style.outline = prevOutline;
                    el.style.boxShadow = prevShadow;
                }, 1000);
            }"""
        )
    except Exception:
        return


async def human_scroll(page: Page, total_px: int = 800, steps: int = 6) -> None:
    per_step = max(1, total_px // max(1, steps))
    for _ in range(steps):
        await page.mouse.wheel(0, per_step)
        await pause(0.08, 0.22)


async def first_visible(page: Page, selectors: List[str], timeout_ms: int = 1500) -> Optional[Locator]:
    for selector in selectors:
        loc = page.locator(selector).first
        try:
            if await loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


async def click_locator(locator: Locator, timeout_ms: int = 5000) -> None:
    await locator.wait_for(state="visible", timeout=timeout_ms)
    await locator.scroll_into_view_if_needed(timeout=timeout_ms)
    await highlight(locator)
    await pause(0.15, 0.35)
    await locator.click(force=True, timeout=timeout_ms)


async def fill_first(page: Page, selectors: List[str], value: str, timeout_ms: int = 1200) -> bool:
    loc = await first_visible(page, selectors, timeout_ms=timeout_ms)
    if not loc:
        return False
    await loc.scroll_into_view_if_needed()
    await highlight(loc)
    await loc.click()
    await loc.fill(value)
    await pause(0.1, 0.25)
    return True


async def select_first(page: Page, selectors: List[str], value: str, timeout_ms: int = 1200) -> bool:
    loc = await first_visible(page, selectors, timeout_ms=timeout_ms)
    if not loc:
        return False
    await highlight(loc)
    await loc.select_option(value=value)
    await pause(0.1, 0.25)
    return True


class Runner:
    def __init__(self, cfg: WalkthroughConfig, evidence: EvidenceStore, state: RunState) -> None:
        self.cfg = cfg
        self.evidence = evidence
        self.state = state

    async def do(
        self,
        page_name: str,
        action: str,
        fn: Callable[[], Awaitable[Any]],
        details: str = "",
        retries: Optional[int] = None,
    ) -> Any:
        max_retries = self.cfg.max_retries if retries is None else retries
        attempt = 0
        started = perf_counter()
        last_exc: Optional[Exception] = None

        while attempt <= max_retries:
            attempt += 1
            try:
                out = await fn()
                duration = int((perf_counter() - started) * 1000)
                self.state.actions.append(
                    ActionRecord(
                        page=page_name,
                        action=action,
                        status="PASS",
                        details=f"{details} | attempts={attempt}",
                        started_at=now_iso(),
                        duration_ms=duration,
                    )
                )
                self.evidence.log(f"PASS [{page_name}] {action} ({duration}ms, attempt {attempt})")
                return out
            except Exception as exc:
                last_exc = exc
                self.evidence.log(f"WARN [{page_name}] {action} attempt {attempt} failed: {exc}")
                await pause(0.2, 0.5)

        duration = int((perf_counter() - started) * 1000)
        msg = f"FAIL [{page_name}] {action} ({duration}ms): {last_exc}"
        self.state.actions.append(
            ActionRecord(
                page=page_name,
                action=action,
                status="FAIL",
                details=f"{details} | attempts={attempt}",
                started_at=now_iso(),
                duration_ms=duration,
            )
        )
        self.state.errors.append(msg)
        self.evidence.log(msg)
        raise RuntimeError(msg) from last_exc

    async def goto(self, page: Page, relative_path: str) -> None:
        url = f"{self.cfg.base_url.rstrip('/')}/{relative_path.lstrip('/')}"
        await page.goto(url, wait_until="networkidle", timeout=self.cfg.timeout_ms)
        await pause(0.4, 0.8)


async def page_landing(page: Page, runner: Runner) -> None:
    name = "index"
    s = runner.cfg.scenario

    await runner.do(name, "open_page", lambda: runner.goto(page, "index.html"), "Open landing")
    await runner.do(name, "hero_scroll", lambda: human_scroll(page, 400, 4), "Review hero value proposition")
    await runner.evidence.screenshot(page, "01_landing_hero", runner.state)

    async def nav_text(txt: str) -> None:
        target = page.get_by_text(txt, exact=False).first
        await click_locator(target)
        await pause(0.3, 0.7)

    for section in ["The Problem", "Breakthrough", "Industry Journey", "Security"]:
        await runner.do(name, f"navigate_{section.lower().replace(' ', '_')}", lambda s=section: nav_text(s))
        await runner.do(name, f"scroll_{section.lower().replace(' ', '_')}", lambda: human_scroll(page, 500, 5))
        await runner.evidence.screenshot(page, f"02_landing_{section.lower().replace(' ', '_')}", runner.state)

    await runner.do(name, "open_access_form", lambda: nav_text("Request Enterprise Access"))

    await runner.do(
        name,
        "fill_name",
        lambda: fill_first(
            page,
            ["input[placeholder*='Name']", "input[name*='name']", "input[id*='name']"],
            s.contact_name,
        ),
    )
    await runner.do(
        name,
        "fill_email",
        lambda: fill_first(page, ["input[type='email']", "input[placeholder*='Email']"], s.contact_email),
    )
    await runner.do(
        name,
        "fill_company",
        lambda: fill_first(
            page,
            ["input[placeholder*='Org']", "input[name*='org']", "input[id*='org']"],
            s.company,
        ),
    )
    await runner.do(
        name,
        "select_role",
        lambda: select_first(page, ["select"], s.role),
        "Some pages use role options by exact value",
    )
    await runner.do(
        name,
        "fill_use_case",
        lambda: fill_first(page, ["textarea"], s.business_context),
    )
    await runner.evidence.screenshot(page, "03_landing_form_completed", runner.state)


async def page_command_center(page: Page, runner: Runner) -> None:
    name = "app"
    s = runner.cfg.scenario

    await runner.do(name, "open_page", lambda: runner.goto(page, "app.html"), "Open command center")
    await runner.evidence.screenshot(page, "10_app_landing", runner.state)

    async def select_agent() -> None:
        # Defensive prep: close optional enterprise modal and force SOX 404 module context.
        try:
            close_candidates = [
                "button:has-text('Continue Exploring')",
                "#enterpriseModal .btn-enterprise",
                ".em-close",
                ".enterprise-close",
            ]
            for sel in close_candidates:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=700):
                    await click_locator(btn, timeout_ms=2500)
                    await pause(0.15, 0.35)
            await page.keyboard.press("Escape")
        except Exception:
            pass

        try:
            m1_tab = page.locator("#mnavM1").first
            if await m1_tab.is_visible(timeout=1500):
                await click_locator(m1_tab, timeout_ms=3000)
        except Exception:
            pass

        agent_map = {
            "SOD Auditor": "sod",
            "Logical Access Auditor": "access",
            "Financial Reporting Risk": "frr",
            "Change Mgmt Auditor": "change",
        }
        agent_key = agent_map.get(s.selected_agent, "")
        selectors = []
        if agent_key:
            selectors.append(f"div.agent-option[data-agent='{agent_key}']")
        selectors.extend(
            [
                f".agent-option:has(h4:has-text('{s.selected_agent}'))",
                f"h4:has-text('{s.selected_agent}')",
            ]
        )

        picked = await first_visible(page, selectors, timeout_ms=2500)
        if not picked:
            raise RuntimeError(f"Agent card not found for '{s.selected_agent}'")
        await click_locator(picked, timeout_ms=5000)

        # Ensure the page-level state is truly set (some custom cards don't always
        # trigger the onclick path through pure pointer simulation).
        if agent_key:
            await page.evaluate(
                """(ak) => {
                    const card = document.querySelector(`.agent-option[data-agent='${ak}']`);
                    if (card && typeof window.selectAgent === 'function') {
                        window.selectAgent(card);
                    }
                }""",
                agent_key,
            )

        continue_btn = await first_visible(
            page,
            [
                "#btnNext1",
                "button:has-text('Continue')",
            ],
            timeout_ms=2500,
        )
        if not continue_btn:
            raise RuntimeError("Continue button for Step 1 not found")

        # Prefer UI click, then force state transition via app function when needed.
        try:
            await click_locator(continue_btn, timeout_ms=3500)
        except Exception:
            pass

        is_v2_visible = await page.evaluate(
            """() => {
                const v2 = document.getElementById('v2');
                return !!(v2 && v2.classList.contains('active'));
            }"""
        )

        if not is_v2_visible:
            await page.evaluate(
                """() => {
                    if (typeof window.goStep === 'function') {
                        window.goStep(2);
                    }
                }"""
            )

        view2 = page.locator("#v2.active").first
        await view2.wait_for(state="visible", timeout=8000)

    await runner.do(name, "select_agent", select_agent, f"selected_agent={s.selected_agent}")
    await runner.evidence.screenshot(page, "11_app_agent_selected", runner.state)

    async def load_data() -> None:
        sample = page.get_by_text(s.sample_data_preference, exact=False).first
        await click_locator(sample)

        paste_tab = page.get_by_text("Paste Text", exact=False).first
        structured_tab = page.get_by_text("Structured Data", exact=False).first
        await click_locator(paste_tab)
        await pause(0.2, 0.5)
        await click_locator(structured_tab)

    await runner.do(name, "load_sample_data", load_data)

    async def run_audit() -> None:
        run_button = await first_visible(
            page,
            [
                "text=Run Audit Agent",
                "text=Run Batch Audit",
                "button:has-text('Run')",
            ],
            timeout_ms=2500,
        )
        if not run_button:
            raise RuntimeError("Run button not found")
        await click_locator(run_button)

        # Wait for any indicative results surface to appear.
        wait_candidates = [
            page.get_by_text("Findings", exact=False).first,
            page.locator("table tbody tr").first,
            page.get_by_text("CRITICAL", exact=False).first,
        ]
        for candidate in wait_candidates:
            try:
                await candidate.wait_for(timeout=12000)
                return
            except Exception:
                continue
        raise RuntimeError("Results were not detected after triggering run")

    await runner.do(name, "run_audit", run_audit, "Execute full audit")
    await runner.evidence.screenshot(page, "12_app_results_loaded", runner.state)

    async def review_filters() -> None:
        for label in ["CRITICAL", "HIGH", "MEDIUM", "ALL"]:
            tab = page.get_by_text(label, exact=True).first
            try:
                if await tab.is_visible(timeout=1500):
                    await click_locator(tab)
                    await pause(0.15, 0.4)
            except Exception:
                continue

    await runner.do(name, "review_severity_filters", review_filters)

    async def review_findings_table() -> None:
        rows = page.locator("table tbody tr")
        count = await rows.count()
        if count == 0:
            raise RuntimeError("No rows in findings table")
        for i in range(min(5, count)):
            row = rows.nth(i)
            await row.scroll_into_view_if_needed()
            await row.hover()
            await pause(0.08, 0.2)

    await runner.do(name, "review_findings_table", review_findings_table)

    async def review_heatmap() -> None:
        chart = await first_visible(page, ["canvas", "[class*='heatmap']", "[class*='chart']"], timeout_ms=2000)
        if not chart:
            raise RuntimeError("Heatmap/chart element not available")
        box = await chart.bounding_box()
        if not box:
            raise RuntimeError("Heatmap/chart has no measurable bounds")
        for pct in [0.25, 0.5, 0.75]:
            await page.mouse.move(box["x"] + box["width"] * pct, box["y"] + box["height"] * 0.5)
            await pause(0.1, 0.25)

    await runner.do(name, "review_heatmap", review_heatmap)

    async def export_actions() -> None:
        for label in ["Audit Report", "Export to Excel", "Dashboard PDF"]:
            btn = page.get_by_text(label, exact=False).first
            try:
                if await btn.is_visible(timeout=1200):
                    await click_locator(btn)
                    await pause(0.2, 0.5)
            except Exception:
                continue

    await runner.do(name, "trigger_exports", export_actions)
    await runner.evidence.screenshot(page, "13_app_exports", runner.state)


async def page_vault(page: Page, runner: Runner) -> None:
    name = "vault"
    await runner.do(name, "open_page", lambda: runner.goto(page, "vault.html"), "Open evidence vault")
    await runner.evidence.screenshot(page, "20_vault_landing", runner.state)

    async def apply_filters() -> None:
        for label in ["File System", "Windows Logs", "Azure AD", "Firewall", "All Origins"]:
            btn = page.get_by_text(label, exact=True).first
            try:
                if await btn.is_visible(timeout=1200):
                    await click_locator(btn)
                    await pause(0.15, 0.4)
            except Exception:
                continue

    await runner.do(name, "filter_evidence_origin", apply_filters)

    async def toggle_sort() -> None:
        oldest = page.get_by_text("Oldest First", exact=False).first
        newest = page.get_by_text("Newest First", exact=False).first
        await click_locator(oldest)
        await pause(0.1, 0.3)
        await click_locator(newest)

    await runner.do(name, "toggle_sort", toggle_sort)

    await runner.do(name, "scroll_ledger", lambda: human_scroll(page, 700, 6))
    await runner.evidence.screenshot(page, "21_vault_ledger", runner.state)


async def page_governance(page: Page, runner: Runner) -> None:
    name = "governance"
    s = runner.cfg.scenario
    await runner.do(name, "open_page", lambda: runner.goto(page, "governance.html"), "Open governance")
    await runner.evidence.screenshot(page, "30_governance_landing", runner.state)

    async def open_tab(label: str) -> None:
        tab = page.get_by_text(label, exact=False).first
        await click_locator(tab)

    async def submit_alert() -> None:
        await open_tab("Alerts")
        await fill_first(page, ["#alert-title", "input[placeholder*='Title']"], f"{s.name} exception escalation")
        await select_first(page, ["select"], "CRITICAL")
        await fill_first(
            page,
            ["textarea"],
            f"Automated escalation for scenario {s.key}. Immediate triage requested for control owner and GRC.",
        )
        btn = page.get_by_text("Raise Alert", exact=False).first
        await click_locator(btn)

    await runner.do(name, "raise_alert", submit_alert)

    async def create_policy() -> None:
        await open_tab("Policies")
        await fill_first(page, ["#policy-id", "input[placeholder*='Policy ID']"], s.policy_id)
        await fill_first(page, ["input[placeholder*='Version']"], "v3.0")
        await fill_first(page, ["input[placeholder*='Title']"], f"{s.name} Governance Policy")
        await fill_first(page, ["input[placeholder*='Owner']"], "IT Audit Manager")
        await select_first(page, ["select"], "Active")
        btn = page.get_by_text("Create Policy", exact=False).first
        await click_locator(btn)

    await runner.do(name, "create_policy", create_policy)

    async def register_framework() -> None:
        await open_tab("Frameworks")
        await fill_first(page, ["input[placeholder*='Framework ID']"], s.framework_id)
        await fill_first(page, ["input[placeholder*='Version']"], "2026.1")
        await fill_first(page, ["input[placeholder*='Name']"], f"{s.name} Framework")
        await fill_first(page, ["textarea", "input[placeholder*='Description']"], s.business_context)
        btn = page.get_by_text("Register", exact=False).first
        await click_locator(btn)

    await runner.do(name, "register_framework", register_framework)

    async def add_risk() -> None:
        await open_tab("Risk Register")
        await fill_first(page, ["input[placeholder*='Risk ID']"], s.risk_id)
        await select_first(page, ["select[name*='category']", "select"], "Compliance")
        await fill_first(page, ["input[placeholder*='Title']"], f"{s.name} high residual risk")
        await fill_first(page, ["input[placeholder*='Owner']"], "VP Internal Audit")
        btn = page.get_by_text("Add to Register", exact=False).first
        await click_locator(btn)

    await runner.do(name, "add_risk_register_entry", add_risk)

    async def create_alert_rule() -> None:
        await open_tab("Alert Rules")
        await fill_first(page, ["input[placeholder*='Rule ID']"], s.rule_id)
        await select_first(page, ["select[name*='severity']", "select"], "CRITICAL")
        await fill_first(page, ["input[placeholder*='Name']"], f"{s.name} threshold rule")
        await fill_first(page, ["input[placeholder*='Threshold']"], "1")
        btn = page.get_by_text("Create Rule", exact=False).first
        await click_locator(btn)

    await runner.do(name, "create_alert_rule", create_alert_rule)
    await runner.evidence.screenshot(page, "31_governance_completed", runner.state)


async def page_uat(page: Page, runner: Runner) -> None:
    name = "uat"
    await runner.do(name, "open_page", lambda: runner.goto(page, "uat.html"), "Open UAT page")
    await runner.evidence.screenshot(page, "40_uat_landing", runner.state)

    await runner.do(name, "scroll_checklist", lambda: human_scroll(page, 500, 5))

    async def set_scale() -> None:
        ok = await select_first(page, ["select"], "small")
        if not ok:
            raise RuntimeError("Unable to set UAT scale")

    await runner.do(name, "set_scale_small", set_scale)

    async def click_actions() -> None:
        for label in ["Refresh Reports", "Compare Latest 2 Runs", "Phase 2 Plan"]:
            btn = page.get_by_text(label, exact=False).first
            try:
                if await btn.is_visible(timeout=1200):
                    await click_locator(btn)
                    await pause(0.2, 0.5)
            except Exception:
                continue

    await runner.do(name, "run_uat_actions", click_actions)
    await runner.evidence.screenshot(page, "41_uat_actions", runner.state)


async def page_help(page: Page, runner: Runner) -> None:
    name = "help"
    await runner.do(name, "open_page", lambda: runner.goto(page, "help.html"), "Open help")
    await runner.do(name, "scroll_docs", lambda: human_scroll(page, 900, 8))

    async def open_sections() -> None:
        for section in ["Suite Overview", "4-Phase Architecture", "Data Security", "AI Agents", "FAQ"]:
            target = page.get_by_text(section, exact=False).first
            try:
                if await target.is_visible(timeout=1200):
                    await click_locator(target)
                    await pause(0.1, 0.3)
            except Exception:
                continue

    await runner.do(name, "open_help_sections", open_sections)
    await runner.evidence.screenshot(page, "50_help_sections", runner.state)


async def run_page(
    page_label: str,
    fn: Callable[[Page, Runner], Awaitable[None]],
    page: Page,
    runner: Runner,
    state: RunState,
) -> None:
    runner.evidence.log(f"PAGE START {page_label}")
    try:
        await fn(page, runner)
        state.page_status[page_label] = "PASS"
        runner.evidence.log(f"PAGE PASS {page_label}")
    except Exception as exc:
        state.page_status[page_label] = "FAIL"
        err = f"Page {page_label} failed: {exc}"
        state.errors.append(err)
        runner.evidence.log(err)
        runner.evidence.log(traceback.format_exc())
        await runner.evidence.screenshot(page, f"error_{page_label}", state)
        if not runner.cfg.continue_on_error:
            raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Comprehensive enterprise UI walkthrough for AuditAI Suite")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Base URL for hosted portal")
    parser.add_argument(
        "--out-dir",
        default=str(Path.home() / "Documents" / "AuditAI_Enterprise_Walkthrough"),
        help="Output root directory for evidence artifacts",
    )
    parser.add_argument("--scenario", default="sox_ap", choices=sorted(SCENARIOS.keys()), help="Business scenario profile")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--slow-mo", type=int, default=450, help="Playwright slow motion in milliseconds")
    parser.add_argument("--timeout-ms", type=int, default=25000, help="Navigation/action timeout")
    parser.add_argument("--max-retries", type=int, default=2, help="Retries per action")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue to next page after page failure")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic wait jitter")
    parser.add_argument("--video", action="store_true", help="Record browser video")
    parser.add_argument(
        "--include-landing",
        action="store_true",
        help="Include index.html walkthrough; default run focuses on operational pages",
    )
    return parser.parse_args()


def build_run_state(cfg: WalkthroughConfig, run_id: str) -> RunState:
    safe_cfg = {
        "base_url": cfg.base_url,
        "output_dir": str(cfg.output_dir),
        "headless": cfg.headless,
        "slow_mo": cfg.slow_mo,
        "timeout_ms": cfg.timeout_ms,
        "max_retries": cfg.max_retries,
        "continue_on_error": cfg.continue_on_error,
        "record_video": cfg.record_video,
        "seed": cfg.seed,
        "include_landing": cfg.include_landing,
        "scenario": asdict(cfg.scenario),
    }
    return RunState(started_at=now_iso(), run_id=run_id, config=safe_cfg)


async def orchestrate(cfg: WalkthroughConfig) -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    evidence = EvidenceStore(cfg.output_dir, run_id)
    state = build_run_state(cfg, run_id)

    random.seed(cfg.seed)
    evidence.log(f"RUN START id={run_id} scenario={cfg.scenario.key}")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=cfg.headless,
            slow_mo=cfg.slow_mo,
            args=["--start-maximized"],
        )

        context_kwargs: Dict[str, Any] = {"viewport": {"width": 1600, "height": 900}}
        if cfg.record_video:
            video_dir = str((evidence.run_dir / "video").resolve())
            os.makedirs(video_dir, exist_ok=True)
            context_kwargs["record_video_dir"] = video_dir
            context_kwargs["record_video_size"] = {"width": 1600, "height": 900}

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        runner = Runner(cfg=cfg, evidence=evidence, state=state)

        page_flow = [
            ("app", page_command_center),
            ("vault", page_vault),
            ("governance", page_governance),
            ("uat", page_uat),
            ("help", page_help),
        ]
        if cfg.include_landing:
            page_flow.insert(0, ("index", page_landing))

        overall_error = False
        try:
            for page_label, fn in page_flow:
                await run_page(page_label, fn, page, runner, state)

            await runner.do("final", "return_to_command_center", lambda: runner.goto(page, "app.html"))
            await runner.do("final", "executive_scroll", lambda: human_scroll(page, 350, 4))
            await evidence.screenshot(page, "99_final_executive_closeout", state)
        except Exception:
            overall_error = True
        finally:
            video_obj = page.video
            await context.close()
            if cfg.record_video and video_obj:
                try:
                    raw_path = await video_obj.path()
                    final_path = evidence.run_dir / "video" / f"enterprise_walkthrough_{run_id}.webm"
                    os.replace(raw_path, final_path)
                    state.video_file = str(final_path.relative_to(evidence.run_dir))
                    evidence.log(f"VIDEO {state.video_file}")
                except Exception as exc:
                    evidence.log(f"WARN video finalize failed: {exc}")
            await browser.close()

    state.ended_at = now_iso()
    evidence.write_manifest(state)

    pass_pages = sum(1 for p in state.page_status.values() if p == "PASS")
    fail_pages = sum(1 for p in state.page_status.values() if p == "FAIL")
    evidence.log(f"RUN SUMMARY pass_pages={pass_pages} fail_pages={fail_pages} errors={len(state.errors)}")
    evidence.log(f"ARTIFACTS {evidence.run_dir}")

    if overall_error and not cfg.continue_on_error:
        return 2
    if fail_pages > 0:
        return 1
    return 0


def main() -> None:
    args = parse_args()
    scenario = SCENARIOS[args.scenario]

    cfg = WalkthroughConfig(
        base_url=args.base_url,
        output_dir=Path(args.out_dir),
        headless=args.headless,
        slow_mo=args.slow_mo,
        timeout_ms=args.timeout_ms,
        max_retries=max(0, args.max_retries),
        continue_on_error=args.continue_on_error,
        record_video=args.video,
        seed=args.seed,
        scenario=scenario,
        include_landing=args.include_landing,
    )

    exit_code = asyncio.run(orchestrate(cfg))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
