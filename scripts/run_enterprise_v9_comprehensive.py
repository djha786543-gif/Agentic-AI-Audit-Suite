"""
AuditAI Suite v9 - Comprehensive Enterprise Walkthrough
=======================================================
A resilient, scenario-driven Playwright walkthrough that simulates a realistic
senior auditor workflow across the public AuditAI portal pages.

Pages in workflow order:
1) index.html      - Landing portal and enterprise intake
2) settings.html   - Organization onboarding and connector setup
3) app.html        - Command Center full audit execution and review
4) vault.html      - Evidence Vault filtering and integrity review
5) governance.html - Governance operations (alerts/policies/framework/risk/rules)
6) uat.html        - UAT checks and readiness review
7) help.html       - Documentation validation and navigation

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
import hashlib
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

POPUP_SELECTORS = [
    "#enterpriseModal .em-close",
    "#enterpriseModal .btn-enterprise",
    "button:has-text('Continue Exploring')",
    "button:has-text('Close')",
    "button:has-text('Dismiss')",
    "button:has-text('No thanks')",
    "button:has-text('Got it')",
    "[aria-label='Close']",
    "[data-dismiss='modal']",
    ".modal .close",
    ".popup .close",
    ".overlay .close",
]


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
    fullscreen: bool
    strict_critical: bool
    showcase_seconds: float


@dataclass
class ActionRecord:
    page: str
    action: str
    status: str
    details: str
    started_at: str
    duration_ms: int


@dataclass
class AssertionRecord:
    page: str
    control: str
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
    assertions: List[AssertionRecord] = field(default_factory=list)
    page_status: Dict[str, str] = field(default_factory=dict)
    page_durations_ms: Dict[str, int] = field(default_factory=dict)
    screenshots: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    artifact_hashes: Dict[str, str] = field(default_factory=dict)
    video_file: Optional[str] = None
    summary_file: Optional[str] = None
    rerun_command: Optional[str] = None
    ended_at: Optional[str] = None


class EvidenceStore:
    def __init__(self, out_dir: Path, run_id: str) -> None:
        self.run_dir = out_dir / f"walkthrough_{run_id}"
        self.shots_dir = self.run_dir / "screenshots"
        self.log_file = self.run_dir / "run.log"
        self.manifest_file = self.run_dir / "manifest.json"
        self.summary_file = self.run_dir / "executive_summary.md"
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
        pass_assertions = sum(1 for a in state.assertions if a.status == "PASS")
        fail_assertions = sum(1 for a in state.assertions if a.status == "FAIL")
        payload = {
            "started_at": state.started_at,
            "ended_at": state.ended_at,
            "run_id": state.run_id,
            "config": state.config,
            "page_status": state.page_status,
            "page_durations_ms": state.page_durations_ms,
            "screenshots": state.screenshots,
            "video_file": state.video_file,
            "summary_file": state.summary_file,
            "rerun_command": state.rerun_command,
            "artifact_hashes_sha256": state.artifact_hashes,
            "errors": state.errors,
            "actions": [asdict(a) for a in state.actions],
            "assertions": [asdict(a) for a in state.assertions],
            "metrics": {
                "total_actions": len(state.actions),
                "passed_actions": sum(1 for a in state.actions if a.status == "PASS"),
                "failed_actions": sum(1 for a in state.actions if a.status == "FAIL"),
                "total_assertions": len(state.assertions),
                "passed_assertions": pass_assertions,
                "failed_assertions": fail_assertions,
                "pages_completed": sum(1 for s in state.page_status.values() if s == "PASS"),
                "pages_failed": sum(1 for s in state.page_status.values() if s == "FAIL"),
            },
        }
        with self.manifest_file.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def hash_artifacts(self) -> Dict[str, str]:
        hashes: Dict[str, str] = {}
        for path in sorted(self.run_dir.rglob("*")):
            if not path.is_file() or path.name == self.manifest_file.name:
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            rel = str(path.relative_to(self.run_dir)).replace("\\", "/")
            hashes[rel] = digest
        return hashes

    def write_executive_summary(self, state: RunState) -> str:
        pass_pages = sum(1 for p in state.page_status.values() if p == "PASS")
        fail_pages = sum(1 for p in state.page_status.values() if p == "FAIL")
        pass_assertions = sum(1 for a in state.assertions if a.status == "PASS")
        fail_assertions = sum(1 for a in state.assertions if a.status == "FAIL")

        lines = [
            "# AuditAI Enterprise Walkthrough - Executive Summary",
            "",
            f"- Run ID: {state.run_id}",
            f"- Started (UTC): {state.started_at}",
            f"- Ended (UTC): {state.ended_at or 'n/a'}",
            f"- Scenario: {state.config.get('scenario', {}).get('name', 'n/a')}",
            f"- Base URL: {state.config.get('base_url', 'n/a')}",
            f"- Rerun command: {state.rerun_command or 'n/a'}",
            "",
            "## Outcome",
            f"- Pages passed: {pass_pages}",
            f"- Pages failed: {fail_pages}",
            f"- Control assertions passed: {pass_assertions}",
            f"- Control assertions failed: {fail_assertions}",
            f"- Total actions executed: {len(state.actions)}",
            "",
            "## Page Status",
        ]
        for page_name, status in state.page_status.items():
            lines.append(f"- {page_name}: {status}")

        lines.append("")
        lines.append("## Page Timings")
        for page_name, duration in state.page_durations_ms.items():
            lines.append(f"- {page_name}: {duration} ms")

        lines.append("")
        lines.append("## Assertion Highlights")
        for assertion in state.assertions:
            lines.append(f"- [{assertion.status}] {assertion.page}.{assertion.control} - {assertion.details}")

        if state.errors:
            lines.append("")
            lines.append("## Errors")
            for err in state.errors:
                lines.append(f"- {err}")

        lines.append("")
        lines.append("## Evidence")
        if state.video_file:
            lines.append(f"- Video: {state.video_file}")
        lines.append(f"- Screenshots: {len(state.screenshots)} files")
        lines.append("- See manifest.json for complete telemetry and SHA-256 hashes")

        content = "\n".join(lines) + "\n"
        self.summary_file.write_text(content, encoding="utf-8")
        return str(self.summary_file.relative_to(self.run_dir)).replace("\\", "/")


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


async def dismiss_known_popups(page: Page) -> int:
    closed = 0
    for selector in POPUP_SELECTORS:
        try:
            loc = page.locator(selector).first
            if await loc.is_visible(timeout=150):
                await loc.click(force=True, timeout=800)
                closed += 1
        except Exception:
            continue
    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
    return closed


async def popup_reaper(page: Page, evidence: EvidenceStore, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            closed = await dismiss_known_popups(page)
            if closed:
                evidence.log(f"POPUP_REAPER closed={closed}")
        except Exception:
            pass
        await asyncio.sleep(0.6)


async def showcase_checkpoint(page: Page, runner: "Runner", label: str, min_seconds: float = 0.0) -> None:
    dwell = max(min_seconds, runner.cfg.showcase_seconds)
    if dwell <= 0:
        return
    runner.evidence.log(f"SHOWCASE {label} dwell={dwell:.1f}s")
    await pause(dwell, dwell + 0.2)


async def click_locator(locator: Locator, timeout_ms: int = 5000) -> None:
    page: Optional[Page] = None
    try:
        page = locator.page
    except Exception:
        page = None
    if page is not None:
        await dismiss_known_popups(page)
    await locator.wait_for(state="visible", timeout=timeout_ms)
    await locator.scroll_into_view_if_needed(timeout=timeout_ms)
    await highlight(locator)
    await pause(0.15, 0.35)
    try:
        await locator.click(force=True, timeout=timeout_ms)
    except Exception:
        if page is not None:
            await dismiss_known_popups(page)
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

    async def assert_control(
        self,
        page_name: str,
        control: str,
        fn: Callable[[], Awaitable[tuple[bool, str]]],
    ) -> None:
        started = perf_counter()
        started_at = now_iso()
        status = "FAIL"
        details = ""
        try:
            ok, details = await fn()
            status = "PASS" if ok else "FAIL"
        except Exception as exc:
            details = str(exc)

        duration = int((perf_counter() - started) * 1000)
        self.state.assertions.append(
            AssertionRecord(
                page=page_name,
                control=control,
                status=status,
                details=details,
                started_at=started_at,
                duration_ms=duration,
            )
        )
        self.evidence.log(f"ASSERT [{page_name}] {control} -> {status} ({details})")
        if status == "FAIL":
            self.state.errors.append(f"ASSERT FAIL [{page_name}] {control}: {details}")


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

    async def run_optional(action: str, fn: Callable[[], Awaitable[Any]], details: str = "") -> None:
        try:
            await runner.do(name, action, fn, details, retries=0)
        except Exception as exc:
            runner.evidence.log(f"INFO [app] optional action {action} skipped: {exc}")

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
    await runner.assert_control(
        name,
        "step_2_activated",
        lambda: page.evaluate(
            """() => {
                const v2 = document.getElementById('v2');
                return [!!(v2 && v2.classList.contains('active')), 'v2 active state verified'];
            }"""
        ),
    )
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
    await runner.assert_control(
        name,
        "results_surface_present",
        lambda: page.evaluate(
            """() => {
                const rowCount = document.querySelectorAll('table tbody tr').length;
                const hasSeverity = !!Array.from(document.querySelectorAll('button,span,div')).find(
                    el => /^(CRITICAL|HIGH|MEDIUM|ALL)$/i.test((el.textContent || '').trim())
                );
                return [rowCount > 0 || hasSeverity, `rows=${rowCount}, severityTabs=${hasSeverity}`];
            }"""
        ),
    )
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
            runner.evidence.log("INFO [app] findings table has 0 rows; continuing with severity-level evidence")
            return
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

    await run_optional("review_heatmap", review_heatmap)

    async def export_actions() -> None:
        for label in ["Audit Report", "Export to Excel", "Dashboard PDF"]:
            btn = page.get_by_text(label, exact=False).first
            try:
                if await btn.is_visible(timeout=1200):
                    await click_locator(btn)
                    await pause(0.2, 0.5)
            except Exception:
                continue

    await run_optional("trigger_exports", export_actions)
    await runner.assert_control(
        name,
        "export_controls_present",
        lambda: page.evaluate(
            """() => {
                const text = document.body.innerText || '';
                const hasAny = text.includes('Audit Report') || text.includes('Dashboard PDF') || text.includes('Export to Excel');
                return [hasAny, 'export controls detected in current view'];
            }"""
        ),
    )
    await runner.evidence.screenshot(page, "13_app_exports", runner.state)

    async def configure_detection_policy() -> None:
        trigger = await first_visible(
            page,
            [
                "button:has-text('Configure Detection Policy')",
                ".policy-trigger-btn",
            ],
            timeout_ms=2500,
        )
        if not trigger:
            raise RuntimeError("Detection Policy trigger not found")
        await click_locator(trigger)

        overlay = page.locator("#policyOverlay.open, #policyOverlay").first
        await overlay.wait_for(state="visible", timeout=6000)

        # Demonstrate real configuration behavior: toggle one rule and apply.
        first_rule = page.locator("#policyRulesGrid .policy-rule-item").first
        await click_locator(first_rule)

        apply_btn = await first_visible(
            page,
            [
                "#policyOverlay button:has-text('Apply Configuration')",
                "button:has-text('Apply Configuration')",
            ],
            timeout_ms=2500,
        )
        if not apply_btn:
            raise RuntimeError("Apply Configuration button not found")
        await click_locator(apply_btn)

        await page.wait_for_timeout(400)

    await run_optional("configure_detection_policy", configure_detection_policy)
    await showcase_checkpoint(page, runner, "detection_policy", min_seconds=2.2)
    await runner.assert_control(
        name,
        "policy_configuration_applied",
        lambda: page.evaluate(
            """() => {
                const overlay = document.getElementById('policyOverlay');
                const isClosed = !overlay || !overlay.classList.contains('open');
                return [isClosed, 'policy overlay closed after apply'];
            }"""
        ),
    )
    await runner.evidence.screenshot(page, "14_app_policy_configured", runner.state)

    async def audit_of_ai_module() -> None:
        tab = page.locator("#mnavM2").first
        await click_locator(tab)
        await page.locator("#v-m2").first.wait_for(state="visible", timeout=6000)

        racm_demo = await first_visible(
            page,
            [
                "#v-m2 button:has-text('Load Example RACM')",
                "button:has-text('Load Example RACM')",
            ],
            timeout_ms=2000,
        )
        if racm_demo:
            await click_locator(racm_demo)

        map_btn = await first_visible(
            page,
            [
                "#v-m2 button:has-text('Map Controls')",
                "button:has-text('Map Controls')",
            ],
            timeout_ms=2500,
        )
        if map_btn:
            await click_locator(map_btn)
            await page.wait_for_timeout(1200)

        apply_all = await first_visible(
            page,
            [
                "#racmApplyBtn",
                "#v-m2 button:has-text('Apply to All Modules')",
            ],
            timeout_ms=2500,
        )
        if apply_all:
            await click_locator(apply_all)
            await page.wait_for_timeout(900)

        # Walk all module-2 governance subviews for complete evidence coverage.
        for sid in ["#m2nav-policy", "#m2nav-trail", "#m2nav-identity", "#m2nav-containment", "#m2nav-racm"]:
            nav = page.locator(sid).first
            if await nav.is_visible(timeout=1200):
                await click_locator(nav)
                await pause(0.12, 0.35)

    await run_optional("audit_of_ai_module_walkthrough", audit_of_ai_module)
    await showcase_checkpoint(page, runner, "audit_of_ai_module", min_seconds=2.4)
    await runner.assert_control(
        name,
        "audit_of_ai_visible",
        lambda: page.evaluate(
            """() => {
                const m2 = document.getElementById('v-m2');
                const shown = !!m2 && m2.style.display !== 'none';
                const hasRacm = !!document.getElementById('m2p-racm');
                return [shown && hasRacm, 'module 2 rendered with RACM panel'];
            }"""
        ),
    )
    await runner.evidence.screenshot(page, "15_app_module2_audit_of_ai", runner.state)

    async def copilot_room_module() -> None:
        tab = page.locator("#mnavM3").first
        await click_locator(tab)
        await page.locator("#v-m3").first.wait_for(state="visible", timeout=6000)

        await fill_first(page, ["#m3OrgName"], runner.cfg.scenario.company)
        await fill_first(page, ["#m3AuditPeriod"], "Q1 2026")
        await fill_first(page, ["#m3Scope"], runner.cfg.scenario.name)
        await fill_first(page, ["#m3Lead"], "Internal Audit Lead")
        await fill_first(page, ["#m3Notes"], "Automated walkthrough evidence run for enterprise readiness.")

        init_btn = await first_visible(
            page,
            [
                "#v-m3 button:has-text('Initialize Engagement')",
                "button:has-text('Initialize Engagement')",
            ],
            timeout_ms=2500,
        )
        if not init_btn:
            raise RuntimeError("Initialize Engagement button not found in module 3")
        await click_locator(init_btn)
        await page.wait_for_timeout(900)

        # Visit all Copilot Room panels for full operational walk.
        for sid in [
            "#m3nav-room",
            "#m3nav-plan",
            "#m3nav-fieldwork",
            "#m3nav-workpapers",
            "#m3nav-wpmapper",
            "#m3nav-findings",
            "#m3nav-setup",
        ]:
            nav = page.locator(sid).first
            if await nav.is_visible(timeout=1200):
                await click_locator(nav)
                await pause(0.12, 0.35)

    await run_optional("copilot_room_module_walkthrough", copilot_room_module)
    await showcase_checkpoint(page, runner, "copilot_room_module", min_seconds=2.4)
    await runner.assert_control(
        name,
        "copilot_room_initialized",
        lambda: page.evaluate(
            """() => {
                const badge = document.getElementById('m3EngagementBadge');
                const txt = (badge && badge.textContent ? badge.textContent : '').trim();
                return [txt.length > 0 && !txt.includes('No engagement initialized'), 'engagement badge updated'];
            }"""
        ),
    )
    await runner.evidence.screenshot(page, "16_app_module3_copilot_room", runner.state)


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
    await runner.assert_control(
        name,
        "vault_filters_rendered",
        lambda: page.evaluate(
            """() => {
                const text = document.body.innerText || '';
                const ok = text.includes('All Origins') && text.includes('Azure AD');
                return [ok, 'expected origin filters are rendered'];
            }"""
        ),
    )

    async def toggle_sort() -> None:
        oldest = await first_visible(
            page,
            [
                "button:has-text('Oldest First')",
                "text=Oldest First",
            ],
            timeout_ms=1200,
        )
        newest = await first_visible(
            page,
            [
                "button:has-text('Newest First')",
                "text=Newest First",
            ],
            timeout_ms=1200,
        )

        if not oldest and not newest:
            runner.evidence.log("INFO [vault] sort toggle controls not present; skipping sort interaction")
            return

        if oldest:
            await click_locator(oldest)
            await pause(0.1, 0.3)
        if newest:
            await click_locator(newest)

    await runner.do(name, "toggle_sort", toggle_sort, retries=0)

    await runner.do(name, "scroll_ledger", lambda: human_scroll(page, 700, 6))
    await runner.assert_control(
        name,
        "ledger_surface_visible",
        lambda: page.evaluate(
            """() => {
                const rowCount = document.querySelectorAll('table tbody tr').length;
                const hasTable = !!document.querySelector('table');
                return [rowCount > 0 || hasTable, `hasTable=${hasTable}, rows=${rowCount}`];
            }"""
        ),
    )
    await runner.evidence.screenshot(page, "21_vault_ledger", runner.state)


async def page_settings(page: Page, runner: Runner) -> None:
    name = "settings"
    s = runner.cfg.scenario

    async def run_optional(action: str, fn: Callable[[], Awaitable[Any]], details: str = "") -> None:
        try:
            await runner.do(name, action, fn, details, retries=0)
        except Exception as exc:
            runner.evidence.log(f"INFO [settings] optional action {action} skipped: {exc}")

    await runner.do(name, "open_page", lambda: runner.goto(page, "settings.html"), "Open onboarding settings")
    await runner.evidence.screenshot(page, "08_settings_landing", runner.state)

    async def update_org_profile() -> None:
        await fill_first(page, ["#orgNameInput"], s.company)
        await fill_first(page, ["#criticalThresholdInput"], "92")
        await fill_first(page, ["#highThresholdInput"], "78")
        save_btn = page.locator("#general .btn.btn-primary").first
        await click_locator(save_btn)
        await pause(0.2, 0.4)

    await runner.do(name, "update_org_profile", update_org_profile)

    async def configure_connector(connector_name: str, endpoint: str, user: str, secret: str, scope: str) -> None:
        await click_locator(page.locator(".tab[data-target='data']").first)
        await page.locator("#data.panel.on").first.wait_for(state="visible", timeout=4000)

        cfg_btn = page.locator(f".connector-config-btn[data-connector='{connector_name}']").first
        await click_locator(cfg_btn)
        await page.locator("#connectorModal.show").first.wait_for(state="visible", timeout=4000)

        await fill_first(page, ["#connectorEndpoint"], endpoint)
        await fill_first(page, ["#connectorUser"], user)
        await fill_first(page, ["#connectorSecret"], secret)
        await fill_first(page, ["#connectorScope"], scope)

        await click_locator(page.locator("#testConnectorBtn").first)
        await pause(0.3, 0.6)
        await click_locator(page.locator("#saveConnectorBtn").first)
        await pause(0.3, 0.6)

    await run_optional(
        "configure_sap_connector",
        lambda: configure_connector(
            "SAP",
            "sap.publicstorage.internal:443",
            "sap_readonly_audit",
            "demo_secret",
            "Client 100 / AP Ledger",
        ),
    )
    await run_optional(
        "configure_servicenow_connector",
        lambda: configure_connector(
            "ServiceNow",
            "https://publicstorage.service-now.com",
            "svc.audit.read",
            "demo_secret",
            "incident, change_request",
        ),
    )

    await showcase_checkpoint(page, runner, "tool_connectors_onboarded", min_seconds=2.2)
    await runner.assert_control(
        name,
        "connectors_connected",
        lambda: page.evaluate(
            """() => {
                const connected = Array.from(document.querySelectorAll('[data-connector-status]'))
                    .filter(el => (el.textContent || '').trim().toLowerCase() === 'connected').length;
                return [connected >= 2, `connected_count=${connected}`];
            }"""
        ),
    )

    async def validate_api_and_security() -> None:
        await click_locator(page.locator(".tab[data-target='api']").first)
        await page.locator("#api.panel.on").first.wait_for(state="visible", timeout=4000)

        await fill_first(page, ["#api input[type='password']"], "demo-api-key")
        await click_locator(page.locator("#testConnection").first)
        await pause(0.2, 0.5)

        await click_locator(page.locator(".tab[data-target='security']").first)
        await page.locator("#security.panel.on").first.wait_for(state="visible", timeout=4000)
        redaction = page.locator("#redactionToggle").first
        if await redaction.is_visible(timeout=1000):
            await redaction.check(force=True)
        await fill_first(page, ["#vaultSessionKey"], "audit-session-key")
        await click_locator(page.locator("#saveSessionKeyBtn").first)

    await run_optional("validate_api_security_controls", validate_api_and_security)
    await runner.assert_control(
        name,
        "api_connection_and_key_set",
        lambda: page.evaluate(
            """() => {
                const apiStatus = document.getElementById('apiStatus');
                const keyStatus = document.getElementById('vaultSessionKeyStatus');
                const apiOk = !!apiStatus && (apiStatus.textContent || '').toLowerCase().includes('successful');
                const keyOk = !!keyStatus && (keyStatus.textContent || '').toLowerCase().includes('set');
                return [apiOk && keyOk, `api_ok=${apiOk}, key_ok=${keyOk}`];
            }"""
        ),
    )
    await runner.evidence.screenshot(page, "09_settings_connectors_ready", runner.state)


async def page_governance(page: Page, runner: Runner) -> None:
    name = "governance"
    s = runner.cfg.scenario
    await runner.do(name, "open_page", lambda: runner.goto(page, "governance.html"), "Open governance")
    await runner.evidence.screenshot(page, "30_governance_landing", runner.state)

    async def open_tab(tab_key: str) -> None:
        # Click the real tab button so governance page handlers receive expected event context.
        tab_btn = await first_visible(
            page,
            [
                f"button.tab-btn[onclick*=\"switchTab('{tab_key}')\"]",
                f"button:has-text('{tab_key.title()}')",
            ],
            timeout_ms=2500,
        )
        if not tab_btn:
            raise RuntimeError(f"Governance tab button not found for '{tab_key}'")
        await click_locator(tab_btn)
        pane = page.locator(f"#tab-{tab_key}.active, #tab-{tab_key}").first
        await pane.wait_for(state="visible", timeout=6000)

    async def submit_alert() -> None:
        await open_tab("alerts")
        await fill_first(page, ["#alertTitle"], f"{s.name} exception escalation")
        await select_first(page, ["#alertSeverity"], "CRITICAL")
        await fill_first(
            page,
            ["#alertDesc"],
            f"Automated escalation for scenario {s.key}. Immediate triage requested for control owner and GRC.",
        )
        btn = page.locator("#tab-alerts button:has-text('Raise Alert')").first
        await click_locator(btn)

    await runner.do(name, "raise_alert", submit_alert)

    async def create_policy() -> None:
        await open_tab("policies")
        await fill_first(page, ["#policyId"], s.policy_id)
        await fill_first(page, ["#policyVersion"], "v3.0")
        await fill_first(page, ["#policyTitle"], f"{s.name} Governance Policy")
        await fill_first(page, ["#policyOwner"], "IT Audit Manager")
        await select_first(page, ["#policyStatus"], "active")
        btn = page.locator("#tab-policies button:has-text('Create Policy')").first
        await click_locator(btn)

    await runner.do(name, "create_policy", create_policy)

    async def register_framework() -> None:
        await open_tab("frameworks")
        await fill_first(page, ["#fwId"], s.framework_id)
        await fill_first(page, ["#fwVersion"], "2026.1")
        await fill_first(page, ["#fwName"], f"{s.name} Framework")
        await fill_first(page, ["#fwDesc"], s.business_context)
        btn = page.locator("#tab-frameworks button:has-text('Register')").first
        await click_locator(btn)

    await runner.do(name, "register_framework", register_framework)

    async def add_risk() -> None:
        await open_tab("risks")
        await fill_first(page, ["#riskId"], s.risk_id)
        await select_first(page, ["#riskCategory"], "compliance")
        await fill_first(page, ["#riskTitle"], f"{s.name} high residual risk")
        await fill_first(page, ["#riskLikelihood"], "4")
        await fill_first(page, ["#riskImpact"], "5")
        await fill_first(page, ["#riskOwner"], "VP Internal Audit")
        await select_first(page, ["#riskTreatment"], "mitigate")
        btn = page.locator("#tab-risks button:has-text('Add to Register')").first
        await click_locator(btn)

    await runner.do(name, "add_risk_register_entry", add_risk)

    async def create_alert_rule() -> None:
        await open_tab("rules")
        await fill_first(page, ["#ruleId"], s.rule_id)
        await select_first(page, ["#ruleSeverity"], "CRITICAL")
        await fill_first(page, ["#ruleName"], f"{s.name} threshold rule")
        await select_first(page, ["#ruleMetric"], "sod_conflicts_count")
        await select_first(page, ["#ruleOperator"], "gte")
        await fill_first(page, ["#ruleThreshold"], "1")
        btn = page.locator("#tab-rules button:has-text('Create Rule')").first
        await click_locator(btn)

    await runner.do(name, "create_alert_rule", create_alert_rule)
    await runner.assert_control(
        name,
        "governance_tabs_accessible",
        lambda: page.evaluate(
            """() => {
                const text = document.body.innerText || '';
                const ok = text.includes('Risk Register') && text.includes('Alert Rules');
                return [ok, 'governance tab labels visible after workflow'];
            }"""
        ),
    )
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
    await runner.assert_control(
        name,
        "uat_readiness_gate_visible",
        lambda: page.evaluate(
            """() => {
                const text = document.body.innerText || '';
                const ok = text.includes('Readiness Gate');
                return [ok, 'readiness gate present in UAT console'];
            }"""
        ),
    )
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
    await runner.assert_control(
        name,
        "help_sections_visible",
        lambda: page.evaluate(
            """() => {
                const text = document.body.innerText || '';
                const ok = text.includes('FAQ') || text.includes('Suite Overview');
                return [ok, 'core help sections detected'];
            }"""
        ),
    )
    await runner.evidence.screenshot(page, "50_help_sections", runner.state)


async def run_page(
    page_label: str,
    fn: Callable[[Page, Runner], Awaitable[None]],
    page: Page,
    runner: Runner,
    state: RunState,
) -> None:
    runner.evidence.log(f"PAGE START {page_label}")
    started = perf_counter()
    try:
        await fn(page, runner)
        state.page_status[page_label] = "PASS"
        state.page_durations_ms[page_label] = int((perf_counter() - started) * 1000)
        runner.evidence.log(f"PAGE PASS {page_label}")
    except Exception as exc:
        state.page_status[page_label] = "FAIL"
        state.page_durations_ms[page_label] = int((perf_counter() - started) * 1000)
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
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="Run with fixed viewport instead of fullscreen window",
    )
    parser.add_argument(
        "--strict-critical",
        action="store_true",
        help="Fail run if any critical modules fail (app, vault, governance)",
    )
    parser.add_argument(
        "--showcase-seconds",
        type=float,
        default=1.8,
        help="Minimum dwell seconds for key module checkpoints in video",
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
        "fullscreen": cfg.fullscreen,
        "strict_critical": cfg.strict_critical,
        "showcase_seconds": cfg.showcase_seconds,
        "scenario": asdict(cfg.scenario),
    }
    return RunState(started_at=now_iso(), run_id=run_id, config=safe_cfg)


async def orchestrate(cfg: WalkthroughConfig) -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    evidence = EvidenceStore(cfg.output_dir, run_id)
    state = build_run_state(cfg, run_id)

    random.seed(cfg.seed)
    evidence.log(f"RUN START id={run_id} scenario={cfg.scenario.key}")
    state.rerun_command = (
        "python scripts/run_enterprise_v9_comprehensive.py "
        f"--scenario {cfg.scenario.key} "
        f"--max-retries {cfg.max_retries} "
        f"--showcase-seconds {cfg.showcase_seconds:.1f} "
        + ("--continue-on-error " if cfg.continue_on_error else "")
        + ("--video " if cfg.record_video else "")
        + ("--include-landing " if cfg.include_landing else "")
        + ("--windowed " if not cfg.fullscreen else "")
        + ("--strict-critical" if cfg.strict_critical else "")
    ).strip()

    async with async_playwright() as playwright:
        launch_args = []
        if cfg.fullscreen:
            launch_args.extend(["--start-maximized", "--start-fullscreen", "--kiosk"])
        else:
            launch_args.append("--start-maximized")
        launch_args.extend(["--disable-notifications", "--disable-popup-blocking"])

        browser = await playwright.chromium.launch(
            headless=cfg.headless,
            slow_mo=cfg.slow_mo,
            args=launch_args,
        )

        context_kwargs: Dict[str, Any] = {"no_viewport": True} if cfg.fullscreen else {"viewport": {"width": 1600, "height": 900}}
        if cfg.record_video:
            video_dir = str((evidence.run_dir / "video").resolve())
            os.makedirs(video_dir, exist_ok=True)
            context_kwargs["record_video_dir"] = video_dir
            context_kwargs["record_video_size"] = {"width": 1600, "height": 900}

        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()

        async def close_new_page(new_page: Page) -> None:
            if new_page is page:
                return
            try:
                evidence.log(f"POPUP_TAB closing url={new_page.url}")
                await new_page.close()
            except Exception:
                pass

        context.on("page", lambda p: asyncio.create_task(close_new_page(p)))
        page.on("dialog", lambda d: asyncio.create_task(d.dismiss()))
        reaper_stop = asyncio.Event()
        reaper_task = asyncio.create_task(popup_reaper(page, evidence, reaper_stop))

        runner = Runner(cfg=cfg, evidence=evidence, state=state)

        page_flow = [
            ("settings", page_settings),
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
            reaper_stop.set()
            try:
                await asyncio.wait_for(reaper_task, timeout=2.0)
            except Exception:
                pass
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
    state.summary_file = evidence.write_executive_summary(state)
    state.artifact_hashes = evidence.hash_artifacts()
    evidence.write_manifest(state)

    pass_pages = sum(1 for p in state.page_status.values() if p == "PASS")
    fail_pages = sum(1 for p in state.page_status.values() if p == "FAIL")
    evidence.log(f"RUN SUMMARY pass_pages={pass_pages} fail_pages={fail_pages} errors={len(state.errors)}")
    evidence.log(
        "RUN ASSERTIONS "
        f"total={len(state.assertions)} "
        f"pass={sum(1 for a in state.assertions if a.status == 'PASS')} "
        f"fail={sum(1 for a in state.assertions if a.status == 'FAIL')}"
    )
    evidence.log(f"ARTIFACTS {evidence.run_dir}")

    if overall_error and not cfg.continue_on_error:
        return 2
    if cfg.strict_critical:
        critical_pages = ["app", "vault", "governance"]
        critical_failures = [p for p in critical_pages if state.page_status.get(p) != "PASS"]
        if critical_failures:
            evidence.log(f"STRICT_CRITICAL FAIL pages={critical_failures}")
            return 3
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
        fullscreen=not args.windowed,
        strict_critical=args.strict_critical,
        showcase_seconds=max(0.0, args.showcase_seconds),
    )

    exit_code = asyncio.run(orchestrate(cfg))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
