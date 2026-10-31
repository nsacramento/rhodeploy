"""
Rho — In-Flight Guide (retired).

The In-Flight Guide and the Pre-Flight Kneeboard were merged into a single
document: see kneeboard.generate_kneeboard(). This shim keeps any old
imports of generate_cheatsheet working.
"""

from rho.modules.kneeboard import generate_kneeboard


def generate_cheatsheet(brief, comms_o, comms_d, aircraft=None,
                        tail_number=None, flight_rules="VFR"):
    return generate_kneeboard(brief, comms_o, comms_d, aircraft=aircraft,
                              tail_number=tail_number, flight_rules=flight_rules)
