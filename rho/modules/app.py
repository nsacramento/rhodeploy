"""
Rho — Student Pilot Co-Pilot
Streamlit V1 web application

Run with: streamlit run app.py
"""

import streamlit as st
import pandas as pd
import os
import sys
import io
from datetime import datetime as _dt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
sys.path.insert(0, ".")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Rho — Student Pilot Co-Pilot",
    page_icon="✈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global styles ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="collapsedControl"] { display: none; }

/* Nav bar */
.nav-bar { display: flex; gap: 4px; margin-bottom: 1rem; border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }

/* Section headers */
h2, h3 { color: #1a1a2e; font-weight: 600; }

/* Metric cards */
[data-testid="metric-container"] {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 0.75rem 1rem;
}

/* Active flight banner */
.active-flight-banner {
    background: #1e40af;
    color: white;
    padding: 0.6rem 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
    font-weight: 500;
}

/* Table */
table { border-collapse: collapse; width: 100%; font-size: 12px; font-family: 'Inter', sans-serif; }
th { background: #1a1a2e; color: white; padding: 6px 8px; text-align: center; font-weight: 500; }
th.task-col { text-align: left; }
td { padding: 4px 6px; border-bottom: 1px solid #f0f0f0; }
td.task-cell { font-size: 11px; max-width: 220px; }
tr.area-header td { background: #f1f5f9; font-weight: 600; font-size: 11px; color: #475569; padding: 6px 8px; }
td.cell-green { background: #dcfce7; color: #166534; text-align: center; font-weight: 600; }
td.cell-yellow { background: #fef9c3; color: #854d0e; text-align: center; font-weight: 600; }
td.cell-red { background: #fee2e2; color: #991b1b; text-align: center; font-weight: 600; }
td.cell-blank { background: #f8fafc; color: #cbd5e1; text-align: center; }
td.cell-total-green { background: #16a34a; color: white; text-align: center; font-weight: 700; }
td.cell-total-yellow { background: #ca8a04; color: white; text-align: center; font-weight: 700; }
td.cell-total-red { background: #dc2626; color: white; text-align: center; font-weight: 700; }
td.cell-total-blank { background: #e2e8f0; color: #94a3b8; text-align: center; }
</style>
""", unsafe_allow_html=True)

# ── Module imports ────────────────────────────────────────────────────────────
from rho.modules.auth       import sign_in, sign_up, sign_out, get_user_id
from rho.modules.insights   import get_preflight_brief, _derive_category, _format_sky
from rho.modules.comms      import get_comms
from rho.modules.kneeboard  import generate_kneeboard
from rho.modules.cheatsheet import generate_cheatsheet
from rho.modules.flights  import (
    create_flight, complete_flight, create_manual_flight,
    delete_flight, get_active_flights, get_flights, get_flight, get_progress,
    REQUIREMENTS, LABELS,
)
from rho.modules.acs import (
    log_flight_skills, get_flight_skill_matrix,
    get_training_plan, get_readiness_summary, get_skill_warnings,
    ACS_TASKS, RATING_LABELS,
)
from rho.modules.airport import get_airports_by_state
from rho.modules.profile import (
    create_or_update_profile, get_profile,
    get_my_students, get_my_instructor, get_pending_invites,
)
from rho.modules.instructor import (
    create_invite, accept_invite,
    get_student_flights, get_student_skill_log,
    save_instructor_ratings, get_instructor_ratings,
    get_all_student_ratings,
)
from rho.modules.aircraft import (
    AIRCRAFT_OPTIONS, AIRCRAFT_DISPLAY,
    get_aircraft, vspeeds_summary, fuel_endurance_hrs, max_range_nm,
)

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [
    ("authenticated",         False),
    ("user_email",            None),
    ("user_role",             None),   # "student" | "instructor"
    ("user_name",             None),
    ("current_page",          "home"),
    ("last_brief",            None),
    ("pending_skills_flight", None),   # flight_id waiting for skill log after completion
    ("acs_editing_flight",    None),   # flight_id currently open in the inline ACS editor
    ("instr_student_id",      None),   # instructor dashboard: selected student
    ("generated_invite_link", None),   # persisted invite link so it survives reruns
    ("aircraft_type",         None),   # default aircraft type key (e.g. 'c172s')
    ("aircraft_tail",         None),   # default tail number (e.g. 'N12345')
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── US States ─────────────────────────────────────────────────────────────────
US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
    "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
    "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
    "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
]

ACS_TASK_DESCRIPTIONS = {
    "I-A":    "Pilot Qualifications — certificates, medical, currency requirements (61.3, 61.56, 61.57)",
    "I-B":    "Airworthiness — annual, 100-hr, ADs, equipment list, weight & balance",
    "I-C":    "Weather — METARs, TAFs, PIREPs, SIGMETs, G-AIRMETs, winds aloft, go/no-go decision",
    "I-D":    "Cross-Country Planning — sectional chart, VFR flight plan, fuel, alternates, TFRs",
    "I-E":    "National Airspace System — Class A/B/C/D/E/G rules, MOAs, restricted areas, TFRs",
    "I-F":    "Performance & Limitations — POH, density altitude, weight & balance, takeoff/landing distance",
    "I-G":    "Operation of Systems — engine, fuel, electrical, pitot-static, flight controls, avionics",
    "I-H":    "Human Factors — IMSAFE, hazardous attitudes, ADM, risk management",
    "II-A":   "Preflight Assessment — walk-around, oil, fuel quantity/quality, sumping, control check",
    "II-B":   "Flight Deck Management — checklist discipline, seat/rudder adjustment, passenger briefing",
    "II-C":   "Engine Starting — mixture, primer, start procedure, after-start checks",
    "II-D":   "Taxiing — throttle, brakes, heading, wind correction, speed control",
    "II-E":   "Taxiway Signs, Markings, Lighting — hold short lines, runway markings, incursion avoidance",
    "II-F":   "Before Takeoff Check — run-up: magnetos, carb heat, controls, instruments, abort criteria",
    "III-A":  "Communications & Lighting — radio procedures, light gun signals, CTAF, ATIS, clearances",
    "III-B":  "Traffic Patterns — entry/exit, rectangular course, wind correction, sequencing",
    "IV-A":   "Normal Takeoff & Climb — rotation speed, Vx vs Vy, crosswind correction, obstacle clearance",
    "IV-B":   "Normal Approach & Landing — VASI/PAPI, stabilised approach, flare, touchdown, rollout",
    "IV-C":   "Soft-Field Takeoff — full back pressure, ground effect, accelerate to Vx/Vy",
    "IV-D":   "Soft-Field Approach & Landing — flat attitude, nose high, minimum roll",
    "IV-E":   "Short-Field Takeoff — max performance climb, obstacle clearance speed",
    "IV-F":   "Short-Field Approach & Landing — precise airspeed, threshold crossing, spot landing",
    "IV-G":   "Crosswind Takeoff & Landing — crab vs sideslip, upwind main first, max demonstrated",
    "IV-H":   "Forward Slip to Landing — full rudder/opposite aileron, steepen descent, no flap awareness",
    "IV-I":   "Go-Around / Rejected Landing — full power, carb heat off, flap retraction sequence, Vx/Vy",
    "V-A":    "Steep Turns — 45° bank, altitude ±100 ft, airspeed ±10 kt, rollout on heading",
    "V-B":    "Ground Reference Maneuvers — rectangular course, S-turns, turns around a point; wind drift correction",
    "VI-A":   "Pilotage & Dead Reckoning — chart reading, checkpoints, estimated vs actual time/fuel",
    "VI-B":   "Navigation Systems & Radar — VOR, GPS, ATC radar services, flight following",
    "VI-C":   "Diversion — unexpected weather/fuel/ATC, pick alternate, new heading/time/fuel, notify ATC",
    "VI-D":   "Lost Procedures — maintain VFR, landmark ID, ATC assist, transponder 7700",
    "VII-A":  "Slow Flight — Vs+5–10 kt, all configurations, coordinated turns, stall recognition",
    "VII-B":  "Power-Off Stalls — approach config, buffet recognition, recovery with minimal altitude loss",
    "VII-C":  "Power-On Stalls — departure config, full power, recovery, no secondary stall",
    "VII-D":  "Spin Awareness — aerodynamics, incipient phase recognition, PARE recovery (no spin required)",
    "VIII-A": "Straight-and-Level (Instruments) — attitude + power, scan technique, ±10° heading, ±100 ft",
    "VIII-B": "Climbs & Descents (Instruments) — constant airspeed, level-off at altitude ±100 ft",
    "VIII-C": "Turns to Headings (Instruments) — standard rate, rollout ±10°, coordination",
    "VIII-D": "Unusual Attitudes (Instruments) — nose high: power, lower nose, wings level; nose low: power, wings, pull",
    "VIII-E": "Radio Nav & Radar (Instruments) — VOR intercept/track, ATC services under IMC-simulated",
    "IX-A":   "Emergency Descent — max-performance descent, clearing turns, Vne awareness",
    "IX-B":   "Emergency Landing (Simulated) — best glide, field selection, ABCDE checklist, pattern, mayday",
    "IX-C":   "Systems & Equipment Malfunctions — partial panel, vacuum failure, electrical, carb ice, rough engine",
    "IX-D":   "Emergency Equipment & Survival — ELT, life vest, first aid, survival kit knowledge",
    "X-A":    "Night Preparation — lighting, dark adaptation, night illusions, night currency requirements",
    "XI-A":   "After Landing, Parking & Securing — runway exit, taxi, shutdown, tie-down, chocks, logbook",
}

@st.cache_data(ttl=3600)
def cached_airports_by_state(state_code):
    return get_airports_by_state(state_code)


def airport_selector(label_state, label_airport, key_state, key_apt,
                     default_state="FL", default_icao=None):
    """Render a state → airport cascading selector. Returns selected ICAO string."""
    idx = US_STATES.index(default_state) if default_state in US_STATES else 0
    state = st.selectbox(label_state, US_STATES, index=idx, key=key_state)
    try:
        airports = cached_airports_by_state(state)
    except Exception as e:
        st.warning(f"Airport list unavailable: {e}")
        airports = []

    if airports:
        opts = {a["display"]: a["icao"] for a in airports}
        default_disp = next(
            (d for d, i in opts.items() if i == default_icao), list(opts.keys())[0]
        )
        sel = st.selectbox(label_airport, list(opts.keys()),
                           index=list(opts.keys()).index(default_disp), key=key_apt)
        return opts[sel]
    else:
        return st.text_input(label_airport, value=default_icao or "", key=key_apt).upper().strip()


# ── Auth ──────────────────────────────────────────────────────────────────────

def show_auth():
    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("## Rho")
        st.markdown("*Student Pilot Co-Pilot — KSRQ*")
        st.divider()
        tab_in, tab_up = st.tabs(["Sign In", "Create Account"])
        with tab_in:
            with st.form("signin"):
                email = st.text_input("Email")
                pw    = st.text_input("Password", type="password")
                if st.form_submit_button("Sign In", use_container_width=True):
                    try:
                        sign_in(email, pw)
                        st.session_state.authenticated = True
                        st.session_state.user_email    = email
                        # If arriving via an invite link, go straight to Profile to accept
                        if st.query_params.get("invite"):
                            st.session_state.current_page = "profile"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Sign-in failed: {e}")
        with tab_up:
            with st.form("signup"):
                email     = st.text_input("Email")
                pw        = st.text_input("Password (min 6 chars)", type="password")
                full_name = st.text_input("Full Name", placeholder="First Last")
                role      = st.selectbox("I am a …", ["student", "instructor"])
                if st.form_submit_button("Create Account", use_container_width=True):
                    try:
                        sign_up(email, pw)
                        sign_in(email, pw)
                        create_or_update_profile(full_name=full_name, role=role)
                        st.session_state.authenticated = True
                        st.session_state.user_email    = email
                        st.session_state.user_role     = role
                        st.session_state.user_name     = full_name
                        st.rerun()
                    except Exception as e:
                        st.error(f"Sign-up failed: {e}")


# ── Navigation ────────────────────────────────────────────────────────────────

def show_nav():
    # Lazy-load profile into session state once per session
    if st.session_state.user_role is None:
        try:
            prof = get_profile()
            if prof:
                st.session_state.user_role    = prof.get("role", "student")
                st.session_state.user_name    = prof.get("full_name") or st.session_state.user_email
                st.session_state.aircraft_type = prof.get("aircraft_type")
                st.session_state.aircraft_tail = prof.get("tail_number")
        except Exception:
            pass

    h_left, h_right = st.columns([6, 2])
    with h_left:
        name_display = st.session_state.user_name or st.session_state.user_email or "Pilot"
        st.markdown(f"### Rho — {name_display}")
    with h_right:
        role_badge = st.session_state.user_role or "student"
        st.caption(f"{st.session_state.user_email}  ·  {role_badge}")
        if st.button("Sign Out", key="signout", use_container_width=True):
            sign_out()
            for k in ("authenticated", "user_email", "user_role", "user_name",
                      "last_brief", "pending_skills_flight", "instr_student_id",
                      "aircraft_type", "aircraft_tail"):
                st.session_state[k] = False if k == "authenticated" else None
            st.rerun()

    pages = [
        ("Home",             "home"),
        ("Pre-Flight Brief", "preflight"),
        ("Flight Log",       "logbook"),
        ("ACS Skills",       "skills"),
        ("Profile",          "profile"),
    ]
    if st.session_state.user_role == "instructor":
        pages.append(("Students", "instructor"))

    cols = st.columns(len(pages))
    for col, (label, key) in zip(cols, pages):
        with col:
            active = st.session_state.current_page == key
            if st.button(label, key=f"nav_{key}", use_container_width=True,
                         type="primary" if active else "secondary"):
                st.session_state.current_page = key
                st.rerun()

    # Profile missing banner (existing users pre-profile system)
    if st.session_state.user_role is None:
        col_pmsg, col_pbtn = st.columns([5, 1])
        with col_pmsg:
            st.warning("Profile not set up — add your name, role, and default aircraft.")
        with col_pbtn:
            if st.button("Set Up Profile", key="nav_profile_prompt"):
                st.session_state.current_page = "profile"
                st.rerun()

    # Active flight banner
    try:
        active_flights = get_active_flights()
    except Exception:
        active_flights = []

    if active_flights:
        f = active_flights[0]
        col_msg, col_btn = st.columns([5, 1])
        with col_msg:
            st.info(
                f"Active flight in progress: **{f['origin']} → {f['destination']}** "
                f"(planned {f.get('planned_date', '')})"
            )
        with col_btn:
            if st.button("Complete Log", key="banner_complete", use_container_width=True):
                st.session_state.current_page = "logbook"
                st.rerun()

    st.divider()
    return st.session_state.current_page


# ── Dashboard / Home ──────────────────────────────────────────────────────────

def page_home():
    name_str = st.session_state.user_name or st.session_state.user_email or "Pilot"
    st.header(f"Welcome back, {name_str}")

    # Aircraft badge
    ac_key  = st.session_state.get("aircraft_type")
    ac_tail = st.session_state.get("aircraft_tail")
    if ac_key:
        ac = get_aircraft(ac_key)
        if ac:
            tail_str = f" — {ac_tail}" if ac_tail else ""
            st.caption(f"✈  {ac['display']}{tail_str}")

    st.divider()

    # ── Part 61 flight hours ──────────────────────────────────────────────────
    try:
        prog      = get_progress()
        total_hrs = prog["logged"].get("total_hours", 0)
        solo_hrs  = prog["logged"].get("solo_hours", 0)
        dual_hrs  = prog["logged"].get("dual_hours", 0)
        met_count = sum(1 for p in prog["progress"].values() if p["met"])
        total_req = len(prog["progress"])
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            pct_t = min(total_hrs / 40.0, 1.0)
            st.metric("Total Hours", f"{total_hrs:.1f} / 40")
            st.progress(pct_t)
        with c2:
            pct_s = min(solo_hrs / 10.0, 1.0)
            st.metric("Solo Hours", f"{solo_hrs:.1f} / 10")
            st.progress(pct_s)
        with c3:
            pct_d = min(dual_hrs / 20.0, 1.0)
            st.metric("Dual Hours", f"{dual_hrs:.1f} / 20")
            st.progress(pct_d)
        with c4:
            st.metric("Requirements Met", f"{met_count} / {total_req}")
    except Exception:
        pass

    # ── ACS checkride readiness ───────────────────────────────────────────────
    try:
        readiness = get_readiness_summary()
        pct   = readiness["pct"]
        green = readiness["green"]
        total = readiness["total"]
        st.markdown(
            f"**ACS Checkride Readiness: {pct}%** "
            f"— {green} of {total} tasks at standard"
        )
        st.progress(pct / 100)
    except Exception:
        pass

    st.divider()

    # ── Two-column: recent flights + training priorities ───────────────────────
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.subheader("Recent Flights")
        try:
            recent = get_flights(limit=5, status="completed")
        except Exception:
            recent = []
        if recent:
            for f in recent:
                h, m    = divmod(f.get("duration_min") or 0, 60)
                ac_str  = ""
                if f.get("tail_number"):
                    ac_str = f" · {f['tail_number']}"
                elif f.get("aircraft_type"):
                    ac_str = " · " + AIRCRAFT_DISPLAY.get(f.get("aircraft_type", ""), "")
                st.markdown(
                    f"**{f.get('flight_date', '—')}** &nbsp; "
                    f"{f['origin']} → {f['destination']} "
                    f"— {h}h {m:02d}m{ac_str}"
                )
        else:
            st.caption("No completed flights yet.")
        if st.button("Go to Flight Log →", key="dash_goto_log"):
            st.session_state.current_page = "logbook"
            st.rerun()

    with col_right:
        st.subheader("Training Priorities")
        try:
            plan = get_training_plan()
        except Exception:
            plan = []
        if plan:
            for item in plan[:5]:
                badge_clr = {3: "#16a34a", 2: "#d97706", 1: "#dc2626"}.get(
                    item.get("rating"), "#94a3b8"
                )
                rating_lbl = {3: "G", 2: "Y", 1: "R"}.get(item.get("rating"), "·")
                st.markdown(
                    f"<span style='background:{badge_clr};color:white;padding:1px 5px;"
                    f"border-radius:3px;font-size:11px;font-weight:700;'>{rating_lbl}</span>"
                    f" <b>{item['task_id']}</b> {item['name']}",
                    unsafe_allow_html=True,
                )
        else:
            st.success("All tasks at standard — checkride ready!")
        if st.button("Go to ACS Skills →", key="dash_goto_skills"):
            st.session_state.current_page = "skills"
            st.rerun()

    st.divider()

    # ── Quick actions ─────────────────────────────────────────────────────────
    st.subheader("Quick Actions")
    qa1, qa2, qa3 = st.columns(3)
    with qa1:
        if st.button("📋  New Pre-Flight Brief", use_container_width=True, type="primary",
                     key="dash_goto_brief"):
            st.session_state.current_page = "preflight"
            st.rerun()
    with qa2:
        if st.button("📝  Log a Past Flight", use_container_width=True,
                     key="dash_goto_log2"):
            st.session_state.current_page = "logbook"
            st.rerun()
    with qa3:
        if st.button("👤  Profile / Aircraft", use_container_width=True,
                     key="dash_goto_profile"):
            st.session_state.current_page = "profile"
            st.rerun()


# ── Pre-Flight Brief ──────────────────────────────────────────────────────────

def page_preflight():
    st.header("Pre-Flight Brief")

    # Airport selectors
    cols = st.columns([1, 2, 1, 2, 1])
    with cols[0]:
        state_o = st.selectbox("Origin State", US_STATES,
                               index=US_STATES.index("FL"), key="pf_state_o")
    with cols[1]:
        try:
            apts_o = cached_airports_by_state(state_o)
        except Exception:
            apts_o = []
        if apts_o:
            opts_o = {a["display"]: a["icao"] for a in apts_o}
            def_o  = next((d for d, i in opts_o.items() if i == "KSRQ"), list(opts_o.keys())[0])
            origin = opts_o[st.selectbox("Origin", list(opts_o.keys()),
                                          index=list(opts_o.keys()).index(def_o), key="pf_apt_o")]
        else:
            origin = st.text_input("Origin ICAO", value="KSRQ", key="pf_apt_o").upper().strip()

    with cols[2]:
        state_d = st.selectbox("Dest State", US_STATES,
                               index=US_STATES.index("FL"), key="pf_state_d")
    with cols[3]:
        try:
            apts_d = cached_airports_by_state(state_d)
        except Exception:
            apts_d = []
        if apts_d:
            opts_d = {a["display"]: a["icao"] for a in apts_d}
            def_d  = next((d for d, i in opts_d.items() if i == "KVNC"), list(opts_d.keys())[0])
            dest   = opts_d[st.selectbox("Destination", list(opts_d.keys()),
                                          index=list(opts_d.keys()).index(def_d), key="pf_apt_d")]
        else:
            dest = st.text_input("Destination ICAO", value="KVNC", key="pf_apt_d").upper().strip()

    with cols[4]:
        alt = st.number_input("Cruise Alt (ft)", value=3500, step=500)

    # ── Aircraft (per-flight, profile default pre-fills) ──────────────────────
    ac_cols = st.columns([2, 1])
    with ac_cols[0]:
        ac_options_list = ["(none)"] + list(AIRCRAFT_OPTIONS.keys())
        default_ac_disp = AIRCRAFT_DISPLAY.get(st.session_state.get("aircraft_type") or "", "(none)")
        ac_idx = ac_options_list.index(default_ac_disp) if default_ac_disp in ac_options_list else 0
        ac_sel = st.selectbox("Aircraft Type", ac_options_list, index=ac_idx, key="pf_aircraft")
        pf_aircraft_key = AIRCRAFT_OPTIONS.get(ac_sel) if ac_sel != "(none)" else None
    with ac_cols[1]:
        pf_tail = st.text_input(
            "Tail Number",
            value=st.session_state.get("aircraft_tail") or "",
            placeholder="N12345",
            key="pf_tail",
        ).strip().upper() or None

    if st.button("Generate Brief", type="primary", use_container_width=True):
        with st.spinner("Fetching weather, airspace, and comms..."):
            try:
                brief          = get_preflight_brief(origin, dest, cruise_alt_ft=alt)
                skill_warnings = get_skill_warnings(brief)
                comms_o        = get_comms(origin)
                comms_d        = get_comms(dest)
                st.session_state.last_brief = {
                    "brief": brief, "skill_warnings": skill_warnings,
                    "comms_o": comms_o, "comms_d": comms_d,
                    "aircraft_key": pf_aircraft_key,
                    "tail_number":  pf_tail,
                }
            except Exception as e:
                st.error(f"Brief failed: {e}")
                return

    if st.session_state.last_brief:
        _render_brief(**st.session_state.last_brief)


def _route_map_image(brief):
    """
    Generate a route overview map as PNG bytes.
    Delegates to map_utils (contextily tiles + shapely polygons).
    Returns PNG bytes, or None if coordinates are unavailable.
    """
    origin_apt = brief.get("origin_apt") or {}
    dest_apt   = brief.get("dest_apt")   or {}
    o_lat = origin_apt.get("lat")
    o_lon = origin_apt.get("lon")
    d_lat = dest_apt.get("lat")
    d_lon = dest_apt.get("lon")
    if not all([o_lat, o_lon, d_lat, d_lon]):
        return None

    try:
        from rho.modules.map_utils import generate_route_map_png
        return generate_route_map_png(
            o_lat, o_lon, d_lat, d_lon,
            brief.get("origin_icao", "ORIG"),
            brief.get("dest_icao",   "DEST"),
            airspaces=brief.get("airspaces"),
            cruise_alt_ft=brief.get("cruise_alt_ft", 3500),
            width_in=9.0, height_in=6.0,
            dark=True,
        )
    except Exception:
        return None


def _fmt_ts(iso_str):
    """Format an ISO timestamp string to 'YYYY-MM-DD HH:MM UTC'."""
    if not iso_str:
        return None
    try:
        clean = str(iso_str).replace("Z", "+00:00")
        dt    = _dt.fromisoformat(clean)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(iso_str)[:16]


def _render_brief_snapshot(flight):
    """
    Render a compact historical brief from a completed flight record.
    Uses weather_snap / route_snap JSONB stored at brief creation time.
    """
    # Timestamp
    brief_at = flight.get("brief_at") or flight.get("created_at")
    if brief_at:
        st.caption(f"Brief generated: {_fmt_ts(brief_at)}")

    # Aircraft (at brief time)
    ac_type = flight.get("aircraft_type")
    ac_tail = flight.get("tail_number")
    if ac_type:
        ac = get_aircraft(ac_type)
        if ac:
            tail_str = f" ({ac_tail})" if ac_tail else ""
            st.caption(f"Aircraft: {ac['display']}{tail_str}  ·  {vspeeds_summary(ac)}")

    # Recommendation
    rec     = flight.get("recommendation", "—")
    reason  = flight.get("reason", "")
    rec_clr = {"GO": "#15803d", "CAUTION": "#92400e", "NO-GO": "#991b1b"}.get(rec, "#374151")
    st.markdown(
        f"<span style='background:{rec_clr};color:white;padding:2px 8px;"
        f"border-radius:4px;font-weight:700;font-size:0.9rem;'>{rec}</span>"
        f" &nbsp; {reason}",
        unsafe_allow_html=True,
    )

    # Weather snapshot
    wx     = flight.get("weather_snap") or {}
    origin = flight.get("origin", "?")
    dest   = flight.get("destination", "?")
    col_o, col_d = st.columns(2)
    for col, label, apt in [
        (col_o, origin, wx.get("origin")),
        (col_d, dest,   wx.get("destination")),
    ]:
        with col:
            if not apt:
                st.caption(f"{label}: no data")
                continue
            cat     = apt.get("category", "?")
            cat_clr = {"VFR": "#15803d", "MVFR": "#b45309",
                       "IFR": "#991b1b", "LIFR": "#7c1d6f"}.get(cat, "#374151")
            wd, wk  = apt.get("wind_dir"), apt.get("wind_kt")
            wind_s  = f"{wd:03d}° @ {wk} kt" if wd is not None and wk is not None else "—"
            ceil_s  = f"{apt['ceiling_ft']:,} ft AGL" if apt.get("ceiling_ft") else "Clear"
            vis_s   = f"{apt['visibility']} sm" if apt.get("visibility") is not None else "—"
            st.markdown(
                f"<b>{label}</b> &nbsp;"
                f"<span style='color:{cat_clr};font-weight:700;'>{cat}</span><br/>"
                f"<small>Winds {wind_s} &nbsp;·&nbsp; Ceil {ceil_s} &nbsp;·&nbsp; Vis {vis_s}</small>",
                unsafe_allow_html=True,
            )

    # Route snapshot
    route_snap = flight.get("route_snap") or {}
    dist = route_snap.get("distance_nm")
    pens = route_snap.get("airspace_penetrations") or []
    if dist:
        pen_note = f"  ·  {len(pens)} airspace crossing(s)" if pens else ""
        st.caption(f"Route: {dist} nm direct{pen_note}")

    # Hazards at brief time
    hazards = wx.get("hazards") or []
    if hazards:
        st.markdown("**Hazards at brief time:**")
        for h in hazards[:5]:
            st.caption(f"⚠ {h}")


def _render_brief(brief, skill_warnings, comms_o, comms_d, aircraft_key=None, tail_number=None):
    origin = brief["origin_icao"]
    dest   = brief["dest_icao"]
    rec    = brief["recommendation"]
    o      = brief["origin_assess"]
    d      = brief["dest_assess"]

    # Brief timestamp
    st.caption(f"Brief generated: {_dt.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

    # ── Go/No-Go banner ───────────────────────────────────────────────────────
    banner = {"GO": ("GO", "#15803d"), "CAUTION": ("CAUTION", "#92400e"), "NO-GO": ("NO-GO", "#991b1b")}
    label, color = banner.get(rec, ("UNKNOWN", "#374151"))
    st.markdown(
        f"<div style='background:{color};color:white;padding:0.75rem 1rem;"
        f"border-radius:6px;font-size:1.1rem;font-weight:700;margin-bottom:0.5rem;'>"
        f"{label} — {brief['reason']}</div>",
        unsafe_allow_html=True,
    )

    # ── Airport cards ─────────────────────────────────────────────────────────
    col_o, col_d = st.columns(2)
    for col, icao, assess, comms, wx in [
        (col_o, origin, o, comms_o, brief.get("origin_wx", {})),
        (col_d, dest,   d, comms_d, brief.get("dest_wx",   {})),
    ]:
        with col:
            cat      = assess["category"]
            cat_clr  = {"VFR": "#15803d", "MVFR": "#b45309", "IFR": "#991b1b", "LIFR": "#7c1d6f"}.get(cat, "#374151")
            trend    = assess.get("trend", "steady")
            trend_str = " — TAF deteriorating" if trend == "deteriorating" else (
                        " — TAF improving" if trend == "improving" else "")

            st.markdown(
                f"<div style='border:1px solid #e2e8f0;border-radius:8px;padding:0.75rem 1rem;'>"
                f"<div style='font-size:1rem;font-weight:700;margin-bottom:0.5rem;'>"
                f"{icao} &nbsp;<span style='color:{cat_clr};'>{cat}</span>"
                f"<span style='color:#6b7280;font-size:0.8rem;font-weight:400;'>{trend_str}</span></div>",
                unsafe_allow_html=True,
            )

            rows = []
            wd, wk = assess.get("wind_dir"), assess.get("wind_kt")
            if wd is not None and wk is not None:
                rows.append(("Winds", f"{wd:03d}&deg; @ {wk} kt"))
            if assess.get("best_runway"):
                xw = f" ({assess['crosswind_kt']:.0f} kt XW)" if assess.get("crosswind_kt") else ""
                rows.append(("Active Runway", f"{assess['best_runway']}{xw} — left traffic (verify A/FD)"))
            rows.append(("Sky", _decode_sky(assess.get("sky_conditions", ""))))
            if assess.get("ceiling_ft"):
                rows.append(("Ceiling", f"{assess['ceiling_ft']:,} ft AGL"))
            rows.append(("Visibility", f"{assess.get('visibility', 'N/A')} sm"))
            if assess.get("temp_c") is not None:
                spread = ""
                if assess.get("dewpoint_c") is not None:
                    spread = f" &nbsp;|&nbsp; Dewpoint {assess['dewpoint_c']}&deg;C"
                    t_d = round(assess["temp_c"] - assess["dewpoint_c"], 1)
                    spread += f" &nbsp;|&nbsp; T/D spread {t_d}&deg;C"
                rows.append(("Temp", f"{assess['temp_c']}&deg;C{spread}"))
            if assess.get("altimeter"):
                try:
                    rows.append(("Altimeter", f'{float(assess["altimeter"]):.2f}&#34; Hg'))
                except (ValueError, TypeError):
                    rows.append(("Altimeter", str(assess["altimeter"])))

            # Comms
            freq_parts = []
            if comms.get("atis"):   freq_parts.append(f"ATIS {comms['atis']}")
            if comms.get("tower"):  freq_parts.append(f"TWR {comms['tower']}")
            if comms.get("ground"): freq_parts.append(f"GND {comms['ground']}")
            if comms.get("unicom"): freq_parts.append(f"UNICOM {comms['unicom']}")
            if comms.get("ctaf"):   freq_parts.append(f"CTAF {comms['ctaf']}")
            if comms.get("approach"):
                seen = set()
                for a in comms["approach"]:
                    freq = (a.get("freq") or "").strip()
                    try:
                        freq_f = float(freq.split()[0].replace(";", ""))
                    except (ValueError, IndexError):
                        continue
                    if freq not in seen and freq_f < 136:
                        freq_parts.append(f"APP {freq.split()[0]}")
                        seen.add(freq)
                        break
            if freq_parts:
                rows.append(("Comms", " &nbsp;|&nbsp; ".join(freq_parts)))

            # Airport links
            rows.append(("Links", (
                f'<a href="https://skyvector.com/airport/{icao}" target="_blank">SkyVector</a>'
                f' &nbsp;|&nbsp; '
                f'<a href="https://www.airnav.com/airport/{icao}" target="_blank">AirNav</a>'
                f' &nbsp;|&nbsp; '
                f'<a href="https://www.1800wxbrief.com/Website/#!/" target="_blank">1800WxBrief</a>'
            )))

            table_html = "<table style='width:100%;font-size:11px;border-collapse:collapse;'>"
            for label_r, val in rows:
                table_html += (
                    f"<tr><td style='padding:2px 4px;color:#6b7280;white-space:nowrap;"
                    f"font-weight:500;width:110px;'>{label_r}</td>"
                    f"<td style='padding:2px 4px;'>{val}</td></tr>"
                )
            table_html += "</table>"

            st.markdown(table_html + "</div>", unsafe_allow_html=True)

            # Raw METAR with plain-English interpretation
            if assess.get("raw_metar"):
                with st.expander("Raw METAR"):
                    st.code(assess["raw_metar"])
                    st.caption(_interpret_metar(assess))

            # TAF — terminal area forecast
            taf = wx.get("taf")
            if taf:
                raw_taf = taf.get("raw") or ""
                forecasts = taf.get("forecasts") or []
                with st.expander("TAF"):
                    if raw_taf:
                        st.code(raw_taf)
                    if forecasts:
                        for fc in forecasts[:6]:
                            t_from = fc.get("time_from", "")
                            t_to   = fc.get("time_to", "")
                            fc_cat = _derive_category(
                                _ceiling_from_fc(fc),
                                _parse_vis_fc(fc),
                            )
                            fc_clr = {"VFR":"#15803d","MVFR":"#b45309","IFR":"#991b1b","LIFR":"#7c1d6f"}.get(fc_cat,"#374151")
                            wnd = ""
                            if fc.get("wind_kt"):
                                try:
                                    wd_i = int(fc.get("wind_dir") or 0)
                                    wnd = f"  winds {wd_i:03d}@{fc['wind_kt']}kt"
                                except (ValueError, TypeError):
                                    wnd = f"  winds VRB@{fc['wind_kt']}kt"
                            vis = f"  vis {fc.get('visibility','')}sm" if fc.get("visibility") else ""
                            sky = _format_sky(fc.get("clouds") or [])
                            st.markdown(
                                f"<span style='color:{fc_clr};font-weight:600;'>{fc_cat}</span>"
                                f" &nbsp;{t_from}–{t_to}{wnd}{vis}  {sky}",
                                unsafe_allow_html=True,
                            )

    # ── Winds Aloft ──────────────────────────────────────────────────────────
    winds_aloft = brief.get("winds_aloft")
    if winds_aloft:
        with st.expander("Winds Aloft", expanded=False):
            alts    = ["3000", "6000", "9000", "12000"]
            wa_rows = []
            for alt in alts:
                wa = winds_aloft.get(alt)
                if wa:
                    wa_rows.append((f"{int(alt):,} ft", wa.get("label", "—")))
            if wa_rows:
                wa_tbl = "<table style='width:100%;font-size:11px;border-collapse:collapse;'>"
                for lbl, val in wa_rows:
                    wa_tbl += (
                        f"<tr><td style='padding:2px 4px;color:#6b7280;white-space:nowrap;"
                        f"font-weight:500;width:90px;'>{lbl}</td>"
                        f"<td style='padding:2px 4px;'>{val}</td></tr>"
                    )
                wa_tbl += "</table>"
                st.markdown(wa_tbl, unsafe_allow_html=True)
            else:
                st.caption("Winds aloft data unavailable for this region.")

    # ── Aircraft ──────────────────────────────────────────────────────────────
    ac_key  = aircraft_key
    ac_tail = tail_number
    if ac_key:
        ac = get_aircraft(ac_key)
        if ac:
            tail_str  = f" — {ac_tail}" if ac_tail else ""
            ac_header = f"{ac['display']}{tail_str}"
            endurance = fuel_endurance_hrs(ac)
            rng       = max_range_nm(ac)
            ac_rows   = [
                ("V-speeds", vspeeds_summary(ac)),
                ("Weights",  f"{ac['max_gross_lbs']:,} lbs gross  |  {ac['useful_load_lbs']:,} lbs useful load"),
                ("Fuel",     f"{ac['fuel_usable_gal']} gal usable  |  {ac['fuel_burn_gph']} gph"),
            ]
            if endurance is not None:
                ac_rows.append(("Endurance", f"{endurance} hrs (5 gal reserve)"))
            if rng is not None:
                ac_rows.append(("Max Range", f"{rng} nm (5 gal reserve)"))
            with st.expander(f"Aircraft — {ac_header}", expanded=True):
                ac_tbl = "<table style='width:100%;font-size:11px;border-collapse:collapse;'>"
                for lbl, val in ac_rows:
                    ac_tbl += (
                        f"<tr><td style='padding:2px 4px;color:#6b7280;white-space:nowrap;"
                        f"font-weight:500;width:90px;'>{lbl}</td>"
                        f"<td style='padding:2px 4px;'>{val}</td></tr>"
                    )
                ac_tbl += "</table>"
                st.markdown(ac_tbl, unsafe_allow_html=True)
                st.caption("Verify V-speeds against your specific aircraft's POH before flight.")

    # ── Route ─────────────────────────────────────────────────────────────────
    route = brief.get("route")
    if route and route.get("direct"):
        dist = route["direct"].get("distance_nm")
        pens = route["direct"].get("airspace_penetrations", [])
        if dist:
            pen_str = f" | {len(pens)} airspace penetration(s)" if pens else " | No airspace conflicts at planned altitude"
            st.info(f"Direct route: **{dist} nm**{pen_str}")
        if pens:
            for p in pens:
                st.warning(
                    f"Class {p['class']} — {p['name']}  "
                    f"({p['lower']} – {p['upper']}) — you are inside this airspace at "
                    f"{brief.get('cruise_alt_ft', '?')} ft"
                )

    # ── Route map ─────────────────────────────────────────────────────────────
    try:
        map_png = _route_map_image(brief)
        if map_png:
            with st.expander("Route Overview Map", expanded=True):
                st.image(map_png, use_container_width=True)
                st.caption(
                    "Airspace shown: Class B (blue), C (purple), D (teal). "
                    "Filled polygons are actual FAA boundaries. "
                    "Only airspace whose vertical band includes your cruise altitude "
                    "is flagged as a penetration."
                )
    except Exception as _map_err:
        pass   # map is best-effort — don't break the brief if it fails

    # ── Hazards ───────────────────────────────────────────────────────────────
    all_hazards = (brief.get("hazards") or []) + skill_warnings
    if all_hazards:
        st.subheader("Hazards & Advisories")
        for w in all_hazards:
            st.warning(w)
    else:
        st.success("No significant hazards — standard VFR conditions")

    # ── SIGMETs (full text) ───────────────────────────────────────────────────
    sigmets = brief.get("sigmets") or []
    if sigmets:
        st.subheader("Active SIGMETs")
        for s in sigmets:
            hazard = s.get("hazard", "UNKNOWN")
            valid_f = s.get("valid_from_utc", "")
            valid_t = s.get("valid_to_utc", "")
            raw     = s.get("raw") or ""
            st.markdown(f"**{hazard}** &nbsp; valid {valid_f} – {valid_t}")
            if raw:
                st.code(raw, language=None)

    # ── Downloads ─────────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Flight Documents")
    dl_c1, dl_c2 = st.columns(2)

    with dl_c1:
        st.markdown("**In-Flight Guide** — take this with you. Comms, headings, airspace rules in crossing order.")
        try:
            cs_bytes = generate_cheatsheet(
                brief, comms_o, comms_d,
                aircraft=get_aircraft(aircraft_key),
            )
            st.download_button(
                label="Download In-Flight Guide (PDF)",
                data=cs_bytes,
                file_name=f"inflight_{origin}_{dest}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
        except Exception as e:
            st.error(f"Could not generate guide: {e}")

    with dl_c2:
        st.markdown("**Pre-Flight Kneeboard** — full brief summary, weather, checklist.")
        try:
            kb_bytes = generate_kneeboard(
                brief, comms_o, comms_d,
                aircraft=get_aircraft(aircraft_key),
            )
            st.download_button(
                label="Download Kneeboard (PDF)",
                data=kb_bytes,
                file_name=f"kneeboard_{origin}_{dest}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"Kneeboard unavailable: {e}")

    # ── Go / No-Go decision ───────────────────────────────────────────────────
    st.divider()
    st.subheader("Your Decision")
    notes = st.text_area("Pilot notes (optional)", key="brief_notes", height=80)

    col_go, col_nogo = st.columns(2)
    with col_go:
        if st.button("GO — Save and create flight log", type="primary",
                     use_container_width=True, key="btn_go"):
            try:
                uid    = get_user_id()
                flight = create_flight(
                    brief, status="in-progress",
                    pilot_notes=notes or None, user_id=uid,
                    aircraft_type=aircraft_key,
                    tail_number=tail_number,
                    brief_at=_dt.utcnow().isoformat(),
                )
                st.success(f"Flight created — {origin} to {dest}. Head to Flight Log after landing.")
                st.session_state.last_brief = None
            except Exception as e:
                st.error(f"Save failed: {e}")

    with col_nogo:
        if st.button("NO-GO — Archive brief only", use_container_width=True, key="btn_nogo"):
            try:
                uid = get_user_id()
                create_flight(
                    brief, status="no-go",
                    pilot_notes=notes or None, user_id=uid,
                    aircraft_type=aircraft_key,
                    tail_number=tail_number,
                    brief_at=_dt.utcnow().isoformat(),
                )
                st.info("No-Go decision saved.")
                st.session_state.last_brief = None
            except Exception as e:
                st.error(f"Save failed: {e}")


def _decode_sky(sky_str):
    """Convert METAR sky string 'FEW018 BKN065' to human-readable 'Few at 1,800 ft AGL · Broken at 6,500 ft AGL'."""
    if not sky_str or sky_str in ("CLR", "SKC", "CAVOK"):
        return "Clear"
    COVER = {"FEW": "Few", "SCT": "Scattered", "BKN": "Broken", "OVC": "Overcast", "VV": "Vert. vis."}
    parts = []
    for token in sky_str.split():
        code = token[:3]
        alt_str = token[3:6] if len(token) >= 6 else ""
        cover_full = COVER.get(code, code)
        try:
            alt_ft = int(alt_str) * 100
            parts.append(f"{cover_full} at {alt_ft:,} ft AGL")
        except (ValueError, TypeError):
            parts.append(cover_full)
    return " · ".join(parts) if parts else sky_str


def _interpret_metar(assess):
    """
    Plain-English decode of a METAR, in the order the fields appear:
    winds → visibility → sky → temp/dew → altimeter → flight category
    """
    parts = []

    # Winds
    wd = assess.get("wind_dir")
    wk = assess.get("wind_kt")
    if wd is not None and wk is not None:
        compass = _deg_to_compass(wd)
        parts.append(f"Wind from {wd:03d}° ({compass}) at {wk} knots.")
    elif wk == 0:
        parts.append("Wind calm.")

    # Visibility
    vis = assess.get("visibility")
    if vis is not None:
        if float(vis) >= 10:
            parts.append("Visibility 10 miles or more.")
        else:
            parts.append(f"Visibility {vis} statute miles.")

    # Sky / ceiling
    sky = assess.get("sky_conditions", "")
    if sky == "CLR" or not sky:
        parts.append("Sky clear.")
    else:
        layers = []
        for layer_str in sky.split():
            # e.g. "FEW018", "BKN065", "OVC010"
            cover = layer_str[:3]
            alt_code = layer_str[3:]
            cover_full = {"FEW": "few", "SCT": "scattered", "BKN": "broken", "OVC": "overcast"}.get(cover, cover)
            try:
                alt_ft = int(alt_code) * 100
                layers.append(f"{cover_full} clouds at {alt_ft:,} ft AGL")
            except ValueError:
                layers.append(f"{cover_full}")
        # Note ceiling (lowest BKN or OVC)
        ceiling = assess.get("ceiling_ft")
        sky_str = "; ".join(layers)
        if ceiling:
            sky_str += f" — ceiling {ceiling:,} ft"
        parts.append(f"Sky: {sky_str}.")

    # Temp / dewpoint
    tc = assess.get("temp_c")
    dc = assess.get("dewpoint_c")
    if tc is not None:
        tc_f = round(tc * 9 / 5 + 32)
        if dc is not None:
            dc_f = round(dc * 9 / 5 + 32)
            spread = round(tc - dc, 1)
            spread_note = (
                "spread very tight — fog or low cloud likely"
                if spread <= 2 else
                "spread narrow — monitor for fog"
                if spread <= 4 else
                "spread OK"
            )
            parts.append(
                f"Temperature {tc}°C ({tc_f}°F), dewpoint {dc}°C ({dc_f}°F) — "
                f"T/D spread {spread}°C ({spread_note})."
            )
        else:
            parts.append(f"Temperature {tc}°C ({tc_f}°F).")

    # Altimeter
    alt = assess.get("altimeter")
    if alt:
        parts.append(f'Altimeter {alt:.2f}" Hg -- set this in your Kollsman window before takeoff.')

    # Flight category summary
    cat = assess.get("category", "")
    cat_notes = {
        "VFR":  "Conditions are VFR (ceiling 3,000+ ft and visibility 5+ sm). Standard VFR flight permitted.",
        "MVFR": "Conditions are marginal VFR (ceiling 1,000–2,999 ft or visibility 3–4 sm). Student pilots should exercise caution.",
        "IFR":  "Conditions are IFR (ceiling below 1,000 ft or visibility below 3 sm). VFR flight not permitted.",
        "LIFR": "Conditions are Low IFR (ceiling below 500 ft or visibility below 1 sm). VFR flight not permitted.",
    }
    if cat in cat_notes:
        parts.append(cat_notes[cat])

    return " ".join(parts) if parts else "No decoded data available."


def _deg_to_compass(deg):
    """Convert degrees to 8-point compass label."""
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    return dirs[int((deg + 22.5) / 45) % 8]


def _ceiling_from_fc(forecast):
    """Extract ceiling from a TAF forecast period's cloud layers."""
    clouds = forecast.get("clouds") or []
    ceiling = None
    for layer in clouds:
        cover = layer.get("cover") or ""
        if cover in ("BKN", "OVC"):
            base = layer.get("base")
            if base is not None:
                ft = int(base)
                if ceiling is None or ft < ceiling:
                    ceiling = ft
    return ceiling


def _parse_vis_fc(forecast):
    """Extract visibility from a TAF forecast period."""
    vis = forecast.get("visibility")
    if vis is None:
        return None
    try:
        return float(str(vis).replace("+", ""))
    except ValueError:
        return None


# ── Flight Log (combined logbook + debrief) ───────────────────────────────────

def page_logbook():
    st.header("Flight Log")

    # ── Pending skills prompt ─────────────────────────────────────────────────
    if st.session_state.pending_skills_flight:
        fid = st.session_state.pending_skills_flight
        f   = get_flight(fid)
        if f:
            st.success(
                f"Flight completed: {f['origin']} to {f['destination']}. "
                f"Ready to log your ACS skills?"
            )
            col_yes, col_skip = st.columns(2)
            with col_yes:
                if st.button("Log Skills Now", type="primary", use_container_width=True):
                    # Keep pending_skills_flight — page_skills() will auto-enter edit mode for it
                    st.session_state.current_page = "skills"
                    st.rerun()
            with col_skip:
                if st.button("Skip for Now", use_container_width=True):
                    st.session_state.pending_skills_flight = None
                    st.rerun()
            st.divider()

    # ── Active flights ────────────────────────────────────────────────────────
    try:
        active = get_active_flights()
    except Exception:
        active = []

    if active:
        st.subheader("Complete a Flight")
        opts = {
            f"{f['origin']} → {f['destination']}  (briefed {f.get('planned_date','')})": f
            for f in active
        }
        sel_label = st.selectbox("Select active flight", list(opts.keys()), key="active_flt_sel")
        flight    = opts[sel_label]

        _render_complete_flight_form(flight)
        st.divider()

    # ── Log a past flight ─────────────────────────────────────────────────────
    with st.expander("Log a Past Flight (no brief)"):
        _render_manual_flight_form()

    # ── Delete a flight ───────────────────────────────────────────────────────
    all_flights = get_flights(limit=50)
    if all_flights:
        with st.expander("Delete a Flight Record"):
            del_opts = {
                f"{f.get('flight_date') or f.get('planned_date','')} — "
                f"{f['origin']}→{f['destination']} [{f['status']}]": f["id"]
                for f in all_flights
            }
            del_sel     = st.selectbox("Select flight to delete", list(del_opts.keys()), key="del_flt_sel")
            confirm_del = st.checkbox("Confirm — permanently delete this flight record", key="del_confirm")
            if st.button("Delete Flight", type="secondary", key="del_flt_btn", disabled=not confirm_del):
                try:
                    delete_flight(del_opts[del_sel])
                    st.success("Flight deleted.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Delete failed: {e}")

    st.divider()

    # ── Part 61 Progress ──────────────────────────────────────────────────────
    st.subheader("Part 61.109 Progress")
    try:
        prog = get_progress()
    except Exception as e:
        st.error(f"Could not load progress: {e}")
        return

    c = st.columns(3)
    for i, (key, req) in enumerate(prog["progress"].items()):
        with c[i % 3]:
            pct = min(req["logged"] / req["required"], 1.0) if req["required"] else 1.0
            st.metric(
                LABELS[key],
                f"{req['logged']:.1f} / {req['required']:.0f} hrs",
                delta="Met" if req["met"] else f"-{req['remaining']:.1f} to go",
            )
            st.progress(pct)

    st.divider()
    st.subheader(f"All Flights ({prog['flights']} completed)")
    flights = get_flights(limit=20, status="completed")
    if not flights:
        st.info("No completed flights yet.")
    for f in flights:
        tags = " | ".join([t for t, v in [
            ("Dual", f.get("dual")), ("Solo", f.get("solo")),
            ("XC", f.get("cross_country")), ("Night", f.get("night")),
            ("Hood", f.get("instrument_hood")),
        ] if v])
        h, m    = divmod(f.get("duration_min") or 0, 60)
        dur_str = f"{h}h {m:02d}m"
        ac_str  = ""
        if f.get("aircraft_type"):
            ac_str = "  ·  " + AIRCRAFT_DISPLAY.get(f["aircraft_type"], f["aircraft_type"])
        if f.get("tail_number"):
            ac_str += f" ({f['tail_number']})"
        tag_str = f"  ·  {tags}" if tags else ""
        st.markdown(
            f"**{f.get('flight_date', '—')}** — {f['origin']} → {f['destination']} "
            f"— {dur_str}{ac_str}{tag_str}"
        )
        if f.get("brief_at"):
            st.caption(f"Brief: {_fmt_ts(f['brief_at'])}")
        if f.get("remarks"):
            st.caption(f["remarks"])
        if f.get("weather_snap") or f.get("route_snap"):
            with st.expander("📋 Brief Snapshot"):
                _render_brief_snapshot(f)


def _render_complete_flight_form(flight):
    """Unified flight log + debrief form for completing an in-progress flight."""
    st.markdown(
        f"**{flight['origin']} to {flight['destination']}** — "
        f"Brief: {flight.get('recommendation','—')} — {flight.get('reason','')}"
    )

    with st.form("complete_flight"):
        st.markdown("#### Flight Details")
        c1, c2, c3 = st.columns(3)
        with c1:
            fdate    = st.date_input("Date flown")
            duration = st.number_input("Duration (min)", min_value=1, value=60)
        with c2:
            dual     = st.checkbox("Dual (with CFI)")
            solo     = st.checkbox("Solo")
            xc       = st.checkbox("Cross-Country")
            night    = st.checkbox("Night")
            hood     = st.checkbox("Hood / Instrument")
        with c3:
            t_os = st.number_input("Takeoffs",   min_value=0, value=1)
            l_gs = st.number_input("Landings",   min_value=0, value=1)
            nt   = st.number_input("Night T/Os", min_value=0, value=0)
            nl   = st.number_input("Night Ldgs", min_value=0, value=0)

        c_tail, c_rmk = st.columns([1, 2])
        with c_tail:
            tail_input = st.text_input(
                "Tail Number",
                value=flight.get("tail_number") or st.session_state.get("aircraft_tail") or "",
                placeholder="N12345",
            )
        with c_rmk:
            remarks = st.text_input("Remarks")

        st.markdown("#### Debrief")
        c4, c5 = st.columns(2)
        with c4:
            route_actual = st.text_input("Route flown / deviations")
            wx_actual    = st.text_input("Weather encountered")
        with c5:
            correct  = st.radio("Was the go/no-go call correct?", ["Yes", "No"], horizontal=True)
            lessons  = st.text_area("Lessons learned", height=80)
        deb_notes = st.text_area("Additional notes", height=60)

        if st.form_submit_button("Complete Flight Log", type="primary", use_container_width=True):
            try:
                uid = get_user_id()
                complete_flight(
                    flight["id"],
                    log_data={
                        "flight_date":    fdate,
                        "duration_min":   duration,
                        "dual":           dual,
                        "solo":           solo,
                        "cross_country":  xc,
                        "night":          night,
                        "instrument_hood": hood,
                        "takeoffs":       t_os,
                        "landings":       l_gs,
                        "night_takeoffs": nt,
                        "night_landings": nl,
                        "remarks":        remarks or None,
                        "actual_route":   route_actual or None,
                        "weather_actual": wx_actual or None,
                        "go_nogo_correct": correct == "Yes",
                        "lessons":        lessons or None,
                        "debrief_notes":  deb_notes or None,
                        "tail_number":    tail_input.strip() or None,
                    },
                    user_id=uid,
                )
                st.session_state.pending_skills_flight = flight["id"]
                st.success("Flight logged and debrief saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")


def _render_manual_flight_form():
    """Form for logging a past flight without a pre-flight brief."""
    with st.form("manual_flight"):
        c1, c2 = st.columns(2)
        with c1:
            state_o = st.selectbox("Origin State", US_STATES, index=US_STATES.index("FL"), key="ml_state_o")
        with c2:
            state_d = st.selectbox("Dest State", US_STATES, index=US_STATES.index("FL"), key="ml_state_d")

        c3, c4 = st.columns(2)
        with c3:
            try:
                apts_o = cached_airports_by_state(state_o)
            except Exception:
                apts_o = []
            if apts_o:
                opts_o   = {a["display"]: a["icao"] for a in apts_o}
                def_o    = next((d for d, i in opts_o.items() if i == "KSRQ"), list(opts_o.keys())[0])
                ml_origin = opts_o[st.selectbox("Origin", list(opts_o.keys()),
                                                 index=list(opts_o.keys()).index(def_o), key="ml_apt_o")]
            else:
                ml_origin = st.text_input("Origin ICAO", value="KSRQ", key="ml_apt_o").upper()
        with c4:
            try:
                apts_d = cached_airports_by_state(state_d)
            except Exception:
                apts_d = []
            if apts_d:
                opts_d  = {a["display"]: a["icao"] for a in apts_d}
                def_d   = next((d for d, i in opts_d.items() if i == "KSRQ"), list(opts_d.keys())[0])
                ml_dest = opts_d[st.selectbox("Destination", list(opts_d.keys()),
                                               index=list(opts_d.keys()).index(def_d), key="ml_apt_d")]
            else:
                ml_dest = st.text_input("Destination ICAO", value="KSRQ", key="ml_apt_d").upper()

        c5, c6, c7 = st.columns(3)
        with c5:
            fdate    = st.date_input("Date", key="ml_date")
            duration = st.number_input("Duration (min)", min_value=1, value=60, key="ml_dur")
        with c6:
            dual  = st.checkbox("Dual",          key="ml_dual")
            solo  = st.checkbox("Solo",          key="ml_solo")
            xc    = st.checkbox("Cross-Country", key="ml_xc")
            night = st.checkbox("Night",         key="ml_night")
            hood  = st.checkbox("Hood",          key="ml_hood")
        with c7:
            t_os = st.number_input("Takeoffs",   min_value=0, value=1, key="ml_to")
            l_gs = st.number_input("Landings",   min_value=0, value=1, key="ml_lg")
            nt   = st.number_input("Night T/Os", min_value=0, value=0, key="ml_nto")
            nl   = st.number_input("Night Ldgs", min_value=0, value=0, key="ml_nlg")

        remarks = st.text_input("Remarks", key="ml_rmk")

        if st.form_submit_button("Save Past Flight", use_container_width=True):
            try:
                uid = get_user_id()
                create_manual_flight(
                    ml_origin, ml_dest, duration, flight_date=fdate,
                    dual=dual, solo=solo, cross_country=xc, night=night,
                    instrument_hood=hood, takeoffs=t_os, landings=l_gs,
                    night_takeoffs=nt, night_landings=nl,
                    remarks=remarks or None, user_id=uid,
                )
                st.success("Past flight logged!")
                st.rerun()
            except Exception as e:
                st.error(f"Save failed: {e}")


# ── ACS Skills ────────────────────────────────────────────────────────────────

RATING_STR  = {"": None, "G": 3, "Y": 2, "R": 1}
RATING_RSTR = {None: "", 3: "G", 2: "Y", 1: "R"}

_CELL_STYLE = {
    3: "background:#16a34a;color:white;font-weight:700;text-align:center;",
    2: "background:#d97706;color:white;font-weight:700;text-align:center;",
    1: "background:#dc2626;color:white;font-weight:700;text-align:center;",
    None: "background:rgba(100,116,139,0.15);color:#94a3b8;text-align:center;",
}
_CELL_LABEL = {3: "G", 2: "Y", 1: "R", None: "·"}


def _acs_html_table(flights, by_flt, latest, task_ids, editing_fid=None):
    """Render the ACS matrix as a color-coded HTML table.

    editing_fid: if set, that flight's column header gets a blue highlight border
                 to show it matches the active editor above.
    """
    html = (
        "<div style='overflow-x:auto;'>"
        "<table style='border-collapse:collapse;width:100%;font-size:12px;"
        "font-family:Inter,sans-serif;'>"
        "<thead><tr>"
        "<th style='background:#1e293b;color:white;padding:6px 8px;text-align:left;"
        "min-width:220px;position:sticky;left:0;z-index:1;'>Task</th>"
    )
    for f in flights:
        date_str   = f.get("flight_date") or f.get("planned_date", "?")
        route      = f"{f['origin']}→{f['destination']}"
        is_edit    = (f["id"] == editing_fid)
        border     = "border-bottom:3px solid #3b82f6;" if is_edit else ""
        edit_badge = "<br><span style='font-size:9px;color:#93c5fd;'>✏ editing</span>" if is_edit else ""
        html += (
            f"<th style='background:#1e293b;color:white;padding:6px 8px;"
            f"text-align:center;min-width:70px;{border}'>"
            f"{date_str}<br><span style='font-weight:400;font-size:10px;'>{route}</span>"
            f"{edit_badge}"
            f"</th>"
        )
    html += (
        "<th style='background:#334155;color:white;padding:6px 8px;"
        "text-align:center;min-width:60px;'>Latest</th>"
        "</tr></thead><tbody>"
    )

    last_area = None
    for tid in task_ids:
        task      = ACS_TASKS[tid]
        area_name = task["area_name"]
        if area_name != last_area:
            last_area = area_name
            span = 2 + len(flights)
            html += (
                f"<tr><td colspan='{span}' style='background:rgba(100,116,139,0.2);"
                f"color:#94a3b8;font-weight:600;font-size:11px;padding:5px 8px;"
                f"border-top:2px solid rgba(100,116,139,0.3);letter-spacing:0.03em;'>"
                f"{area_name}</td></tr>"
            )
        html += (
            f"<tr>"
            f"<td style='padding:4px 8px;border-bottom:1px solid rgba(100,116,139,0.15);"
            f"color:inherit;'><b>{tid}</b> — {task['name']}</td>"
        )
        for f in flights:
            entry  = by_flt.get(f["id"], {}).get(tid)
            rating = entry["rating"] if entry else None
            style  = _CELL_STYLE[rating]
            label  = _CELL_LABEL[rating]
            html += (
                f"<td style='padding:4px 6px;"
                f"border-bottom:1px solid rgba(100,116,139,0.15);{style}'>{label}</td>"
            )
        # Latest column
        lat     = latest.get(tid)
        l_style = _CELL_STYLE[lat]
        l_label = _CELL_LABEL[lat]
        html += (
            f"<td style='padding:4px 6px;"
            f"border-bottom:1px solid rgba(100,116,139,0.15);"
            f"border-left:2px solid rgba(100,116,139,0.3);{l_style}'>{l_label}</td>"
        )
        html += "</tr>"

    html += "</tbody></table></div>"
    return html


def page_skills():
    st.header("ACS Skills Matrix")

    with st.spinner("Loading skill data..."):
        data    = get_flight_skill_matrix(limit=12)
        flights = data["flights"]
        by_flt  = data["by_flight"]
        latest  = data["latest_per_task"]

    stats = get_readiness_summary(latest)
    st.info(stats["summary"])
    st.progress(stats["pct"] / 100,
                text=f"{stats['pct']}% of ACS tasks at standard ({stats['green']}/{stats['total']})")

    if not flights:
        st.info("Complete flights to populate the skills matrix.")
        return

    task_ids = list(ACS_TASKS.keys())

    # ── Auto-enter edit mode when redirected from completed flight ─────────────
    pending = st.session_state.get("pending_skills_flight")
    if pending and not st.session_state.get("acs_editing_flight"):
        if any(f["id"] == pending for f in flights):
            st.session_state.acs_editing_flight = pending
            st.session_state.pending_skills_flight = None   # consumed

    editing_fid = st.session_state.get("acs_editing_flight")

    # ── Edit flight selector buttons ──────────────────────────────────────────
    st.caption("Select a flight to log or edit skill ratings:")
    btn_cols = st.columns(min(len(flights), 5))
    for i, flt in enumerate(flights[:5]):
        fid      = flt["id"]
        date_str = flt.get("flight_date") or flt.get("planned_date", "?")
        route    = f"{flt['origin']}→{flt['destination']}"
        is_active = (editing_fid == fid)
        with btn_cols[i % 5]:
            label = f"{'✏ ' if is_active else ''}{date_str} {route}"
            if st.button(label, key=f"acs_edit_btn_{fid}",
                         type="primary" if is_active else "secondary",
                         use_container_width=True):
                if is_active:
                    st.session_state.acs_editing_flight = None
                else:
                    st.session_state.acs_editing_flight = fid
                    st.session_state.pending_skills_flight = None
                st.rerun()

    # ── Inline editor (shown above the matrix when a flight is selected) ───────
    if editing_fid:
        edit_flt = next((f for f in flights if f["id"] == editing_fid), None)
        if edit_flt:
            existing  = by_flt.get(editing_fid, {})
            date_str  = edit_flt.get("flight_date") or edit_flt.get("planned_date", "?")
            flt_label = f"{date_str} — {edit_flt['origin']}→{edit_flt['destination']}"

            st.divider()
            st.markdown(f"**✏ Editing: {flt_label}**")
            st.caption("Set G = Met standard, Y = Needs work, R = Below standard, blank = not practiced. Click Save when done.")

            # Build the ratings dataframe
            rows = []
            for tid, task_info in ACS_TASKS.items():
                entry     = existing.get(tid)
                cur_str   = RATING_RSTR.get(entry.get("rating") if entry else None, "") if entry else ""
                rows.append({
                    "Area":   task_info["area_name"],
                    "Task":   f"{tid} — {task_info['name']}",
                    "Rating": cur_str,
                    "_tid":   tid,
                })

            df = pd.DataFrame(rows)
            edited = st.data_editor(
                df[["Area", "Task", "Rating"]],
                column_config={
                    "Area": st.column_config.TextColumn(
                        "Area", disabled=True, width="medium"
                    ),
                    "Task": st.column_config.TextColumn(
                        "Task", disabled=True, width="large"
                    ),
                    "Rating": st.column_config.SelectboxColumn(
                        "Rating",
                        options=["", "G", "Y", "R"],
                        width="small",
                        required=False,
                        help="G = Met standard, Y = Needs work, R = Below standard",
                    ),
                },
                hide_index=True,
                use_container_width=True,
                num_rows="fixed",
                key=f"acs_editor_{editing_fid}",
            )

            c1, c2, _ = st.columns([1, 1, 5])
            with c1:
                if st.button("💾 Save Ratings", type="primary", key="acs_inline_save"):
                    task_id_list = list(ACS_TASKS.keys())
                    to_save = {}
                    for i, tid in enumerate(task_id_list):
                        val = str(edited.iloc[i]["Rating"] or "").strip() if i < len(edited) else ""
                        num = RATING_STR.get(val)
                        if num is not None:
                            to_save[tid] = num
                    if to_save:
                        try:
                            uid = get_user_id()
                            log_flight_skills(editing_fid, to_save, user_id=uid)
                            st.success(f"Saved {len(to_save)} rating(s).")
                            st.session_state.acs_editing_flight = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Save failed: {e}")
                    else:
                        st.info("No ratings selected — set at least one G/Y/R before saving.")
            with c2:
                if st.button("Cancel", key="acs_inline_cancel"):
                    st.session_state.acs_editing_flight = None
                    st.rerun()

            st.divider()

    # ── Color-coded matrix table ───────────────────────────────────────────────
    st.caption("G = Met standard   |   Y = Needs work   |   R = Below standard   |   · = Not practiced")
    st.markdown(
        _acs_html_table(flights, by_flt, latest, task_ids, editing_fid=editing_fid),
        unsafe_allow_html=True,
    )

    # ── Task descriptions ──────────────────────────────────────────────────────
    with st.expander("ACS Task Descriptions"):
        for tid, desc in ACS_TASK_DESCRIPTIONS.items():
            task = ACS_TASKS[tid]
            st.markdown(f"**{tid} — {task['name']}**")
            st.caption(desc)

    # ── Training plan ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Training Priorities")
    plan = get_training_plan(latest)
    if plan:
        for item in plan[:12]:
            badge_clr = {"3": "#16a34a", "2": "#d97706", "1": "#dc2626"}.get(
                str(item.get("rating")), "#6b7280"
            )
            st.markdown(
                f"<div style='padding:4px 0;'>"
                f"<span style='background:{badge_clr};color:white;padding:2px 6px;"
                f"border-radius:4px;font-size:11px;font-weight:600;margin-right:8px;'>"
                f"{_CELL_LABEL.get(item.get('rating'))}</span>"
                f"<b>{item['task_id']}</b> — {item['name']} "
                f"<span style='color:#94a3b8;font-size:11px;'>({item['area_name']})</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.success("All ACS tasks at standard — checkride ready!")

    # ── Instructor ratings (students with a connected instructor) ─────────────
    if st.session_state.get("user_role") == "student":
        try:
            instructor = get_my_instructor()
        except Exception:
            instructor = None
        if instructor:
            instr_name = instructor.get("full_name") or instructor.get("email") or "your instructor"
            st.divider()
            st.subheader(f"Instructor Ratings — {instr_name}")
            try:
                uid       = get_user_id()
                instr_all = get_all_student_ratings(uid)
            except Exception:
                instr_all = []

            if instr_all:
                # Latest instructor rating per task
                instr_by_task = {}
                for r in instr_all:
                    tid = r["task_id"]
                    instr_by_task[tid] = r["rating"]

                # Find discrepancies between self and instructor
                discrepancies = []
                RATING_LBL = {3: "🟢 Proficient", 2: "🟡 Progressing", 1: "🔴 Needs Work"}
                for tid, instr_r in instr_by_task.items():
                    student_r = latest.get(tid)
                    if student_r is not None and student_r != instr_r:
                        discrepancies.append({
                            "task_id":    tid,
                            "name":       ACS_TASKS.get(tid, {}).get("name", tid),
                            "student":    student_r,
                            "instructor": instr_r,
                        })

                if discrepancies:
                    st.warning(
                        f"{len(discrepancies)} discrepancy(ies) — "
                        "your self-rating differs from your instructor's:"
                    )
                    for d in discrepancies[:10]:
                        s_lbl = RATING_LBL.get(d["student"], "—")
                        i_lbl = RATING_LBL.get(d["instructor"], "—")
                        st.markdown(
                            f"**{d['task_id']}** {d['name']}: "
                            f"You → {s_lbl} &nbsp;·&nbsp; Instructor → {i_lbl}",
                            unsafe_allow_html=True,
                        )
                else:
                    st.success("Your ratings align with your instructor's.")

                # Summary count
                st.caption(
                    f"Instructor has rated {len(instr_by_task)} of "
                    f"{len(ACS_TASKS)} tasks."
                )
            else:
                st.caption(f"No instructor ratings yet from {instr_name}.")


# ── Profile page ──────────────────────────────────────────────────────────────

def page_profile():
    st.header("Profile")

    # ── Check for incoming invite token ──────────────────────────────────────
    invite_token = st.query_params.get("invite")
    if invite_token:
        st.info(f"Invite token detected: `{invite_token}`")
        if st.button("Accept Instructor Invite", type="primary"):
            result = accept_invite(invite_token)
            if result.get("ok"):
                st.success("Instructor connection accepted! Reload the page.")
                st.query_params.clear()
                st.session_state.user_role = "instructor"
                st.rerun()
            else:
                st.error(result.get("error", "Could not accept invite."))
        st.divider()

    # ── Load current profile ──────────────────────────────────────────────────
    try:
        prof = get_profile()
    except Exception as e:
        st.error(f"Could not load profile: {e}")
        return

    if not prof:
        st.warning("No profile found. Fill in your details below to create one.")
        prof = {}

    # ── Edit form ─────────────────────────────────────────────────────────────
    with st.form("profile_form"):
        full_name = st.text_input("Full Name", value=prof.get("full_name") or "")
        role      = st.selectbox(
            "Role",
            ["student", "instructor"],
            index=0 if prof.get("role", "student") == "student" else 1,
        )
        st.markdown("#### Default Aircraft")
        ac_options_list = ["(none)"] + list(AIRCRAFT_OPTIONS.keys())
        current_ac_disp = AIRCRAFT_DISPLAY.get(prof.get("aircraft_type") or "", "")
        ac_idx  = ac_options_list.index(current_ac_disp) if current_ac_disp in ac_options_list else 0
        ac_sel  = st.selectbox("Aircraft Type", ac_options_list, index=ac_idx)
        tail    = st.text_input("Tail Number", value=prof.get("tail_number") or "",
                                placeholder="N12345")
        if st.form_submit_button("Save Profile", use_container_width=False):
            try:
                ac_key = AIRCRAFT_OPTIONS.get(ac_sel) if ac_sel != "(none)" else None
                create_or_update_profile(
                    full_name=full_name, role=role,
                    aircraft_type=ac_key,
                    tail_number=tail or None,
                )
                st.session_state.user_role     = role
                st.session_state.user_name     = full_name
                st.session_state.aircraft_type = ac_key
                st.session_state.aircraft_tail = tail.strip() or None
                st.success("Profile saved.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save profile: {e}")

    st.divider()

    # ── Instructor connection (students only) ─────────────────────────────────
    if (prof.get("role") or st.session_state.user_role) == "student":
        st.subheader("Instructor Connection")
        try:
            instructor = get_my_instructor()
        except Exception:
            instructor = None

        if instructor:
            st.success(
                f"Connected to: **{instructor.get('full_name') or instructor.get('email')}**"
            )
        else:
            st.info("No instructor connected yet. Generate an invite link and share it with your instructor.")
            if st.button("Generate Invite Link"):
                try:
                    token = create_invite()
                    base  = os.environ.get("RHO_BASE_URL", "http://localhost:8501")
                    st.session_state.generated_invite_link = f"{base}/?invite={token}"
                except Exception as e:
                    st.error(f"Could not create invite: {e}")
            if st.session_state.generated_invite_link:
                st.code(st.session_state.generated_invite_link, language=None)
                st.caption("Share this link with your instructor. It expires in 7 days.")

        # Show pending invites
        try:
            pending = get_pending_invites()
        except Exception:
            pending = []
        if pending:
            st.caption(f"{len(pending)} pending invite(s) outstanding.")

    # ── Students (instructors only) ───────────────────────────────────────────
    elif (prof.get("role") or st.session_state.user_role) == "instructor":
        st.subheader("Your Students")
        try:
            students = get_my_students()
        except Exception:
            students = []

        if students:
            for s in students:
                st.write(f"• {s.get('full_name') or s.get('email')}")
        else:
            st.info(
                "No students connected yet. Students generate an invite link from their Profile page — "
                "visit that link to connect."
            )


# ── Instructor dashboard ───────────────────────────────────────────────────────

def page_instructor():
    st.header("Student Dashboard")

    # ── Student selector ──────────────────────────────────────────────────────
    try:
        students = get_my_students()
    except Exception as e:
        st.error(f"Could not load students: {e}")
        return

    if not students:
        st.info(
            "No students connected yet. Students generate an invite link from their Profile page — "
            "visit that link to connect."
        )
        return

    student_opts = {
        (s.get("full_name") or s.get("email")): s["id"]
        for s in students
    }
    chosen_name = st.selectbox("Select student", list(student_opts.keys()))
    student_id  = student_opts[chosen_name]
    st.session_state.instr_student_id = student_id

    # ── Fetch student flights ─────────────────────────────────────────────────
    try:
        flights = get_student_flights(student_id)
    except Exception as e:
        st.error(f"Could not load student flights: {e}")
        return

    if not flights:
        st.info("No flights logged yet for this student.")
        return

    completed = [f for f in flights if f.get("status") == "completed"]
    st.caption(f"{len(completed)} completed flights")

    # ── Flight selector ───────────────────────────────────────────────────────
    flight_opts = {
        f"{f.get('flight_date') or f.get('planned_date', '?')}  {f.get('origin','?')} → {f.get('destination','?')}": f["id"]
        for f in completed
    }
    chosen_flight_label = st.selectbox("Select flight to review", list(flight_opts.keys()))
    flight_id = flight_opts[chosen_flight_label]

    # ── Load skill logs ───────────────────────────────────────────────────────
    try:
        skill_rows = get_student_skill_log(student_id, [flight_id])
    except Exception as e:
        st.error(f"Could not load skill log: {e}")
        skill_rows = []

    try:
        instr_ratings = get_instructor_ratings(flight_id)
    except Exception:
        instr_ratings = {}

    student_ratings = {r["task_id"]: r["rating"] for r in skill_rows}

    # ── Build dual-column ACS matrix ─────────────────────────────────────────
    RATING_ICON = {3: "🟢", 2: "🟡", 1: "🔴", None: "—"}
    RATING_LABEL_SHORT = {3: "3 Proficient", 2: "2 Progressing", 1: "1 Needs Work"}

    st.subheader(f"ACS Skills — {chosen_flight_label}")

    # Group tasks by area
    from collections import OrderedDict
    areas = OrderedDict()
    for task_id, info in ACS_TASKS.items():
        area_name = info["area_name"]
        if area_name not in areas:
            areas[area_name] = []
        areas[area_name].append((task_id, info["name"]))

    # Instructor rating form
    new_ratings = {}
    with st.form("instructor_ratings_form"):
        for area_name, tasks in areas.items():
            st.markdown(f"**{area_name}**")
            for task_id, task_name in tasks:
                stu_r     = student_ratings.get(task_id)
                instr_r   = (instr_ratings.get(task_id) or {}).get("rating")
                stu_icon  = RATING_ICON.get(stu_r, "—")
                col_label, col_stu, col_instr = st.columns([3, 1, 2])
                with col_label:
                    st.caption(f"{task_id}: {task_name}")
                with col_stu:
                    st.caption(f"Student: {stu_icon}")
                with col_instr:
                    options = ["(no rating)", "1 Needs Work", "2 Progressing", "3 Proficient"]
                    default_idx = 0
                    if instr_r is not None:
                        label = RATING_LABEL_SHORT.get(instr_r, "")
                        if label in options:
                            default_idx = options.index(label)
                    sel = st.selectbox(
                        "Instructor",
                        options,
                        index=default_idx,
                        key=f"instr_{task_id}_{flight_id}",
                        label_visibility="collapsed",
                    )
                    if sel != "(no rating)":
                        new_ratings[task_id] = int(sel[0])

        if st.form_submit_button("Save Instructor Ratings", type="primary"):
            try:
                result = save_instructor_ratings(flight_id, student_id, new_ratings)
                saved = result.get("saved", 0)
                st.success(f"Saved {saved} rating(s).")
            except Exception as e:
                st.error(f"Could not save ratings: {e}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not st.session_state.authenticated:
        show_auth()
        return

    page = show_nav()

    if page == "home":
        page_home()
    elif page == "preflight":
        page_preflight()
    elif page == "logbook":
        page_logbook()
    elif page == "skills":
        page_skills()
    elif page == "profile":
        page_profile()
    elif page == "instructor":
        page_instructor()


if __name__ == "__main__":
    main()
