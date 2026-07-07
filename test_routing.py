"""
Quick smoke test for the routing module — run from /Users/nic/rho
Tests a route from KSRQ to KVNC (Venice Municipal, ~15nm south)
"""
import sys
sys.path.insert(0, ".")
from rho.modules.routing import get_airspace_near, generate_routes, get_airspace_at_point

# KSRQ coords
KSRQ_LAT, KSRQ_LON = 27.3954, -82.5544
# KVNC (Venice) coords
KVNC_LAT, KVNC_LON = 27.0716, -82.4403

print("\nFetching airspace within 50nm of KSRQ...")
airspaces = get_airspace_near(KSRQ_LAT, KSRQ_LON, radius_nm=50)

print(f"\n{'='*55}")
print(f"  Airspace near KSRQ ({len(airspaces)} polygons)")
print(f"{'='*55}")
seen = set()
for a in airspaces:
    key = (a['name'], a['airspace_class'])
    if key not in seen:
        print(f"  Class {a['airspace_class']:2s}  {a['lower_ft']:>12} – {a['upper_ft']:>12}  {a['name']}")
        seen.add(key)

print(f"\n{'='*55}")
print(f"  Am I in controlled airspace at KSRQ?")
print(f"{'='*55}")
at_ksrq = get_airspace_at_point(KSRQ_LAT, KSRQ_LON, airspaces)
if at_ksrq:
    for a in at_ksrq:
        print(f"  YES — Class {a['airspace_class']}: {a['name']}  ({a['lower_ft']} – {a['upper_ft']})")
else:
    print("  Not within any tracked airspace polygon at this point.")

print(f"\n{'='*55}")
print(f"  Route: KSRQ → KVNC")
print(f"{'='*55}")
routes = generate_routes(KSRQ_LAT, KSRQ_LON, KVNC_LAT, KVNC_LON, airspaces)

for variant, route in routes.items():
    print(f"\n  [{variant.upper()}]  {route['distance_nm']} nm")
    if route.get("airspace_penetrations"):
        for p in route["airspace_penetrations"]:
            print(f"    ⚠ Penetrates Class {p['class']}: {p['name']}  ({p['lower']} – {p['upper']})")
    else:
        print("    ✓ No controlled airspace penetrations on direct route")
    if route.get("note"):
        print(f"    Note: {route['note']}")

print(f"\n{'='*55}\n")
