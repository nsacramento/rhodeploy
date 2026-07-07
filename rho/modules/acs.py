"""
Rho — ACS (Airman Certification Standards) skills module
Tracks student pilot proficiency against FAA Private Pilot ACS (PAR-ACS-9).

Rating scale (per flight):
    1 — 🔴  Below standard   (attempted but did not meet ACS standard)
    2 — 🟡  Needs work       (marginal; approaching standard)
    3 — 🟢  Met standard     (performed to ACS standard for this flight)

Skills are logged per flight. The matrix view shows one column per flight,
allowing progress over time to be tracked visually. Overall score is derived
from the most recent rating for each task.

Table: skill_log
    id            UUID (auto)
    created_at    TIMESTAMPTZ (auto)
    user_id       UUID — from auth.uid() via Supabase RLS
    acs_task_id   TEXT — e.g. 'IV-A'
    proficiency   INTEGER — 1/2/3 (see scale above)
    flight_log_id UUID — links to flight_log.id
    cfi_notes     TEXT — optional CFI comments
"""

from rho.modules.db import get_client

# ── ACS Task Definitions ──────────────────────────────────────────────────────
# Source: FAA Private Pilot ACS PAR-ACS-9

ACS_TASKS = {
    # ── Pre-Flight Knowledge ───────────────────────────────────────────────────
    "I-A":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Pilot Certs & Currency"},
    "I-B":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Aircraft Airworthiness (ARROW)"},
    "I-C":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Weather Assessment & Go/No-Go"},
    "I-D":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Cross-Country Planning"},
    "I-E":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Airspace Rules (B/C/D/E/G)"},
    "I-F":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Performance Calculations"},
    "I-G":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Aircraft Systems"},
    "I-H":    {"area": "I",    "area_name": "Pre-Flight Knowledge",         "name": "Human Factors & ADM"},

    # ── Pre-Flight Procedures ─────────────────────────────────────────────────
    "II-A":   {"area": "II",   "area_name": "Pre-Flight Procedures",        "name": "Walk-Around Inspection"},
    "II-B":   {"area": "II",   "area_name": "Pre-Flight Procedures",        "name": "Cockpit Setup & Checklist Use"},
    "II-C":   {"area": "II",   "area_name": "Pre-Flight Procedures",        "name": "Engine Start"},
    "II-D":   {"area": "II",   "area_name": "Pre-Flight Procedures",        "name": "Taxiing"},
    "II-E":   {"area": "II",   "area_name": "Pre-Flight Procedures",        "name": "Runway Signs, Markings & Lighting"},
    "II-F":   {"area": "II",   "area_name": "Pre-Flight Procedures",        "name": "Before-Takeoff Check (Run-Up)"},

    # ── Airport & Radio Operations ────────────────────────────────────────────
    "III-A":  {"area": "III",  "area_name": "Airport & Radio Operations",   "name": "Radio Comms, ATIS & Light Signals"},
    "III-B":  {"area": "III",  "area_name": "Airport & Radio Operations",   "name": "Traffic Pattern Entry & Departure"},

    # ── Takeoffs ──────────────────────────────────────────────────────────────
    "IV-A":   {"area": "IV",   "area_name": "Takeoffs",                     "name": "Normal Takeoff"},
    "IV-C":   {"area": "IV",   "area_name": "Takeoffs",                     "name": "Soft-Field Takeoff"},
    "IV-E":   {"area": "IV",   "area_name": "Takeoffs",                     "name": "Short-Field Takeoff"},
    "IV-G":   {"area": "IV",   "area_name": "Takeoffs",                     "name": "Crosswind Takeoff"},

    # ── Landings ─────────────────────────────────────────────────────────────
    "IV-B":   {"area": "IV",   "area_name": "Landings",                     "name": "Normal Landing"},
    "IV-D":   {"area": "IV",   "area_name": "Landings",                     "name": "Soft-Field Landing"},
    "IV-F":   {"area": "IV",   "area_name": "Landings",                     "name": "Short-Field Landing"},
    "IV-H":   {"area": "IV",   "area_name": "Landings",                     "name": "Forward Slip to Landing"},
    "IV-I":   {"area": "IV",   "area_name": "Landings",                     "name": "Go-Around / Rejected Landing"},

    # ── Maneuvers ────────────────────────────────────────────────────────────
    "V-A":    {"area": "V",    "area_name": "Maneuvers",                    "name": "Steep Turns (45° bank)"},
    "V-B":    {"area": "V",    "area_name": "Maneuvers",                    "name": "Ground Reference Maneuvers"},

    # ── Navigation ───────────────────────────────────────────────────────────
    "VI-A":   {"area": "VI",   "area_name": "Navigation",                   "name": "Pilotage & Dead Reckoning"},
    "VI-B":   {"area": "VI",   "area_name": "Navigation",                   "name": "VOR / GPS Navigation"},
    "VI-C":   {"area": "VI",   "area_name": "Navigation",                   "name": "Diversion to Alternate"},
    "VI-D":   {"area": "VI",   "area_name": "Navigation",                   "name": "Lost Procedures"},

    # ── Slow Flight & Stalls ──────────────────────────────────────────────────
    "VII-A":  {"area": "VII",  "area_name": "Slow Flight & Stalls",         "name": "Slow Flight"},
    "VII-B":  {"area": "VII",  "area_name": "Slow Flight & Stalls",         "name": "Power-Off Stall"},
    "VII-C":  {"area": "VII",  "area_name": "Slow Flight & Stalls",         "name": "Power-On Stall"},
    "VII-D":  {"area": "VII",  "area_name": "Slow Flight & Stalls",         "name": "Spin Awareness"},

    # ── Basic Instruments (Under Hood) ────────────────────────────────────────
    "VIII-A": {"area": "VIII", "area_name": "Basic Instruments (Hood)",     "name": "Straight-and-Level"},
    "VIII-B": {"area": "VIII", "area_name": "Basic Instruments (Hood)",     "name": "Climbs & Descents"},
    "VIII-C": {"area": "VIII", "area_name": "Basic Instruments (Hood)",     "name": "Turns to Headings"},
    "VIII-D": {"area": "VIII", "area_name": "Basic Instruments (Hood)",     "name": "Unusual Attitude Recovery"},
    "VIII-E": {"area": "VIII", "area_name": "Basic Instruments (Hood)",     "name": "Radio Nav Under Hood"},

    # ── Emergencies ──────────────────────────────────────────────────────────
    "IX-A":   {"area": "IX",   "area_name": "Emergencies",                  "name": "Emergency Descent"},
    "IX-B":   {"area": "IX",   "area_name": "Emergencies",                  "name": "Engine-Out Landing (Simulated)"},
    "IX-C":   {"area": "IX",   "area_name": "Emergencies",                  "name": "Systems & Equipment Failures"},
    "IX-D":   {"area": "IX",   "area_name": "Emergencies",                  "name": "Emergency Equipment & Survival"},

    # ── Night Operations ─────────────────────────────────────────────────────
    "X-A":    {"area": "X",    "area_name": "Night Operations",             "name": "Night Preflight & Flight"},

    # ── Post-Flight ──────────────────────────────────────────────────────────
    "XI-A":   {"area": "XI",   "area_name": "Post-Flight",                  "name": "Parking, Securing & Post-Flight"},
}

