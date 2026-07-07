"""Quick smoke test for the NOTAMs module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.notams import get_notams

notams = get_notams("KSRQ")

print(f"\n{'='*55}")
print(f"  NOTAMs for KSRQ ({len(notams)} found)")
print(f"{'='*55}")

if not notams:
    print("  No active NOTAMs.")
else:
    for n in notams[:10]:
        print(f"\n  [{n['number']}]")
        print(f"  Effective : {n['effective_utc']}")
        print(f"  Expires   : {n['expires_utc']}")
        print(f"  Text      : {(n['text'] or '')[:120]}")

print(f"\n{'='*55}\n")
