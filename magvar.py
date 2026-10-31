"""
Rho — magnetic variation from the World Magnetic Model (WMM 2025, valid 2025–2030).

    from rho.modules.magvar import mag_var_west
    var = mag_var_west(lat, lon)     # degrees WEST positive (MC = TC + var)

Uses pygeomag (pure Python, ships the NOAA WMM coefficients). If it's missing,
falls back to a coarse estimate and marks it via mag_var_source().
"""

from datetime import date as _date

try:
    from pygeomag import GeoMag
    _GM = GeoMag(coefficients_file="wmm/WMM_2025.COF")
except Exception:   # package missing or coefficients unavailable
    _GM = None


def _decimal_year(d=None):
    d = d or _date.today()
    start = _date(d.year, 1, 1)
    days = (_date(d.year + 1, 1, 1) - start).days
    return d.year + (d - start).days / days


def mag_var_west(lat, lon, alt_ft=0):
    """Magnetic variation in degrees, WEST positive (east negative). None if lat/lon missing."""
    if lat is None or lon is None:
        return None
    if _GM is not None:
        try:
            r = _GM.calculate(glat=float(lat), glon=float(lon), alt=float(alt_ft) * 0.0003048,
                              time=_decimal_year(), allow_date_outside_lifespan=True)
            return round(-r.d, 1)   # WMM declination is east-positive
        except Exception:
            pass
    # Coarse fallback (CONUS only, can be off by many degrees in the West)
    return round((lon + 80) * -0.4 + 5, 1)


def mag_var_source():
    return "WMM 2025" if _GM is not None else "estimate"
