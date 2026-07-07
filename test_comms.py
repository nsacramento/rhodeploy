"""Quick smoke test for the comms module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.comms import get_comms

SEP = "=" * 55

for icao in ["KSRQ", "KVNC"]:
    print(f"\n{SEP}")
    print(f"  COMMS: {icao}")
    print(f"{SEP}")

    c = get_comms(icao)

    if c["remarks"]:
        for r in c["remarks"]:
            print(f"  NOTE: {r}")

    if c["has_tower"]:
        print(f"  Towered airport")
    else:
        print(f"  Non-towered airport")

    if c["atis"]:
        print(f"  ATIS        : {c['atis']}")
    if c["clearance"]:
        print(f"  Clearance   : {c['clearance']}")
    if c["tower"]:
        print(f"  Tower       : {c['tower']}")
    if c["ground"]:
        print(f"  Ground      : {c['ground']}")
    if c["unicom"]:
        print(f"  UNICOM      : {c['unicom']}")
    if c["ctaf"]:
        print(f"  CTAF        : {c['ctaf']}")

    if c["approach"]:
        print(f"  Approach/Dep:")
        seen = set()
        for a in c["approach"]:
            key = (a["freq"], a["use_code"])
            if key not in seen:
                print(f"    {a['freq']:10s}  {a['use_code']}")
                seen.add(key)

    if not any([c["atis"], c["tower"], c["ground"], c["unicom"], c["ctaf"], c["approach"]]):
        print("  No frequency data found.")

print(f"\n{SEP}\n")
