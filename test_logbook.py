"""Quick smoke test for the logbook module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.logbook import log_flight, get_flights, get_progress

SEP = "=" * 55

# ── Log a few sample flights ──────────────────────────────────────────────────
print("\nLogging sample flights...")

log_flight("KSRQ", "KSRQ", duration_min=60,  flight_date="2026-05-01",
           dual=True, takeoffs=4, landings=4,
           remarks="Pattern work, touch-and-goes")

log_flight("KSRQ", "KVNC", duration_min=90,  flight_date="2026-05-10",
           dual=True, cross_country=True, takeoffs=1, landings=1,
           remarks="First dual XC to Venice")

log_flight("KSRQ", "KSRQ", duration_min=45,  flight_date="2026-05-20",
           solo=True, takeoffs=3, landings=3,
           remarks="First solo!")

log_flight("KSRQ", "KSRQ", duration_min=120, flight_date="2026-05-28",
           dual=True, night=True, night_takeoffs=3, night_landings=3,
           takeoffs=3, landings=3, remarks="Night currency with CFI")

log_flight("KSRQ", "KSRQ", duration_min=60,  flight_date="2026-06-01",
           dual=True, instrument_hood=True, takeoffs=1, landings=1,
           remarks="Hood work, unusual attitudes")

print(f"  5 flights logged.")

# ── Recent flights ────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  FLIGHT LOG (most recent 5)")
print(f"{SEP}")

for f in get_flights(limit=5):
    hrs  = f['duration_min'] // 60
    mins = f['duration_min'] % 60
    tags = []
    if f.get("dual"):         tags.append("DUAL")
    if f.get("solo"):         tags.append("SOLO")
    if f.get("cross_country"): tags.append("XC")
    if f.get("night"):        tags.append("NIGHT")
    if f.get("instrument_hood"): tags.append("HOOD")
    print(f"  {f['flight_date']}  {f['origin']}→{f['destination']}  "
          f"{hrs}h{mins:02d}m  {' '.join(tags)}")
    if f.get("remarks"):
        print(f"             {f['remarks']}")

# ── Part 61 progress ──────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  PART 61 PROGRESS")
print(f"{SEP}")

p = get_progress()
print(f"\n  {p['summary']}")
print(f"  Total flights logged: {p['flights']}")
print()

labels = {
    "total_hours":           "Total flight time",
    "dual_hours":            "Dual (with instructor)",
    "solo_hours":            "Solo",
    "dual_xc_hours":         "Dual cross-country",
    "dual_night_hours":      "Dual night",
    "dual_instrument_hours": "Dual instrument (hood)",
}

for key, req in p["progress"].items():
    bar_filled = int((req["logged"] / req["required"]) * 20) if req["required"] else 20
    bar_filled = min(bar_filled, 20)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)
    status = "✓" if req["met"] else f"{req['remaining']} hrs to go"
    print(f"  {labels[key]:<28}  [{bar}]  {req['logged']:4.1f}/{req['required']:.0f} hrs  {status}")

print(f"\n{SEP}\n")
