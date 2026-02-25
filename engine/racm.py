"""
engine/racm.py
──────────────
Risk-Assessment-Control-Mitigation (RACM) Module.

Provides:
  1. RACM_TABLE        — maps every control_id to COSO component and PCAOB
                         AS 2201 paragraph reference.
  2. enrich_with_racm  — annotates a finding dict with its RACM reference.
  3. check_compensating_controls — degrades severity when a detective control
                         mitigates a failed preventative control.
  4. sample_generator  — produces a statistical sample plan for every
                         100%-population test run by the engine.
"""
from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple


# ─── RACM Lookup Table ────────────────────────────────────────────────────────
# Keys are control_id prefixes (matched with startswith).
# Values carry:
#   coso_component  – one of the five COSO 2013 framework components
#   pcaob_ref       – PCAOB AS 2201 paragraph(s) most relevant to this control
#   finding_type    – short label used in audit reports
# ─────────────────────────────────────────────────────────────────────────────
RACM_TABLE: List[Dict[str, str]] = [
    # Segregation of Duties
    {
        "control_id_prefix": "ITGC-SOD",
        "coso_component": "Control Environment",
        "coso_principle": "COSO CC1.4 – Commitment to Competence and Accountability",
        "pcaob_ref": "PCAOB AS 2201 §26 (Fraud Risk), §39 (Significant Deficiency)",
        "finding_category": "Segregation of Duties",
        "sox_section": "SOX §404",
    },
    # Logical Access Controls
    {
        "control_id_prefix": "ITGC-LA",
        "coso_component": "Control Activities",
        "coso_principle": "COSO CC6.1 – Logical Access Security",
        "pcaob_ref": "PCAOB AS 2201 §25 (Access Controls), §42 (IT Controls)",
        "finding_category": "Logical Access Controls",
        "sox_section": "SOX §302, §404",
    },
    # Change Management
    {
        "control_id_prefix": "ITGC-CM",
        "coso_component": "Control Activities",
        "coso_principle": "COSO CC8.1 – Change Management Controls",
        "pcaob_ref": "PCAOB AS 2201 §42 (IT General Controls), §B9 (Program Changes)",
        "finding_category": "Change Management",
        "sox_section": "SOX §404",
    },
    # Computer Operations – Backup & Recovery
    {
        "control_id_prefix": "ITGC-OPS",
        "coso_component": "Risk Assessment",
        "coso_principle": "COSO CC9.1 – Business Continuity and Availability",
        "pcaob_ref": "PCAOB AS 2201 §42 (IT General Controls), §B10 (Computer Operations)",
        "finding_category": "Computer Operations",
        "sox_section": "SOX §404",
    },
    # IT Application Controls – Accounts Payable
    {
        "control_id_prefix": "ITAC-AP",
        "coso_component": "Control Activities",
        "coso_principle": "COSO CC4.1 – Transaction Authorization and Approval",
        "pcaob_ref": "PCAOB AS 2201 §26 (Fraud Risk), §43 (Application Controls)",
        "finding_category": "IT Application Controls – AP",
        "sox_section": "SOX §302, §404",
    },
    # IT Application Controls – Interfaces
    {
        "control_id_prefix": "ITAC-INT",
        "coso_component": "Information & Communication",
        "coso_principle": "COSO CC2.1 – Information Quality and Completeness",
        "pcaob_ref": "PCAOB AS 2201 §42 (IT General Controls), §43 (Interface Controls)",
        "finding_category": "IT Application Controls – Interfaces",
        "sox_section": "SOX §404",
    },
]

# Fallback when no prefix matches
_RACM_DEFAULT: Dict[str, str] = {
    "coso_component": "Monitoring Activities",
    "coso_principle": "COSO CC4.2 – Ongoing Monitoring",
    "pcaob_ref": "PCAOB AS 2201 §42 (IT General Controls)",
    "finding_category": "General IT Control",
    "sox_section": "SOX §404",
}


def get_racm(control_id: str) -> Dict[str, str]:
    """Return the RACM reference record for a given control_id."""
    for entry in RACM_TABLE:
        if control_id.startswith(entry["control_id_prefix"]):
            return {k: v for k, v in entry.items() if k != "control_id_prefix"}
    return dict(_RACM_DEFAULT)


def enrich_with_racm(finding: Dict[str, Any]) -> Dict[str, Any]:
    """
    Annotate a finding dict in-place with RACM references.
    Adds a 'racm' sub-dict containing COSO and PCAOB AS 2201 references.
    Returns the mutated finding for convenience.
    """
    control_id = finding.get("control_id", "")
    finding["racm"] = get_racm(control_id)
    return finding


# ─── Compensating Controls ────────────────────────────────────────────────────

