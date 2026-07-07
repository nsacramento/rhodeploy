"""Quick smoke test for the weather module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.weather import get_weather_brief

brief = get_weather_brief("KSRQ")

# ── METAR ──
m = brief["metar"]
print(f"\n{'='*50}")
print("  METAR")
print(f"{'='*50}")
if m:
    print(f"  Raw      : {m['raw']}")
    print(f"  Category : {m['flight_category']}")
    print(f"  Wind     : {m['wind_dir']}° @ {m['wind_kt']}kt")
    print(f"  Vis      : {m['visibility']} SM")
    print(f"  Temp/Dew : {m['temp_c']}°C / {m['dewpoint_c']}°C")
    print(f"  Altimeter: {m['altimeter']} hPa")
    for c in m['clouds']:
        print(f"  Clouds   : {c['cover']} @ {c['base']} ft")
else:
    print("  No METAR available.")

# ── TAF ──
t = brief["taf"]
print(f"\n{'='*50}")
print("  TAF")
print(f"{'='*50}")
if t:
    print(f"  Issued   : {t['issued_utc']}")
    print(f"  Valid    : {t['valid_from_utc']} → {t['valid_to_utc']}")
    for i, f in enumerate(t['forecasts']):
        label = f['change_type'] or ("Initial" if i == 0 else "FM")
        clouds = ", ".join(f"{c['cover']}@{c['base']}ft" for c in f['clouds'])
        print(f"  {label:8s} {f['valid_from_utc']}  Wind {f['wind_dir']}°@{f['wind_kt']}kt  Vis {f['visibility']}SM  {clouds}")
else:
    print("  No TAF available.")

# ── PIREPs ──
print(f"\n{'='*50}")
print(f"  PIREPs within 100nm")
print(f"{'='*50}")
pireps = brief["pireps"]
if pireps:
    for p in pireps[:5]:
        print(f"  {p['raw']}")
else:
    print("  No PIREPs in area.")

# ── SIGMETs ──
print(f"\n{'='*50}")
print(f"  Active SIGMETs")
print(f"{'='*50}")
sigmets = brief["sigmets"]
if sigmets:
    for s in sigmets[:3]:
        print(f"  {s['hazard']} — valid through {s['valid_to_utc']}")
else:
    print("  No active SIGMETs.")

# ── G-AIRMETs ──
print(f"\n{'='*50}")
print(f"  Active G-AIRMETs (CONUS)")
print(f"{'='*50}")
gairmets = brief["gairmets"]
if gairmets:
    seen = set()
    for g in gairmets:
        key = f"{g['product']} {g['hazard']}"
        if key not in seen:
            sev = f" ({g['severity']})" if g['severity'] else ""
            print(f"  {g['product']:6s} {g['hazard']}{sev} — expires {g['expire_utc']}")
            seen.add(key)
else:
    print("  No active G-AIRMETs.")

print(f"\n{'='*50}\n")
