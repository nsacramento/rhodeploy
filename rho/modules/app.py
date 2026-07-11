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
header[data-testid="stHeader"] { display: none; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stSidebar"] { display: none !important; }

/* ── Input field contrast — text inputs, number inputs, textareas ─────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    border: 1.5px solid #94a3b8 !important;
    border-radius: 6px !important;
    background: #ffffff !important;
}

/* ── Selectbox / dropdown contrast ─────────────────────────────────────── */
/* Streamlit now uses React ARIA (not BaseWeb) for selectboxes.
   Target the role="group" div which wraps the visible input + arrow button. */
[data-testid="stSelectbox"] [role="group"],
[data-testid="stMultiSelect"] [role="group"] {
    border: 1.5px solid #94a3b8 !important;
    border-radius: 6px !important;
    background-color: #ffffff !important;
}
[data-testid="stSelectbox"] input[role="combobox"],
[data-testid="stMultiSelect"] input[role="combobox"] {
    background-color: #ffffff !important;
}

/* ── Login tab colors (dark bg) — overridden to white in show_auth() ──── */
[data-baseweb="tab"], [role="tab"] {
    color: #1e293b !important;
    font-weight: 600 !important;
    opacity: 1 !important;
}
[data-baseweb="tab"][aria-selected="true"],
[role="tab"][aria-selected="true"] {
    color: #1d4ed8 !important;
    font-weight: 700 !important;
}

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

/* ── GO button — green ── */
button[data-testid="baseButton-primary"] {
    background-color: #15803d !important;
    border-color: #15803d !important;
    color: white !important;
}
button[data-testid="baseButton-primary"]:hover {
    background-color: #166534 !important;
    border-color: #166534 !important;
}

/* ── NO-GO button — red ──
   Targets a secondary button in the last (2nd) column of a 2-column layout.
   nth-child(2):last-child ensures exactly 2 columns (not nav bars with more). */
[data-testid="stColumn"]:nth-child(2):last-child button[data-testid="baseButton-secondary"] {
    background-color: #991b1b !important;
    border-color: #991b1b !important;
    color: white !important;
}
[data-testid="stColumn"]:nth-child(2):last-child button[data-testid="baseButton-secondary"]:hover {
    background-color: #7f1d1d !important;
    border-color: #7f1d1d !important;
}

/* ── App background — light aviation blue-gray (logged-in state) ── */
[data-testid="stAppViewContainer"] { background-color: #eef2f7 !important; }
[data-testid="stMain"]             { background-color: #eef2f7 !important; }
.block-container { padding-top: 1.2rem !important; }

/* ── Login page — aviation sky gradient (overrides above) ── */
.rho-login-page [data-testid="stAppViewContainer"],
.rho-login-bg {
    background: linear-gradient(160deg, #0a1628 0%, #1a3a5c 40%, #1e6091 70%, #5ba3d4 100%) !important;
    min-height: 100vh;
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
from rho.modules.navlog    import generate_navlog
from rho.modules.reports   import generate_readiness_report, generate_lesson_plan
from rho.modules.feedback  import submit_feedback, FEEDBACK_FEATURES
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
    ("invite_email",          ""),     # email typed into instructor invite input
    ("pending_invite",        None),   # invite token preserved across login/signup rerun
    ("aircraft_type",         None),   # default aircraft type key (e.g. 'c172s')
    ("aircraft_tail",         None),   # default tail number (e.g. 'N12345')
    ("feedback_ids",          None),   # list of unique feedback entry IDs (int)
    ("feedback_next_id",      0),      # counter for next feedback entry ID
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


# ── Shared helpers ────────────────────────────────────────────────────────────

def _progress_html(pct, color="#15803d"):
    """Dark, high-contrast progress bar (replaces Streamlit's light-on-light default)."""
    w = max(0.0, min(1.0, float(pct))) * 100
    return (
        "<div style='background:#cbd5e1;border-radius:4px;height:8px;"
        "overflow:hidden;margin:4px 0 12px;'>"
        "<div style='width:" + f"{w:.1f}" + "%;background:" + color + ";height:100%;"
        "border-radius:4px;'></div></div>"
    )


# ── Auth ──────────────────────────────────────────────────────────────────────

def show_auth():
    # Aviation sky background
    st.markdown("""
    <style>
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(160deg, #0a1628 0%, #0d2a4a 35%, #1a4f7a 65%, #4a90c4 100%) !important;
    }
    [data-testid="stMain"]   { background: transparent !important; }
    [data-testid="stBottom"] { background: transparent !important; }
    /* Override app background on login page */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(160deg, #0a1628 0%, #0d2a4a 35%, #1a4f7a 65%, #4a90c4 100%) !important;
    }
    /* White labels for form fields on dark background */
    [data-testid="stTextInput"] label,
    [data-testid="stSelectbox"] label,
    [data-testid="stForm"] label { color: rgba(255,255,255,0.9) !important; }
    /* Tab styles injected globally above — no duplicate needed here */
    .rho-login-card {
        background: rgba(255,255,255,0.95);
        border-radius: 16px;
        padding: 2rem 2.5rem 2.5rem;
        box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        backdrop-filter: blur(10px);
    }
    .rho-login-header {
        text-align: center;
        margin-bottom: 0.25rem;
    }
    .rho-login-logo {
        font-size: 3rem;
        line-height: 1;
        margin-bottom: 0.25rem;
        filter: brightness(0) invert(1);
    }
    .rho-login-title {
        font-size: 2rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
        margin: 0;
        text-shadow: 0 1px 4px rgba(0,0,0,0.4);
    }
    .rho-login-tagline {
        font-size: 0.9rem;
        color: #b8d4f0;
        margin: 0.15rem 0 0;
        font-style: italic;
    }
    /* Tab colors on dark login background — override global dark rule */
    [data-baseweb="tab"], [role="tab"] {
        color: rgba(255,255,255,0.75) !important;
        font-weight: 600 !important;
        opacity: 1 !important;
    }
    [data-baseweb="tab"][aria-selected="true"],
    [role="tab"][aria-selected="true"] {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    </style>
    """, unsafe_allow_html=True)

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("""
        <div class="rho-login-header">
            <div class="rho-login-logo">✈</div>
            <p class="rho-login-title">Rho</p>
            <p class="rho-login-tagline">Student Pilot Co-Pilot · VFR Flight Planning</p>
        </div>
        """, unsafe_allow_html=True)
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
                        # Preserve invite token across rerun, redirect to Profile
                        _tok = st.query_params.get("invite")
                        if _tok:
                            st.session_state.pending_invite  = _tok
                            st.session_state.current_page    = "profile"
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
                        # Preserve invite token across rerun, redirect to Profile
                        _tok = st.query_params.get("invite")
                        if _tok:
                            st.session_state.pending_invite = _tok
                            st.session_state.current_page   = "profile"
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
                st.session_state.user_role     = prof.get("role", "student")
                st.session_state.user_name     = prof.get("full_name") or st.session_state.user_email
                st.session_state.aircraft_type = prof.get("aircraft_type")
                st.session_state.aircraft_tail = prof.get("tail_number")
        except Exception:
            pass

    name_display = st.session_state.user_name or st.session_state.user_email or "Pilot"
    role_display = (st.session_state.user_role or "student").capitalize()

    pages = [
        ("Home",             "home"),
        ("Pre-Flight Brief", "preflight"),
        ("Flight Log",       "logbook"),
        ("ACS Skills",       "skills"),
        ("Tools",            "tools"),
        ("Profile",          "profile"),
        ("Guide",            "guide"),
        ("Feedback",         "feedback"),
    ]
    if st.session_state.user_role == "instructor":
        pages.append(("Students", "instructor"))

    # ── Top bar: brand + pilot info + sign out ────────────────────────────────
    brand_col, info_col, signout_col = st.columns([1, 6, 1])
    with brand_col:
        st.markdown(
            "<div style='font-size:1.1rem;font-weight:800;color:#1e293b;"
            "padding:6px 0;letter-spacing:-0.5px;'>✈ Rho</div>",
            unsafe_allow_html=True,
        )
    with info_col:
        st.markdown(
            f"<div style='padding:6px 0;font-size:0.82rem;color:#64748b;'>"
            f"<b style='color:#1e293b;'>{name_display}</b> &nbsp;·&nbsp; {role_display}"
            f"</div>",
            unsafe_allow_html=True,
        )
    with signout_col:
        if st.button("Sign Out", key="signout", use_container_width=True):
            sign_out()
            for k in ("authenticated", "user_email", "user_role", "user_name",
                      "last_brief", "pending_skills_flight", "instr_student_id",
                      "aircraft_type", "aircraft_tail", "generated_invite_link",
                      "invite_email", "feedback_ids"):
                st.session_state[k] = False if k == "authenticated" else None
            st.rerun()

    # ── Nav strip — segmented control ────────────────────────────────────────
    page_labels = [label for label, _ in pages]
    page_keys   = [key   for _, key   in pages]
    current_label = next(
        (label for label, key in pages if key == st.session_state.current_page),
        page_labels[0],
    )
    # Key changes with current page so control always reflects programmatic nav changes
    selected = st.segmented_control(
        "nav", page_labels,
        default=current_label,
        key=f"_nav_{current_label}",
        label_visibility="collapsed",
    )
    if selected and selected != current_label:
        st.session_state.current_page = page_keys[page_labels.index(selected)]
        st.rerun()

    # ── Profile missing banner ────────────────────────────────────────────────
    if st.session_state.user_role is None:
        col_pmsg, col_pbtn = st.columns([5, 1])
        with col_pmsg:
            st.warning("Profile not set up — add your name, role, and default aircraft.")
        with col_pbtn:
            if st.button("Set Up Profile", key="nav_profile_prompt"):
                st.session_state.current_page = "profile"
                st.rerun()

    # ── Active flight banner ──────────────────────────────────────────────────
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
            st.markdown(_progress_html(pct_t), unsafe_allow_html=True)
        with c2:
            pct_s = min(solo_hrs / 10.0, 1.0)
            st.metric("Solo Hours", f"{solo_hrs:.1f} / 10")
            st.markdown(_progress_html(pct_s, "#0284c7"), unsafe_allow_html=True)
        with c3:
            pct_d = min(dual_hrs / 20.0, 1.0)
            st.metric("Dual Hours", f"{dual_hrs:.1f} / 20")
            st.markdown(_progress_html(pct_d, "#7c3aed"), unsafe_allow_html=True)
        with c4:
            st.metric("Requirements Met", f"{met_count} / {total_req}")
            pct_r = min(met_count / max(total_req, 1), 1.0)
            st.markdown(_progress_html(pct_r, "#f59e0b"), unsafe_allow_html=True)
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
        st.markdown(_progress_html(pct / 100), unsafe_allow_html=True)
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
    dl_c1, dl_c2, dl_c3 = st.columns(3)

    with dl_c1:
        st.markdown("**In-Flight Guide** — comms, headings, airspace rules, radio scripts.")
        try:
            cs_bytes = generate_cheatsheet(
                brief, comms_o, comms_d,
                aircraft=get_aircraft(aircraft_key),
                tail_number=tail_number,
                flight_rules="VFR",
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

    with dl_c3:
        st.markdown("**VFR Nav Log** — headings, WCA, GS, ETE, fuel planning.")
        try:
            nl_bytes = generate_navlog(
                brief,
                aircraft=get_aircraft(aircraft_key),
                flight_rules="VFR",
            )
            st.download_button(
                label="Download Nav Log (PDF)",
                data=nl_bytes,
                file_name=f"navlog_{origin}_{dest}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"Nav log unavailable: {e}")

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
            bar_color = "#15803d" if req["met"] else "#0284c7"
            st.metric(
                LABELS[key],
                f"{req['logged']:.1f} / {req['required']:.0f} hrs",
                delta="Met" if req["met"] else f"-{req['remaining']:.1f} to go",
            )
            st.markdown(_progress_html(pct, bar_color), unsafe_allow_html=True)

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
        "min-width:160px;max-width:200px;position:sticky;left:0;z-index:1;'>Task</th>"
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
            f"color:inherit;max-width:200px;white-space:normal;'>"
            f"<b style='font-size:11px;'>{tid}</b>"
            f"<br><span style='font-size:10px;color:#94a3b8;'>{task['name']}</span></td>"
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
    rdy_clr = "#15803d" if stats["pct"] >= 80 else ("#b45309" if stats["pct"] >= 50 else "#991b1b")
    st.markdown(
        f"<div style='font-size:0.8rem;color:#475569;margin-bottom:2px;'>"
        f"{stats['pct']}% of ACS tasks at standard ({stats['green']}/{stats['total']})"
        f"</div>"
        + _progress_html(stats["pct"] / 100, rdy_clr),
        unsafe_allow_html=True,
    )

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

    # ── PDF Downloads ─────────────────────────────────────────────────────────
    st.divider()
    st.subheader("Reports")
    rpt_c1, rpt_c2 = st.columns(2)

    pilot_name = st.session_state.get("user_name") or st.session_state.get("user_email")

    with rpt_c1:
        st.markdown("**Checkride Readiness Report** — full per-area ACS breakdown, student + CFI signature block.")
        try:
            rpt_bytes = generate_readiness_report(
                latest_per_task=latest,
                stats=stats,
                pilot_name=pilot_name,
                flight_rules="VFR",
            )
            st.download_button(
                label="Download Readiness Report (PDF)",
                data=rpt_bytes,
                file_name="checkride_readiness.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
        except Exception as e:
            st.error(f"Could not generate report: {e}")

    with rpt_c2:
        st.markdown("**Lesson Plan** — next 3 lessons targeting your highest-priority skill gaps.")
        try:
            lp_bytes = generate_lesson_plan(
                plan=plan,
                latest_per_task=latest,
                n_lessons=3,
                pilot_name=pilot_name,
                flight_rules="VFR",
            )
            st.download_button(
                label="Download Lesson Plan (PDF)",
                data=lp_bytes,
                file_name="lesson_plan.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        except Exception as e:
            st.caption(f"Lesson plan unavailable: {e}")

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

    # ── Check for incoming invite token (URL param or session state) ─────────
    invite_token = st.query_params.get("invite") or st.session_state.get("pending_invite")
    if invite_token:
        try:
            result = accept_invite(invite_token)
            if result.get("ok"):
                st.success(
                    "You're now connected as this student's instructor! "
                    "You can view their flights in the **Students** tab."
                )
                st.session_state.pending_invite = None
                st.session_state.user_role      = "instructor"
                st.query_params.clear()
            else:
                err = result.get("error", "Could not process invite.")
                if "already used" in err or "not found" in err:
                    st.info(
                        "This invite link has already been used or expired. "
                        "Ask the student to generate a new one."
                    )
                else:
                    st.error(err)
                st.session_state.pending_invite = None
        except Exception as e:
            st.warning(f"Invite processing error: {e}")
            st.session_state.pending_invite = None
        st.divider()

    # ── Manual invite code entry (fallback for instructors) ───────────────────
    with st.expander("Enter an invite code manually"):
        manual_token = st.text_input("Paste invite code here", key="manual_invite_input",
                                     placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        if st.button("Connect", key="manual_invite_btn") and manual_token.strip():
            try:
                result = accept_invite(manual_token.strip())
                if result.get("ok"):
                    st.success("Connected! Check the Students tab.")
                    st.session_state.user_role = "instructor"
                    st.rerun()
                else:
                    st.error(result.get("error", "Invalid or expired code."))
            except Exception as e:
                st.error(f"Error: {e}")
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
            st.info("No instructor connected yet.")
            st.caption(
                "How it works: generate a link below and share it with your instructor. "
                "When they click it and log in (or create an account), they'll be linked to you automatically. "
                "One instructor can have multiple students — each student generates their own invite."
            )
            import urllib.parse
            instr_email = st.text_input(
                "Instructor's email (optional — pre-fills the share message)",
                value=st.session_state.get("invite_email", ""),
                placeholder="cfi@example.com",
                key="invite_email_input",
            )
            st.session_state.invite_email = instr_email

            if st.button("Generate Invite Link"):
                try:
                    token = create_invite()
                    base  = os.environ.get("RHO_BASE_URL", "http://localhost:8501")
                    st.session_state.generated_invite_link = f"{base}/?invite={token}"
                except Exception as e:
                    st.error(f"Could not create invite: {e}")

            if st.session_state.generated_invite_link:
                link = st.session_state.generated_invite_link
                st.code(link, language=None)
                subject = urllib.parse.quote("You're invited to connect on Rho — Student Pilot Co-Pilot")
                body = urllib.parse.quote(
                    f"Hi,\n\nI'd like to add you as my instructor on Rho, a student pilot co-pilot app.\n\n"
                    f"Click the link below to connect:\n{link}\n\n"
                    f"The link expires in 7 days. If you don't have an account yet, you'll be prompted to create one.\n\nThanks!"
                )
                to = urllib.parse.quote(instr_email) if instr_email else ""
                mailto = f"mailto:{to}?subject={subject}&body={body}"
                st.markdown(
                    f"[Open in email client]({mailto}) — or copy the link above and paste it manually.",
                    unsafe_allow_html=False,
                )
                st.caption("Link expires in 7 days.")

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

    student_ratings = {r["acs_task_id"]: r["proficiency"] for r in skill_rows}

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


# ── Tools ─────────────────────────────────────────────────────────────────────

def page_tools():
    st.header("Tools")

    # ── Density Altitude Calculator ───────────────────────────────────────────
    st.subheader("Density Altitude")
    st.caption("Performance calculations use density altitude, not pressure altitude. High DA = reduced climb rate, longer takeoff roll, reduced engine power.")

    da_c1, da_c2, da_c3 = st.columns(3)
    with da_c1:
        pa_ft = st.number_input("Pressure Altitude (ft)", min_value=0, max_value=20000,
                                value=0, step=100, key="da_pa")
    with da_c2:
        oat_c = st.number_input("Outside Air Temp (°C)", min_value=-40, max_value=50,
                                value=15, step=1, key="da_oat")
    with da_c3:
        altimeter_in = st.number_input('Altimeter Setting ("Hg)', min_value=27.0,
                                       max_value=31.0, value=29.92, step=0.01,
                                       format="%.2f", key="da_alt")

    # Pressure altitude from altimeter setting
    # PA = field elevation + (29.92 - altimeter) * 1000
    # If user enters PA directly (e.g. from altimeter set to 29.92), use as is
    # ISA temperature at PA
    isa_temp_c = 15.0 - (pa_ft / 1000.0) * 1.98
    temp_dev   = oat_c - isa_temp_c

    # ICAO density altitude formula: DA = PA + 118.8 * (OAT - ISA)
    density_alt = int(pa_ft + 118.8 * temp_dev)

    da_color = (
        "green"  if density_alt < 2000 else
        "orange" if density_alt < 5000 else
        "red"
    )
    st.markdown(
        f"<div style='background:#f1f5f9;border-radius:8px;padding:16px 20px;margin:8px 0;'>"
        f"<span style='font-size:0.9rem;color:#475569;'>Density Altitude</span><br/>"
        f"<span style='font-size:2rem;font-weight:800;color:{da_color};'>{density_alt:,} ft</span>"
        f"&nbsp;&nbsp;<span style='font-size:0.85rem;color:#6b7280;'>"
        f"ISA at PA: {isa_temp_c:.1f}°C &nbsp;|&nbsp; "
        f"Temp deviation: {temp_dev:+.1f}°C from ISA</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

    if density_alt > 5000:
        st.warning("High density altitude — expect significantly degraded climb performance and longer takeoff roll. Review POH performance charts.")
    elif density_alt > 2000:
        st.info("Elevated density altitude — review POH performance charts before flight.")

    st.divider()

    # ── W&B Calculator ────────────────────────────────────────────────────────
    st.subheader("Weight & Balance")
    st.caption("Select your aircraft, enter station weights, and Rho will compute gross weight and CG. Always verify against your specific aircraft's POH loading graph.")

    # Aircraft selector
    ac_options_list = list(AIRCRAFT_OPTIONS.keys())
    default_ac = None
    if st.session_state.get("aircraft_type"):
        default_disp = AIRCRAFT_DISPLAY.get(st.session_state.aircraft_type)
        if default_disp and default_disp in ac_options_list:
            default_ac = default_disp

    ac_sel = st.selectbox(
        "Aircraft",
        ac_options_list,
        index=ac_options_list.index(default_ac) if default_ac else 0,
        key="wb_aircraft",
    )
    ac_key = AIRCRAFT_OPTIONS.get(ac_sel)
    ac     = get_aircraft(ac_key) if ac_key else None
    wb     = ac.get("wb") if ac else None

    if not ac or not wb:
        st.info("W&B data not available for this aircraft. Select a different aircraft.")
        return

    st.caption(f"Datum: {wb['datum']} &nbsp;|&nbsp; Empty weight: {ac['empty_weight_lbs']:,} lbs at arm {wb['empty_arm']} in &nbsp;|&nbsp; Max gross: {ac['max_gross_lbs']:,} lbs &nbsp;|&nbsp; CG limits: {wb['cg_fwd_in']}–{wb['cg_aft_in']} in")

    # Station inputs
    stations = wb["stations"]
    st.markdown("**Enter station weights:**")

    wb_inputs = {}
    n_cols = min(len(stations), 4)
    wb_cols = st.columns(n_cols)
    for i, (station_name, station) in enumerate(stations.items()):
        with wb_cols[i % n_cols]:
            max_lbs = station["max_lbs"]
            if "Fuel" in station_name:
                # Offer gallons → auto-convert
                gal = st.number_input(
                    f"{station_name} (gal)",
                    min_value=0.0,
                    max_value=float(ac.get("fuel_usable_gal", max_lbs // 6)),
                    value=0.0,
                    step=1.0,
                    key=f"wb_{station_name}",
                )
                lbs = round(gal * wb.get("fuel_lbs_per_gal", 6.0), 1)
                st.caption(f"= {lbs} lbs")
                wb_inputs[station_name] = lbs
            else:
                lbs = st.number_input(
                    f"{station_name} (lbs)",
                    min_value=0,
                    max_value=max_lbs,
                    value=0,
                    step=5,
                    key=f"wb_{station_name}",
                )
                wb_inputs[station_name] = lbs

    # Calculate
    empty_wt  = ac["empty_weight_lbs"]
    empty_mom = empty_wt * wb["empty_arm"]

    total_payload_wt  = sum(wb_inputs.values())
    total_payload_mom = sum(
        wb_inputs[sn] * stations[sn]["arm"]
        for sn in stations
    )

    gross_wt  = empty_wt + total_payload_wt
    total_mom = empty_mom + total_payload_mom
    cg_in     = round(total_mom / gross_wt, 2) if gross_wt else 0

    max_gross  = ac["max_gross_lbs"]
    cg_fwd     = wb["cg_fwd_in"]
    cg_aft     = wb["cg_aft_in"]

    wt_ok  = gross_wt <= max_gross
    cg_ok  = cg_fwd <= cg_in <= cg_aft
    all_ok = wt_ok and cg_ok

    # Results display
    res_clr = "#15803d" if all_ok else "#991b1b"
    verdict = "WITHIN LIMITS" if all_ok else "OUT OF LIMITS"

    st.markdown(
        f"<div style='background:#f1f5f9;border-radius:8px;padding:16px 20px;margin:12px 0;'>"
        f"<div style='display:flex;gap:40px;align-items:center;'>"
        f"<div><span style='font-size:0.8rem;color:#475569;'>Gross Weight</span><br/>"
        f"<span style='font-size:1.6rem;font-weight:800;color:{'#15803d' if wt_ok else '#991b1b'};'>"
        f"{gross_wt:,} lbs</span><br/>"
        f"<span style='font-size:0.75rem;color:#6b7280;'>max {max_gross:,} lbs</span></div>"
        f"<div><span style='font-size:0.8rem;color:#475569;'>CG Position</span><br/>"
        f"<span style='font-size:1.6rem;font-weight:800;color:{'#15803d' if cg_ok else '#991b1b'};'>"
        f"{cg_in} in</span><br/>"
        f"<span style='font-size:0.75rem;color:#6b7280;'>limits: {cg_fwd}–{cg_aft} in</span></div>"
        f"<div><span style='font-size:0.8rem;color:#475569;'>Verdict</span><br/>"
        f"<span style='font-size:1.4rem;font-weight:800;color:{res_clr};'>{verdict}</span></div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

    if not wt_ok:
        over = gross_wt - max_gross
        st.error(f"Over max gross weight by {over} lbs. Reduce payload before flight.")
    if not cg_ok:
        if cg_in < cg_fwd:
            st.error(f"CG too far forward ({cg_in} in vs limit {cg_fwd} in). Shift weight aft or reduce forward stations.")
        else:
            st.error(f"CG too far aft ({cg_in} in vs limit {cg_aft} in). This is a serious stability hazard — do not fly.")

    # Station breakdown table
    with st.expander("Station breakdown"):
        rows = [("Station", "Weight (lbs)", "Arm (in)", "Moment (lb·in)")]
        rows.append((f"Empty Aircraft", f"{empty_wt:,}", f"{wb['empty_arm']}", f"{int(empty_mom):,}"))
        for sn, lbs in wb_inputs.items():
            arm = stations[sn]["arm"]
            mom = lbs * arm
            rows.append((sn, f"{lbs}", f"{arm}", f"{int(mom):,}"))
        rows.append(("TOTAL", f"{gross_wt:,}", f"{cg_in}", f"{int(total_mom):,}"))

        for i, row in enumerate(rows):
            cols = st.columns([2, 1, 1, 1.5])
            for j, cell in enumerate(row):
                bold = (i == 0 or i == len(rows) - 1)
                cols[j].markdown(f"**{cell}**" if bold else cell)

    st.caption("CG limits shown are simplified two-point envelopes. Always verify against the POH loading graph for your specific aircraft serial number.")


# ── Feedback ──────────────────────────────────────────────────────────────────

def page_feedback():
    st.header("Share Feedback")
    st.caption(
        "Rho is in beta — your feedback shapes what gets built next. "
        "You can log feedback for multiple features in one go."
    )

    # Better selectbox contrast
    st.markdown("""
    <style>
    div[data-testid="stSelectbox"] > div:first-child > div:first-child {
        background: #f8fafc !important;
        border: 1px solid #94a3b8 !important;
    }
    div[data-testid="stSelectbox"] svg { color: #334155 !important; fill: #334155 !important; }
    </style>
    """, unsafe_allow_html=True)

    # Initialize entry ID list
    if not st.session_state.get("feedback_ids"):
        st.session_state.feedback_ids    = [0]
        st.session_state.feedback_next_id = 1

    fb_ids = st.session_state.feedback_ids

    default_idx = FEEDBACK_FEATURES.index("Overall App / General")

    for pos, fid in enumerate(fb_ids):
        if pos > 0:
            st.markdown("---")
        hdr_col, rm_col = st.columns([6, 1])
        with hdr_col:
            if len(fb_ids) > 1:
                st.markdown(f"**Feedback {pos + 1}**")
        with rm_col:
            if len(fb_ids) > 1:
                if st.button("Remove", key=f"fb_rm_{fid}"):
                    st.session_state.feedback_ids = [x for x in fb_ids if x != fid]
                    # clear widget state for removed entry
                    for suffix in ("feature", "rating", "message"):
                        st.session_state.pop(f"fb_{suffix}_{fid}", None)
                    st.rerun()

        st.selectbox(
            "Feature",
            FEEDBACK_FEATURES,
            index=st.session_state.get(f"fb_feature_{fid}", default_idx)
                  if isinstance(st.session_state.get(f"fb_feature_{fid}"), int)
                  else default_idx,
            key=f"fb_feature_{fid}",
            label_visibility="collapsed",
        )

        st.caption("Rating (1 = poor, 5 = excellent)")
        st.radio(
            "Rating",
            [1, 2, 3, 4, 5],
            format_func=str,
            index=(st.session_state.get(f"fb_rating_{fid}", 4) - 1),
            horizontal=True,
            key=f"fb_rating_{fid}",
            label_visibility="collapsed",
        )

        st.text_area(
            "Feedback",
            placeholder="What worked? What was confusing? What would you change?",
            height=100,
            key=f"fb_message_{fid}",
            label_visibility="collapsed",
        )

    add_col, _ = st.columns([2, 5])
    with add_col:
        if st.button("+ Add another feature", key="fb_add"):
            nid = st.session_state.feedback_next_id
            st.session_state.feedback_ids     = fb_ids + [nid]
            st.session_state.feedback_next_id = nid + 1
            st.rerun()

    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)

    if st.button("Submit Feedback", type="primary"):
        # Read all entries from session state widget keys
        fb_ids = st.session_state.feedback_ids
        all_entries = []
        empty_nums  = []
        for pos, fid in enumerate(fb_ids):
            msg = (st.session_state.get(f"fb_message_{fid}") or "").strip()
            if not msg:
                empty_nums.append(str(pos + 1))
            else:
                feat_val = st.session_state.get(f"fb_feature_{fid}")
                feature  = (
                    FEEDBACK_FEATURES[feat_val]
                    if isinstance(feat_val, int)
                    else (feat_val or FEEDBACK_FEATURES[default_idx])
                )
                all_entries.append({
                    "feature": feature,
                    "rating":  st.session_state.get(f"fb_rating_{fid}", 4),
                    "message": msg,
                })
        if empty_nums:
            st.warning(f"Please add a message for feedback {', '.join(empty_nums)}.")
        else:
            errors = []
            uid = get_user_id()
            for e in all_entries:
                try:
                    submit_feedback(feature=e["feature"], message=e["message"],
                                    rating=e["rating"], user_id=uid)
                except Exception as ex:
                    errors.append(str(ex))
            if errors:
                st.error(f"Some entries failed: {errors[0]}")
            else:
                n = len(all_entries)
                st.success(
                    f"{'Feedback' if n == 1 else str(n) + ' entries'} submitted — "
                    "thank you! It goes straight to Nic."
                )
                # Reset form
                for fid in st.session_state.feedback_ids:
                    for suffix in ("feature", "rating", "message"):
                        st.session_state.pop(f"fb_{suffix}_{fid}", None)
                st.session_state.feedback_ids     = [0]
                st.session_state.feedback_next_id = 1
                st.rerun()

    st.divider()
    st.caption(
        "Feedback is private — only the Rho team can see it. "
        "For urgent issues, email nsacramento2@gmail.com."
    )

    # ── Admin panel (only visible to nsacramento2@gmail.com) ──────────────────
    if st.session_state.get("user_email") == "nsacramento2@gmail.com":
        st.divider()
        st.subheader("Admin — All Feedback")

        try:
            from rho.modules.feedback import get_all_feedback
            entries = get_all_feedback(limit=500)
        except Exception as e:
            st.error(f"Could not load feedback: {e}")
            entries = []

        if not entries:
            st.info("No feedback submitted yet.")
        else:
            # Summary stats
            total   = len(entries)
            rated   = [e for e in entries if e.get("rating")]
            avg_rating = round(sum(e["rating"] for e in rated) / len(rated), 1) if rated else None

            s1, s2, s3 = st.columns(3)
            s1.metric("Total submissions", total)
            s2.metric("Avg rating", f"{avg_rating} / 5" if avg_rating else "—")
            s3.metric("Features mentioned", len(set(e["feature"] for e in entries)))

            # CSV download
            import io
            csv_lines = ["Date,Feature,Rating,Message"]
            for e in entries:
                date    = (e.get("created_at") or "")[:10]
                feature = e.get("feature", "").replace(",", ";")
                rating  = str(e.get("rating") or "")
                message = (e.get("message") or "").replace('"', "'").replace("\n", " ")
                csv_lines.append(f'{date},"{feature}",{rating},"{message}"')
            csv_bytes = "\n".join(csv_lines).encode("utf-8")

            st.download_button(
                label="Download all feedback (CSV)",
                data=csv_bytes,
                file_name="rho_feedback.csv",
                mime="text/csv",
                type="primary",
            )

            st.divider()

            # Per-feature breakdown
            from_feature = {}
            for e in entries:
                f = e.get("feature", "Other")
                from_feature.setdefault(f, []).append(e)

            for feature, items in sorted(from_feature.items(),
                                         key=lambda x: -len(x[1])):
                f_ratings = [i["rating"] for i in items if i.get("rating")]
                f_avg = round(sum(f_ratings) / len(f_ratings), 1) if f_ratings else None
                avg_str = f"  ·  avg {f_avg}/5" if f_avg else ""

                with st.expander(f"{feature}  ({len(items)} submissions{avg_str})"):
                    for item in items:
                        date   = (item.get("created_at") or "")[:10]
                        rating = item.get("rating")
                        stars  = ("★" * rating + "☆" * (5 - rating)) if rating else "no rating"
                        st.markdown(
                            f"<div style='padding:8px 0;border-bottom:1px solid #e2e8f0;'>"
                            f"<span style='font-size:11px;color:#94a3b8;'>{date}</span>"
                            f"&nbsp;&nbsp;<span style='color:#b45309;font-size:12px;'>{stars}</span><br/>"
                            f"{item.get('message', '')}"
                            f"</div>",
                            unsafe_allow_html=True,
                        )


# ── User Guide ────────────────────────────────────────────────────────────────

def page_guide():
    st.markdown("## How to Use Rho")
    st.caption("A VFR flight planning co-pilot built for student pilots. "
               "Rho consolidates weather, airspace, communications, and training tracking "
               "into one workflow — from initial brief through post-flight debrief.")
    st.divider()

    steps = [
        ("01", "Set Up Your Profile",
         "Establishes who you are in the system and seeds your default aircraft across all flights.",
         "Go to **Profile**, enter your full name, select your role (student or instructor), "
         "and choose your default aircraft type and tail number. "
         "This information pre-fills your brief forms and ties your training history to your account."),

        ("02", "Run a Pre-Flight Brief",
         "The core of Rho. Pulls live weather, airspace, and comms data for your specific route "
         "so you can make an informed go/no-go decision before you leave the ground.",
         "Go to **Pre-Flight Brief**, select origin and destination airports by state, set your "
         "planned cruise altitude, and choose your aircraft for the flight. "
         "Hit **Generate Brief** to pull live METAR and TAF weather, active SIGMETs and G-AIRMETs, "
         "airspace along your route with penetration warnings, runway and crosswind analysis, "
         "and all tower, ground, ATIS, and UNICOM frequencies for both airports."),

        ("03", "Make Your GO / NO-GO Decision",
         "Keeps the decision authority with you — the pilot in command — while giving you "
         "objective weather data to back it up.",
         "Rho evaluates conditions against VFR student pilot minimums and flags a recommendation: "
         "**GO**, **CAUTION**, or **NO-GO**. Review the full brief, download your kneeboard and "
         "in-flight guide PDFs, then make your call. "
         "Pressing GO creates an active flight record you can complete after landing. "
         "NO-GO archives the brief for your records without starting a flight."),

        ("04", "Complete Your Flight Log",
         "Captures the actual flight for your logbook and builds toward your Part 61.109 "
         "aeronautical experience requirements.",
         "After landing, go to **Flight Log**, find your active flight, and open the debrief form. "
         "Log actual flight time, conditions (day/night, hood, cross-country), takeoffs and landings, "
         "and any notes. Rho updates your running Part 61.109 hour totals automatically."),

        ("05", "Log Your ACS Skills",
         "Tracks training progress task by task so you and your instructor can see where you are "
         "ready and where you still need work.",
         "After each flight, rate yourself on the ACS tasks you practiced — Normal Takeoff, "
         "Steep Turns, Short-Field Landing, and so on — using a 1–4 proficiency scale. "
         "The **ACS Skills** matrix shows every task across every flight as a color-coded grid. "
         "Your instructor can also leave independent ratings per flight via a connected instructor account, "
         "and Rho flags any gaps between your self-ratings and theirs."),
    ]

    for num, title, purpose, instructions in steps:
        col_num, col_body = st.columns([1, 10])
        with col_num:
            st.markdown(
                f"<div style='font-size:1.6rem;font-weight:800;color:#4a6fa5;"
                f"text-align:center;padding-top:0.2rem'>{num}</div>",
                unsafe_allow_html=True)
        with col_body:
            st.markdown(f"**{title}**")
            st.caption(purpose)
            st.markdown(instructions)
        st.divider()

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Kneeboard PDF**")
        st.markdown("Available on the brief page after generating a brief. "
                    "One-page pre-flight summary with weather snapshot, route distance, "
                    "V-speeds for your aircraft, pre-departure checklist, and emergency reference.")
    with c2:
        st.markdown("**In-Flight Guide PDF**")
        st.markdown("Departure communications script, heading and estimated time to destination, "
                    "airspace crossings in route order with class rules, arrival communications, "
                    "and active weather concerns.")

    st.divider()
    st.markdown("**A few things worth knowing**")
    st.markdown(
        "Airport dropdowns load by US state — select a state first, then pick your airport from the list. "
        "Aircraft type is selected per flight at brief time, not fixed to your profile, since many students "
        "train in multiple aircraft. "
        "Instructors connect to student accounts via an invite link generated in the Profile page. "
        "All weather data — METAR, TAF, SIGMET, winds aloft — is fetched live each time you generate a brief."
    )


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
    elif page == "tools":
        page_tools()
    elif page == "feedback":
        page_feedback()
    elif page == "guide":
        page_guide()


if __name__ == "__main__":
    main()