RATING_LABELS = {
    1: "Below standard",
    2: "Needs work",
    3: "Met ACS standard",
}

RATING_ICONS = {
    1: "🔴",
    2: "🟡",
    3: "🟢",
}

# Condition → ACS tasks + minimum rating required (for skill-aware go/no-go)
CONDITION_SKILL_MAP = [
    ("high_crosswind", 2, ["IV-G"],           "Crosswind {xw:.0f} kt — Crosswind T/O & Landing not yet practiced"),
    ("night",          2, ["X-A"],            "Night flight — Night Preparation not yet practiced"),
    ("mvfr_ceiling",   2, ["VIII-A","VIII-B"],"MVFR ceiling — Basic Instrument Maneuvers not yet practiced"),
    ("cross_country",  2, ["VI-A","VI-B"],    "Cross-country — Navigation skills not yet practiced"),
    ("emergency_ops",  1, ["IX-B"],           "Always verify Emergency Approach procedures are introduced"),
]


# ── Log skills for a flight ───────────────────────────────────────────────────

def log_flight_skills(flight_id, ratings, user_id=None):
    """
    Log multiple skill ratings for a single flight.

    flight_id : UUID string linking to flights.id
    ratings   : dict { acs_task_id: rating }
                rating must be 1 (red), 2 (yellow), or 3 (green)
                tasks not included are treated as "not practiced" (blank)
    user_id   : current user UUID from auth.get_user_id()

    Returns list of saved records.
    """
    results = []
    client  = get_client()
    for task_id, rating in ratings.items():
        if task_id not in ACS_TASKS:
            continue
        if rating not in (1, 2, 3):
            continue
        record = {
            "acs_task_id": task_id,
            "proficiency": rating,
            "flight_id":   flight_id,
        }
        if user_id:
            record["user_id"] = user_id
        resp = client.table("skill_log").insert(record).execute()
        if resp.data:
            results.append(resp.data[0])
    return results


