"""
demo_intelligence.py — End-to-end demo of the Auditor Intelligence pipeline
Shows how 400+ noise events are deduplicated and real risks are surfaced.
"""
import json
from core.sox_validator import SOXValidator
from core.forensic_engine import ForensicEngine
from core.sqlite_store import AuditIntelligenceStore

validator = SOXValidator()
forensic = ForensicEngine()
store = AuditIntelligenceStore()

# ─── Simulate the exact UAT problem: 400+ 'Negative Amount' warnings ─────
noise_events = [
    {"id": i, "source_system": "ERP-Accounts-Payable", "event_type": "validation_error",
     "log_data": "Negative Amount detected in invoice processing: -$12.50",
     "amount": -12.50}
    for i in range(400)
]

# ─── Add 3 real high-risk events ─────────────────────────────────────────
real_risks = [
    {"id": 401, "source_system": "Treasury-Wire", "event_type": "unauthorized_access",
     "log_data": "Root access granted to unapproved user for wire transfer of $85000",
     "amount": 85000, "user": "rogue_admin", "access_level": "root"},
    {"id": 402, "source_system": "Payroll-System", "event_type": "validation_bypass",
     "log_data": "Payroll batch approved without secondary authorization: $125000",
     "amount": 125000},
    {"id": 403, "source_system": "GL-Journal", "event_type": "detect_anomaly",
     "log_data": "Manual journal entry exceeds threshold: $250000 posted at 2:00AM",
     "amount": 250000},
]

all_events = noise_events + real_risks
result = validator.process_events(all_events)

s = result["summary"]
print("=" * 60)
print("  AUDITOR INTELLIGENCE — DEDUPLICATION DEMO")
print("=" * 60)
print(f"  Raw events input:       {s['total_raw_events']}")
print(f"  Findings output:        {len(result['findings'])}")
print(f"  Systemic groups:        {s['systemic_groups']}")
print(f"  Auto-cleared:           {s['auto_cleared']}")
print(f"  Critical:               {s['critical_findings']}")
print(f"  High:                   {s['high_findings']}")
print(f"  Medium:                 {s['medium_findings']}")
print(f"  Low:                    {s['low_findings']}")
print(f"  Total impact:           ${s['total_financial_impact']:,.2f}")
print()

for f in result["findings"][:5]:
    print(f"  [{f['priority']:8s}] Score={f['risk_score']:5.1f} | ${f['financial_impact']:>12,.2f} | {f['description'][:80]}")
    reasons = f["auditor_reasoning"].split(" | ")
    for r in reasons[:2]:
        print(f"           >> {r[:100]}")
    print()

# Save to SQLite
store.save_findings(result["findings"])
summary = forensic.generate_executive_summary(result["findings"], result["summary"])
store.save_executive_summary(summary)

print("=" * 60)
print("  EXECUTIVE SUMMARY")
print("=" * 60)
print(f"  Headline:     {summary['headline'][:100]}")
print(f"  Risk Posture: {summary['risk_posture']}")
print(f"  Integrity:    valid={summary['integrity_check']['is_valid']}, confidence={summary['integrity_check']['confidence_score']}")
print()

dash = store.get_findings_summary()
print("  SQLite Dashboard Summary:")
print(f"    Total findings:  {dash['total_findings']}")
print(f"    Critical:        {dash['critical']}")
print(f"    High:            {dash['high']}")
print(f"    Avg risk score:  {dash['average_risk_score']}")
print(f"    Financial impact: ${dash['total_financial_impact']:,.2f}")
print("=" * 60)
