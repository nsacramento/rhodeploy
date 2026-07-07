"""Quick smoke test for the debrief module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.decisions import get_decisions
from rho.modules.debrief   import save_debrief, get_debrief, get_recent_debriefs

SEP = "=" * 55

# ── Find the most recent decision to debrief ──────────────────────────────────
print("\nFetching most recent decision...")
decisions = get_decisions(limit=1)

if not decisions:
    print("  No decisions found — run test_decisions.py first.")
    sys.exit(1)

decision = decisions[0]
print(f"  Decision: {decision['origin']} → {decision['destination']}")
print(f"  Pre-flight call: {decision['recommendation']} — {decision['reason']}")
print(f"  Decision ID: {decision['id']}")

# ── Save a debrief ────────────────────────────────────────────────────────────
print("\nSaving debrief...")
saved = save_debrief(
    decision_id          = decision["id"],
    flight_duration_min  = 22,
    actual_route         = "Direct KSRQ → KVNC, remained clear of Class C",
    weather_actual       = "VFR as forecast, winds calm, smooth at 3500ft",
    go_nogo_correct      = True,
    lessons              = "Verify ATIS before taxi — frequency was slightly different than expected",
    notes                = "Smooth flight, good practice on radio calls with Tampa Approach",
)
print(f"  Saved! ID: {saved['id']}")

# ── Retrieve it back ──────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  DEBRIEF: {decision['origin']} → {decision['destination']}")
print(f"{SEP}")

d = get_debrief(decision["id"])
print(f"  Duration     : {d['flight_duration_min']} min")
print(f"  Route flown  : {d['actual_route']}")
print(f"  Weather      : {d['weather_actual']}")
print(f"  Call correct : {'✓ Yes' if d['go_nogo_correct'] else '✗ No'}")
print(f"  Lessons      : {d['lessons']}")
print(f"  Notes        : {d['notes']}")

# ── Recent debriefs ───────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  RECENT DEBRIEFS")
print(f"{SEP}")

for db in get_recent_debriefs(limit=3):
    dec = db.get("decisions") or {}
    print(f"\n  {dec.get('origin','?')} → {dec.get('destination','?')}  |  {db['created_at'][:16]}")
    print(f"  Call correct: {'✓' if db.get('go_nogo_correct') else '✗'}  |  {db.get('flight_duration_min','?')} min")
    if db.get("lessons"):
        print(f"  Lessons: {db['lessons']}")

print(f"\n{SEP}\n")