def log_skill(acs_task_id, proficiency, flight_id=None, cfi_notes=None, user_id=None):
    """
    Log a single proficiency entry for an ACS task.

    acs_task_id : task identifier, e.g. 'IV-G'
    proficiency : 1 (red/below standard), 2 (yellow/needs work), 3 (green/met standard)
    flight_id   : optional UUID linking to flights.id
    cfi_notes   : optional CFI comments
    user_id     : current user UUID from auth.get_user_id()
    """
    if acs_task_id not in ACS_TASKS:
        raise ValueError(f"Unknown ACS task: {acs_task_id}")
    if proficiency not in (1, 2, 3):
        raise ValueError(f"Rating must be 1, 2, or 3 — got: {proficiency}")

    record = {"acs_task_id": acs_task_id, "proficiency": proficiency}
    if flight_id:
        record["flight_id"] = flight_id
    if cfi_notes:
        record["cfi_notes"] = cfi_notes
    if user_id:
        record["user_id"] = user_id

    response = get_client().table("skill_log").insert(record).execute()
    if not response.data:
        raise RuntimeError(f"Supabase insert returned no data: {response}")
    return response.data[0]


# ── Flight skill matrix ───────────────────────────────────────────────────────

def get_flight_skill_matrix(limit=12):
    """
    Build a skill progress matrix indexed by flight × ACS task.

    Returns a dict with:
        flights        : list of completed flight dicts, newest-first
        by_flight      : { flight_id: { task_id: {rating, label, notes} } }
        latest_per_task: { task_id: rating | None }  — most recent rating per task
    """
    from rho.modules.flights import get_flights

    flights = get_flights(limit=limit, status="completed")
    if not flights:
        return {"flights": [], "by_flight": {}, "latest_per_task": {}}

    flight_ids = [f["id"] for f in flights]

    # Fetch skill_log entries for these flights (new flight_id column)
    resp = (
        get_client().table("skill_log")
        .select("*")
        .in_("flight_id", flight_ids)
        .order("created_at", desc=True)
        .execute()
    )
    entries = resp.data or []

    # Group by flight — keep most recent entry per task per flight
    by_flight = {fid: {} for fid in flight_ids}
    for entry in entries:
        fid  = entry.get("flight_id")
        tid  = entry.get("acs_task_id")
        rate = entry.get("proficiency")
        if fid in by_flight and tid and rate in (1, 2, 3):
            if tid not in by_flight[fid]:
                by_flight[fid][tid] = {
                    "rating": rate,
                    "label":  RATING_LABELS[rate],
                    "notes":  entry.get("cfi_notes"),
                    "log_id": entry.get("id"),
                }

    # Derive latest rating per task from the flights we already loaded.
    # flights list is newest-first, so first hit per task wins.
    # This avoids pulling in stale skill_log rows that have no flight_id.
    latest_per_task = {}
    for f in flights:
        for tid, entry in by_flight.get(f["id"], {}).items():
            if tid not in latest_per_task:
                latest_per_task[tid] = entry["rating"]

    return {
        "flights":         flights,
        "by_flight":       by_flight,
        "latest_per_task": latest_per_task,
    }


