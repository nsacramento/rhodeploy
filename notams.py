"""
Rho — NOTAMs module
Status: STUBBED — pending API access

The FAA migrated NOTAM distribution to the new NOTAM Management Service (NMS)
in 2025-2026. The old notams.aim.faa.gov/notamSearch/proxy endpoint is gone.

Access options (none are instant):
  - NMS API: email 7-AWA-NAIMES@faa.gov to request access
  - NASA DIP API: https://dip.amesaero.nasa.gov (under investigation)

In the meantime, check NOTAMs manually:
  - FAA NOTAM Search: https://notams.aim.faa.gov/notamSearch/
  - 1800wxbrief.com (standard pre-flight briefing)

TODO: Wire up live NOTAM fetch once API access is confirmed.
"""

NOTAM_SEARCH_URL = "https://notams.aim.faa.gov/notamSearch/"


def get_notams(icao, radius_nm=10):
    """
    Fetch active NOTAMs for a given ICAO identifier.

    NOTE: Currently stubbed — returns empty list with a manual-check reminder.
    Will be wired to live API once FAA NMS access is confirmed.
    """
    print(
        f"[Rho] NOTAMs not yet wired up. "
        f"Check manually: {NOTAM_SEARCH_URL}?searchType=0&designatorForIcao={icao}"
    )
    return []
