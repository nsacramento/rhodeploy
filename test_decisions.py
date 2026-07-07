"""Quick smoke test for the decisions module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.insights  import get_preflight_brief
from rho.modules.decisions import save_decision, get_decisions

SEP = "=" * 55

# ── Generate a brief and save the decision ────────────────────────────────────
print("\nGenerating brief for KSRQ → KVNC...")
brief = get_preflight_brief("KSRQ", "KVNC")

print(f"  Recommendation: {brief['recommendation']} — {brief['reason']}")
print("\nSaving decision to Supabase...")

saved = save_decision(brief, notes="Test decision from Rho smoke test")

print(f"  Saved! ID: {saved['id']}")
print(f"  Created: {saved['created_at']}")

# ── Fetch recent decisions ────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  RECENT DECISIONS (last 5)")
print(f"{SEP}")

decisions = get_decisions(limit=5)
if not decisions:
    print("  No decisions found.")
else:
    for d in decisions:
        print(f"\n  [{d['created_at'][:16]}]  {d['origin']} → {d['destination']}")
        print(f"  {d['recommendation']} — {d['reason']}")
        if d.get("notes"):
            print(f"  Notes: {d['notes']}")

print(f"\n{SEP}\n")