# Detective controls that can compensate for a failed preventative control.
# Format: control_id_prefix → list of compensating detective control indicators
_COMPENSATING_DETECTIVE_CONTROLS: Dict[str, List[str]] = {
    "ITGC-SOD": [
        "monthly_access_review",
        "manager_access_review",
        "quarterly_access_review",
        "privileged_access_review",
        "user_access_review",
    ],
    "ITGC-LA": [
        "privileged_access_review",
        "siem_alert",
        "dlp_monitor",
        "log_review",
    ],
    "ITAC-AP": [
        "manager_review_log",
        "month_end_review",
        "ap_reconciliation",
        "vendor_statement_recon",
    ],
}


def check_compensating_controls(
    finding: Dict[str, Any],
    available_controls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Check whether a detective compensating control mitigates a failed
    preventative control.  If one is present the severity is reduced
    from CRITICAL → HIGH, and a note is added to the finding.

    Args:
        finding:            The finding dict (may be mutated in-place).
        available_controls: List of detective-control identifiers that are
                            active in the environment (e.g. from a controls
                            inventory uploaded alongside the audit data).

    Returns:
        The (potentially updated) finding dict.
    """
    if available_controls is None:
        available_controls = []

    control_id = finding.get("control_id", "")
    current_risk = finding.get("risk_level", "LOW")

    # Only attempt mitigation for CRITICAL findings
    if current_risk != "CRITICAL":
        return finding

    detective_keys: List[str] = []
    for prefix, keys in _COMPENSATING_DETECTIVE_CONTROLS.items():
        if control_id.startswith(prefix):
            detective_keys = keys
            break

    matched = [k for k in detective_keys if k in available_controls]
    if matched:
        finding["risk_level"] = "HIGH"
        finding["compensating_control_applied"] = True
        finding["compensating_controls"] = matched
        rec = finding.get("recommendation", "")
        finding["recommendation"] = (
            rec
            + f" [COMPENSATING CONTROL ACTIVE: {', '.join(matched)} — severity"
            " reduced from CRITICAL to HIGH pending formal control effectiveness review]"
        )
    else:
        finding["compensating_control_applied"] = False

    return finding


# ─── Statistical Sampling ─────────────────────────────────────────────────────

def sample_generator(
    population: List[Any],
    confidence_level: float = 0.95,
    margin_of_error: float = 0.05,
    expected_prevalence: float = 0.5,
) -> Dict[str, Any]:
    """
    Generate a statistical sample plan from a full population.

    Uses the standard formula for finite-population sample size:
        n₀ = z² · p · (1-p) / e²
        n  = n₀ / (1 + (n₀ - 1) / N)

    Args:
        population:          The full list of records (100 % census).
        confidence_level:    Desired confidence level (default 0.95 → 95 %).
        margin_of_error:     Acceptable margin of error (default 0.05 → ±5 %).
        expected_prevalence: Expected error rate (default 0.5 = worst case).

    Returns:
        A dict containing:
          - population_size     : total records in the population
          - sample_size         : calculated sample size
          - confidence_level_pct: confidence level as a percentage string
          - margin_of_error_pct : margin of error as a percentage string
          - z_score             : z-score used in the calculation
          - sample_indices      : list of 0-based indices of sampled records
          - sample_records      : the sampled records themselves
          - methodology         : short description for the audit report
    """
    # z-score lookup for common confidence levels
    _Z_SCORES: Dict[float, float] = {
        0.90: 1.645,
        0.95: 1.960,
        0.99: 2.576,
    }
    z = _Z_SCORES.get(confidence_level, 1.960)

    N = len(population)
    if N == 0:
        return {
            "population_size": 0,
            "sample_size": 0,
            "confidence_level_pct": f"{int(confidence_level * 100)}%",
            "margin_of_error_pct": f"{int(margin_of_error * 100)}%",
            "z_score": z,
            "sample_indices": [],
            "sample_records": [],
            "methodology": "No records in population — sampling not applicable.",
        }

    p = expected_prevalence
    e = margin_of_error

    # Infinite-population sample size
    n0 = (z ** 2 * p * (1 - p)) / (e ** 2)
    # Finite-population correction
    n = math.ceil(n0 / (1 + (n0 - 1) / N))
    # Cap at population size
    n = min(n, N)

    random.seed(42)  # deterministic seed for reproducibility
    indices = sorted(random.sample(range(N), n))
    sample = [population[i] for i in indices]

    return {
        "population_size": N,
        "sample_size": n,
        "confidence_level_pct": f"{int(confidence_level * 100)}%",
        "margin_of_error_pct": f"±{int(margin_of_error * 100)}%",
        "z_score": round(z, 3),
        "sample_indices": indices,
        "sample_records": sample,
        "methodology": (
            f"Statistical random sample: {n} of {N} records selected at a "
            f"{int(confidence_level * 100)}% confidence level with a "
            f"±{int(margin_of_error * 100)}% margin of error "
            f"(z={z}, p={p}). Seed=42 for reproducibility."
        ),
    }
