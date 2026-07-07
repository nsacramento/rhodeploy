"""Quick smoke test for the airport module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.airport import get_airport_full

apt = get_airport_full("KSRQ")
print(f"\n{'='*40}")
print(f"  {apt['icao']} — {apt['name']}")
print(f"  {apt['city']}, {apt['state']}")
print(f"  Elevation : {apt['elevation_ft']} ft MSL")
print(f"  Coords    : {apt['lat']:.4f}N, {abs(apt['lon']):.4f}W")
print(f"  Status    : {apt['status']}")
print(f"\n  Runways ({len(apt['runways'])}):")
for rwy in apt['runways']:
    lit = "✓ lighted" if rwy['lighted'] else "no lights"
    print(f"    RWY {rwy['designator']:6s}  {rwy['length_ft']:,} x {rwy['width_ft']} ft  {rwy['surface']}  {lit}")
print(f"{'='*40}\n")