# ── Summary / readiness ───────────────────────────────────────────────────────

def get_readiness_summary(latest_per_task=None):
    """
    Return checkride readiness stats based on latest rating per task.
    Accepts a latest_per_task dict or fetches from Supabase if not provided.
    """
    if latest_per_task is None:
        matrix = get_flight_skill_matrix(limit=50)
        latest_per_task = matrix["latest_per_task"]

    total = len(ACS_TASKS)
    counts = {1: 0, 2: 0, 3: 0, None: 0}
    for task_id in ACS_TASKS:
        rating = latest_per_task.get(task_id)
        counts[rating if rating in (1, 2, 3) else None] += 1

    green  = counts[3]
    yellow = counts[2]
    red    = counts[1]
    blank  = counts[None]
    pct    = round(100 * green / total)

    return {
        "green":  green,
        "yellow": yellow,
        "red":    red,
        "blank":  blank,
        "total":  total,
        "pct":    pct,
        "summary": (
            f"🟢 {green} at standard  🟡 {yellow} in progress  "
            f"🔴 {red} below standard  ⬜ {blank} not yet practiced  "
            f"| Checkride readiness: {pct}%"
        ),
    }


def get_training_plan(latest_per_task=None):
    """
    Prioritised training plan based on skill gaps.
    Returns list sorted by priority: {task_id, name, area_name, rating, priority, reason}
    """
    if latest_per_task is None:
        matrix = get_flight_skill_matrix(limit=50)
        latest_per_task = matrix["latest_per_task"]

    high_priority = {
        "IX-B", "IX-A", "IX-C",
        "IV-A", "IV-B", "IV-I",
        "VII-B", "VII-C",
        "VIII-D",
    }

    plan = []
    for task_id, task in ACS_TASKS.items():
        rating = latest_per_task.get(task_id)
        if rating == 3:
            continue  # Already at standard — skip

        if rating is None:
            priority = 1 if task_id in high_priority else 2
            reason   = "Not yet practiced"
        elif rating == 1:
            priority = 1 if task_id in high_priority else 2
            reason   = "Below standard — needs focused work"
        else:  # rating == 2
            priority = 2 if task_id in high_priority else 3
            reason   = "In progress — working toward ACS standard"

        plan.append({
            "task_id":   task_id,
            "name":      task["name"],
            "area_name": task["area_name"],
            "rating":    rating,
            "icon":      RATING_ICONS.get(rating, "⬜"),
            "priority":  priority,
            "reason":    reason,
        })

    plan.sort(key=lambda x: (x["priority"], x["task_id"]))
    return plan


# ── Skill-aware go/no-go warnings ────────────────────────────────────────────

def get_skill_warnings(brief, latest_per_task=None):
    """
    Compare flight conditions against pilot skill level.
    Returns warning strings where conditions exceed demonstrated skills.

    brief           : dict from insights.get_preflight_brief()
    latest_per_task : optional pre-fetched {task_id: rating} dict
    """
    if latest_per_task is None:
        matrix = get_flight_skill_matrix(limit=50)
        latest_per_task = matrix["latest_per_task"]

    o = brief.get("origin_assess") or {}
    d = brief.get("dest_assess") or {}

    conditions = {
        "high_crosswind": (o.get("crosswind_kt") or 0) > 8,
        "night":          False,
        "mvfr_ceiling":   o.get("category") == "MVFR" or d.get("category") == "MVFR",
        "cross_country":  _is_cross_country(brief),
        "emergency_ops":  True,
    }

    warnings = []
    for cond_key, threshold, task_ids, template in CONDITION_SKILL_MAP:
        if not conditions.get(cond_key):
            continue
        for tid in task_ids:
            rating = latest_per_task.get(tid)
            if (rating is None) or (rating < threshold):
                xw = o.get("crosswind_kt") or 0
                try:
                    msg = template.format(xw=xw)
                except Exception:
                    msg = template
                warnings.append(f"[SKILL] {msg}")
                break

    return warnings


def _is_cross_country(brief):
    route = brief.get("route")
    if not route:
        return False
    dist = (route.get("direct") or {}).get("distance_nm", 0)
    return dist >= 50
