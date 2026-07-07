"""Quick smoke test for the insights module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.insights import get_preflight_brief

print("\nGenerating pre-flight brief: KSRQ → KVNC...")
brief = get_preflight_brief("KSRQ", "KVNC")

SEP = "=" * 55

print(f"\n{SEP}")
print(f"  PRE-FLIGHT BRIEF: {brief['origin_icao']} → {brief['dest_icao']}")
print(f"{SEP}")

# Origin
o = brief["origin_assess"]
print(f"\n  ORIGIN  ({brief['origin_icao']})")
print(f"  Category  : {o['category']}")
print(f"  METAR     : {o['raw_metar']}")
print(f"  Wind      : {o['wind_dir']}° at {o['wind_kt']} kt")
if o["best_runway"]:
    print(f"  Best RWY  : {o['best_runway']}  (xwind ~{o['crosswind_kt']} kt)")
print(f"  TAF trend : {o['trend']}")

# Destination
d = brief["dest_assess"]
print(f"\n  DESTINATION ({brief['dest_icao']})")
print(f"  Category  : {d['category']}")
print(f"  METAR     : {d['raw_metar']}")
print(f"  Wind      : {d['wind_dir']}° at {d['wind_kt']} kt")
if d["best_runway"]:
    print(f"  Best RWY  : {d['best_runway']}  (xwind ~{d['crosswind_kt']} kt)")
print(f"  TAF trend : {d['trend']}")

# Route
if brief["route"]:
    print(f"\n  ROUTE")
    print(f"  Distance  : {brief['route']['direct']['distance_nm']} nm")

# Hazards
print(f"\n  HAZARDS")
if brief["hazards"]:
    for h in brief["hazards"]:
        print(f"  ⚠  {h}")
else:
    print("  ✓ No significant hazards")

# Recommendation
print(f"\n{SEP}")
rec = brief["recommendation"]
print(f"  RECOMMENDATION: {rec}")
print(f"  {brief['reason']}")
print(f"{SEP}")

# Summary
print(f"\n  SUMMARY")
print(f"  {brief['summary']}")
print(f"\n{SEP}\n")
