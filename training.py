"""
Rho — training library: flight PROCEDURES (ACS maneuvers) and TECHNIQUES.

Content follows the FAA Airplane Flying Handbook (FAA-H-8083-3C), the AIM, and
the Private Pilot – Airplane ACS. Standards quoted are Private Pilot ACS
tolerances. Task IDs match acs.py (e.g. "VII-A").

Text may contain aircraft placeholders filled from aircraft.py V-speeds
({vx} {vy} {vg} {va} {vfe} {vs0} {vs1} {vno} {ac}) and from TRAINING_NUMBERS
(power settings, flap speeds, pattern speeds — 172N / 172S so far).
Unknown values -> "(per POH)".

Public API
    PROCEDURES, TECHNIQUES        lists of item dicts
    ITEMS                         {key: item} for both
    fill(text, aircraft)          placeholder substitution
    recommend_for_brief(brief, comms_o, comms_d, layouts)
        -> [{key, airport, reason, level}]   techniques relevant to THIS flight

ALWAYS defer to the aircraft POH and the student's CFI.
"""

# ── Aircraft training numbers (power settings, flap speeds, target speeds) ────
# Typical flight-school numbers. Your school's / CFI's numbers win.
# Keyed by aircraft "model" from aircraft.py. Missing model -> "(per POH)".

TRAINING_NUMBERS = {
    "172N": {
        "sf_entry_rpm": "1,500–1,700 rpm", "sf_hold_rpm": "~2,000 rpm",
        "sf_slow": "60 kt", "sf_target": "55 kt",
        "vfe10": "110 kt", "vfe_full": "85 kt", "flaps_full": "30°",
        "pos_approach": "65 kt", "pon_speed": "55–60 kt",
        "cruise_rpm": "2,300 rpm", "st_speed": "90–95 kt", "gr_speed": "~90 kt",
        "dw_rpm": "2,200 rpm", "dw_speed": "85–90 kt", "abeam_rpm": "1,500 rpm",
        "abeam_speed": "75–80 kt", "base_speed": "70 kt", "final_speed": "65 kt",
        "carb": "Carb heat ON",
    },
    "172S": {
        "sf_entry_rpm": "1,500–1,700 rpm", "sf_hold_rpm": "~2,000 rpm",
        "sf_slow": "60 kt", "sf_target": "55 kt",
        "vfe10": "110 kt", "vfe_full": "85 kt", "flaps_full": "30°",
        "pos_approach": "65 kt", "pon_speed": "55–60 kt",
        "cruise_rpm": "2,400 rpm", "st_speed": "90–95 kt", "gr_speed": "~90 kt",
        "dw_rpm": "2,200 rpm", "dw_speed": "85–90 kt", "abeam_rpm": "1,500 rpm",
        "abeam_speed": "75–80 kt", "base_speed": "70 kt", "final_speed": "65 kt",
        "carb": "Fuel pump/mixture per checklist (fuel injected — no carb heat)",
    },
}


class _Speeds(dict):
    def __missing__(self, k):
        return "(per POH)"


def fill(text, aircraft=None):
    ac = aircraft or {}
    vals = _Speeds()
    for k in ("vx", "vy", "vg", "va", "vfe", "vs0", "vs1", "vno"):
        if ac.get(k):
            vals[k] = f"{ac[k]} kt"
    vals.update(TRAINING_NUMBERS.get(ac.get("model") or "", {}))
    if "carb" not in vals:
        vals["carb"] = "Carb heat ON (if carbureted)"
    vals["ac"] = ac.get("display") or "your aircraft"
    try:
        return text.format_map(vals)
    except (ValueError, IndexError, KeyError):
        return text


def has_numbers(aircraft):
    """True when the library has specific power/flap numbers for this aircraft."""
    return bool(aircraft) and (aircraft.get("model") in TRAINING_NUMBERS)


def all_text(item):
    """Every string in an item (for search)."""
    out = [item.get("title", ""), item.get("summary", ""), item.get("why", "")]
    for k in ("setup", "steps", "recovery", "standards", "errors", "watch"):
        out += item.get(k) or []
    for _, steps in item.get("phases") or []:
        out += steps
    return " ".join(out)


# ── Shared snippets ───────────────────────────────────────────────────────────

_CLEAR = "Clearing turns"
_BUG = "Choose / bug heading + altitude (recover ≥ 1,500 ft AGL)"
_STALL_RECOVER = [
    "Nose down — reduce angle of attack (horn/buffet stops)",
    "Wings level — coordinated aileron + rudder",
    "Full power, carb heat OFF — right rudder",
    "Pitch for climb: Vx {vx} / Vy {vy}",
    "Flaps up in steps (20° → 10° → 0°) after positive rate",
    "Return to altitude + heading",
]


# ══════════════════════════════════════════════════════════════════════════════
# PROCEDURES — ACS maneuvers (punchy step-by-step)
# ══════════════════════════════════════════════════════════════════════════════

PROCEDURES = [
    {
        "key": "slow_flight",
        "title": "Slow Flight",
        "acs": "VII-A",
        "summary": "Fly just above the stall warning. Pitch = airspeed, power = altitude.",
        "steps": [
            _CLEAR,
            _BUG,
            "{carb}",
            "Power {sf_entry_rpm}",
            "Slight back pressure — hold altitude",
            "Flaps 10° below {vfe10}",
            "Flaps 20° below {vfe_full}",
            "Flaps {flaps_full} below {vfe_full}",
            "Airspeed to {sf_slow}",
            "Add power to {sf_hold_rpm}",
            "Final speed {sf_target} — right rudder, ball centered",
            "Fly straight, turns, climbs, descents as assigned",
        ],
        "recovery": [
            "Full power, carb heat OFF",
            "Nose down to hold altitude as speed builds",
            "Flaps up in steps (20° → 10° → 0°)",
            "Cruise power, trim",
        ],
        "standards": ["Altitude ±100 ft", "Heading ±10°", "Airspeed +10 / −0 kt", "Bank ±10°",
                      "No stall horn"],
        "watch": ["Stall horn = too slow", "Losing altitude while slowing", "Not enough right rudder"],
        "source": "Airplane Flying Handbook — Slow flight",
    },
    {
        "key": "power_off_stall",
        "title": "Power-Off Stall (approach to landing)",
        "acs": "VII-B",
        "summary": "Stall in landing configuration — like the flare or base-to-final.",
        "steps": [
            _CLEAR,
            _BUG,
            "{carb}",
            "Power {sf_entry_rpm} — hold altitude",
            "Flaps 10° below {vfe10}",
            "Flaps 20° → {flaps_full} below {vfe_full}",
            "At {pos_approach}: pitch for a stabilized descent",
            "Power IDLE",
            "Raise nose smoothly to landing attitude — hold heading (or ≤ 20° bank)",
            "Hold it: horn → buffet → break",
        ],
        "recovery": _STALL_RECOVER,
        "standards": ["Heading ±10° / bank ±10° (≤ 20°)", "Recover promptly after the stall",
                      "Recover ≥ 1,500 ft AGL", "No secondary stall or spin"],
        "watch": ["Power before nose down", "Pulling up too fast → secondary stall",
                  "All flaps up at once → sink"],
        "source": "Airplane Flying Handbook — Stalls",
    },
    {
        "key": "power_on_stall",
        "title": "Power-On Stall (departure)",
        "acs": "VII-C",
        "summary": "Stall in takeoff configuration with climb power — like pulling too hard after takeoff.",
        "steps": [
            _CLEAR,
            _BUG,
            "Power {sf_entry_rpm} — hold altitude",
            "Flaps as for takeoff (usually 0°–10°)",
            "Slow to {pon_speed} (liftoff speed)",
            "Full power (at least 65%)",
            "Pitch up smoothly (~15–20° nose up)",
            "Lots of right rudder — ball centered",
            "Hold heading (or ≤ 20° bank) until the break",
        ],
        "recovery": _STALL_RECOVER,
        "standards": ["Heading ±10° / bank ±10° (≤ 20°)", "Power ≥ 65%",
                      "Recover promptly after the stall", "Recover ≥ 1,500 ft AGL"],
        "watch": ["Left wing drops — not enough right rudder", "Pitch way too high"],
        "source": "Airplane Flying Handbook — Stalls",
    },
    {
        "key": "steep_turns",
        "title": "Steep Turns",
        "acs": "V-A",
        "summary": "360° at 45° bank each way, holding altitude.",
        "steps": [
            _CLEAR,
            _BUG,
            "Power {cruise_rpm} — airspeed {st_speed} (at or below Va {va})",
            "Pick a landmark on the entry heading",
            "Roll into 45° bank",
            "Passing 30°: add back pressure + ~100 rpm",
            "Hold the sight picture — nose on the horizon",
            "Lead rollout by ~20°",
            "Roll out: release back pressure, power back",
            "Roll straight into the turn the other way",
        ],
        "standards": ["Bank 45° ±5°", "Altitude ±100 ft", "Airspeed ±10 kt", "Rollout heading ±10°"],
        "watch": ["Sinking in the first 90°", "Bank creeping past 45°", "Ballooning on rollout"],
        "source": "Airplane Flying Handbook — Performance maneuvers",
    },
    {
        "key": "ground_reference",
        "title": "Ground Reference Maneuvers",
        "acs": "V-B",
        "summary": "Rectangular course, S-turns, turns around a point — fly a ground track in wind.",
        "steps": [
            "Pick a reference (field, road, or point) with a landing spot nearby",
            "Clearing turn",
            "Altitude 600–1,000 ft AGL",
            "Power {cruise_rpm} — {gr_speed}",
            "Find the wind",
            "Enter downwind (45° to downwind for the rectangle)",
            "Steepest bank downwind, shallowest upwind (max 45°)",
            "Crab on straight legs",
            "Eyes outside — glance at altimeter",
        ],
        "standards": ["Altitude 600–1,000 AGL, ±100 ft", "Airspeed ±10 kt", "Correct for wind drift"],
        "watch": ["Constant bank (track drifts)", "Altitude creep while looking down", "Towers & wires"],
        "source": "Airplane Flying Handbook — Ground reference maneuvers",
    },
    {
        "key": "pattern_practice",
        "title": "Pattern Practice (takeoffs & landings)",
        "acs": "III-B",
        "summary": "The traffic pattern, leg by leg — power, flaps, speeds, calls.",
        "phases": [
            ("Departure / upwind", [
                "Takeoff — climb at Vy {vy}",
                "Past the runway end, within 300 ft of pattern altitude: turn crosswind",
                "Level at pattern altitude (usually 1,000 ft AGL — check Chart Supplement)",
                "Power {dw_rpm} — {dw_speed}",
            ]),
            ("Downwind", [
                "About ½ mile from the runway, parallel to it",
                "Before-landing checklist",
                "Call: \"___ traffic, N___, left downwind runway __\"",
            ]),
            ("Abeam the numbers", [
                "{carb}",
                "Power {abeam_rpm}",
                "Flaps 10° below {vfe10}",
                "Pitch for {abeam_speed} — start descent",
            ]),
            ("Base (runway 45° behind you)", [
                "Turn base — call it",
                "Flaps 20° below {vfe_full}",
                "{base_speed}",
            ]),
            ("Final", [
                "Turn final — call it",
                "Flaps {flaps_full}",
                "{final_speed} — pick your aim point",
                "Stabilized by 300 ft AGL or GO AROUND",
                "Over the fence: power idle, flare, mains first",
            ]),
            ("Touch-and-go (only if your CFI approves)", [
                "Stay on centerline — flaps UP, carb heat OFF",
                "Full power — rotate, Vy {vy}",
            ]),
        ],
        "standards": ["Pattern altitude ±100 ft", "Airspeed ±10 kt",
                      "Approach speed +10 / −5 kt", "Touchdown within 400 ft of the point"],
        "watch": ["Overshooting base-to-final — never skid it around with rudder",
                  "Rushed checklist", "Unstable approach — go around"],
        "source": "AIM 4-3-3; Airplane Flying Handbook — Approaches and landings",
    },
    {
        "key": "emergency_landing",
        "title": "Emergency Approach & Landing (engine failure)",
        "acs": "IX-B",
        "summary": "A-B-C-D-E. Fly the airplane first.",
        "steps": [
            "**A**irspeed — best glide {vg}, trim",
            "**B**est field — into the wind, within glide range, turn toward it",
            "**C**hecklist — fuel BOTH, mixture RICH, carb heat ON, primer IN & locked, mags BOTH / try L-R",
            "**D**eclare — 121.5, \"MAYDAY ×3\", squawk 7700",
            "**E**xecute — fly a pattern to the field, aim ⅓ in, flaps when it's made",
            "Before touchdown: mixture CUTOFF, fuel OFF, mags OFF, master OFF (after flaps), doors unlatched",
            "Right after takeoff? Nose down, land ahead (±30°) — no turnback",
        ],
        "standards": ["Best glide ±10 kt", "Field within gliding distance", "Plan and fly a pattern",
                      "Checklists complete"],
        "watch": ["Late best glide", "Stretching the glide", "Field behind you"],
        "source": "Airplane Flying Handbook — Emergency procedures",
    },
    {
        "key": "emergency_descent",
        "title": "Emergency Descent",
        "acs": "IX-A",
        "summary": "Get down fast — fire, smoke, or medical.",
        "steps": [
            "Clear below",
            "Power IDLE, {carb}",
            "Roll into 30–45° bank",
            "Nose down — speed ≤ Vno {vno} (≤ Va {va} if bumpy)",
            "Flaps only below Vfe {vfe}, per POH",
            "Roll out, level off at target altitude",
        ],
        "standards": ["Airspeed +0 / −10 kt", "Level off ±100 ft"],
        "watch": ["Overspeeding Vno / Vfe", "Bank too shallow"],
        "source": "Airplane Flying Handbook — Emergency procedures",
    },
    {
        "key": "spin_awareness",
        "title": "Spin Awareness",
        "acs": "VII-D",
        "summary": "Spin = stall + yaw. Stay coordinated. Recovery: PARE.",
        "steps": [
            "**P**ower — IDLE",
            "**A**ilerons — NEUTRAL",
            "**R**udder — FULL opposite the rotation",
            "**E**levator — briskly FORWARD",
            "Rotation stops: rudder neutral, wings level, ease out of the dive",
        ],
        "standards": ["Explain causes, situations, and recovery (knowledge task)"],
        "watch": ["Skidding base-to-final", "Aileron to lift a dropping wing in a stall"],
        "source": "Airplane Flying Handbook — Spins",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TECHNIQUES — takeoffs, landings, and situational skills
# ══════════════════════════════════════════════════════════════════════════════

TECHNIQUES = [
    {
        "key": "vfr_minimums",
        "kind": "vfr_mins",          # custom renderer: diagram + table
        "title": "VFR Weather Minimums by Airspace",
        "acs": "I-E",
        "summary": "Visibility and cloud clearance for each class of airspace (14 CFR 91.155).",
        "why": "Cloud clearance is what keeps you visible to IFR traffic descending out of the clouds — "
               "and keeps you out of the clouds yourself.",
        "steps": ["Class B: 3 sm, clear of clouds",
                  "Class C, D, E below 10,000: 3 sm, 500 below, 1,000 above, 2,000 horizontal (3-152)",
                  "Class E at/above 10,000: 5 sm, 1,000 below, 1,000 above, 1 sm horizontal",
                  "Class G ≤ 1,200 AGL day: 1 sm, clear of clouds",
                  "Surface areas: 1,000 ft ceiling and 3 sm to enter the pattern",
                  "Student solo: 3 sm day, 5 sm night (61.89)"],
        "standards": ["Explain VFR weather minimums for each class of airspace"],
        "source": "14 CFR 91.155; 14 CFR 61.89; AIM 3-1-4",
    },
    {
        "key": "crosswind_takeoff",
        "title": "Crosswind Takeoff",
        "acs": "IV-G",
        "summary": "Hold the upwind wing down, track the centerline, then crab after liftoff.",
        "why": "A crosswind tries to lift the upwind wing and weathervane the airplane into the wind.",
        "setup": ["Find the crosswind component — Rho's brief shows it for the favored runway.",
                  "Check your POH's maximum demonstrated crosswind."],
        "steps": [
            "Taxi into position on the centerline. **Full aileron into the wind** (control wheel turned "
            "toward the wind).",
            "Apply full power smoothly; use rudder to track the centerline (left rudder may be needed to "
            "stop weathervaning on a right crosswind, and vice versa).",
            "As speed builds and ailerons become effective, **gradually reduce** the aileron input — "
            "just enough to keep the wings level.",
            "Rotate positively at Vr so the airplane doesn't skip sideways on the runway.",
            "Once airborne, turn slightly into the wind (crab) to track the extended centerline; "
            "level the wings and climb at Vy {vy}.",
        ],
        "standards": ["Maintain centerline", "Correct for wind drift", "Vy +10/−5 kt in the climb"],
        "errors": ["Releasing aileron input too early → upwind wing lifts",
                   "Not enough aileron at the start of the roll",
                   "Drifting downwind after liftoff (no crab)"],
        "safety": "If you can't hold the centerline early in the roll, abort — power idle, brakes.",
        "source": "Airplane Flying Handbook — Takeoffs and Departure Climbs",
    },
    {
        "key": "crosswind_landing",
        "title": "Crosswind Landing",
        "acs": "IV-B",
        "summary": "Crab on final, then wing-low (sideslip) to touch down aligned with the centerline.",
        "why": "Touching down while drifting sideways side-loads the gear and can cause a ground loop "
               "or runway excursion.",
        "setup": ["Know the crosswind component and which side it's from (Rho's brief shows it).",
                  "If gusty, add half the gust factor to your approach speed."],
        "steps": [
            "On final, crab (turn into the wind) to track the extended centerline.",
            "Before the flare — usually on short final — transition to the **wing-low method**: "
            "lower the upwind wing with aileron, and use **opposite rudder** to align the nose with the "
            "centerline.",
            "Adjust: aileron controls drift (more bank = less drift); rudder keeps the nose straight.",
            "Hold the sideslip through the flare. Touch down on the **upwind main wheel first**, "
            "then the other main, then the nosewheel.",
            "During rollout, keep adding aileron into the wind as you slow (full deflection by the end). "
            "Use rudder for the centerline.",
        ],
        "standards": ["No drift, longitudinal axis aligned with the runway at touchdown",
                      "Approach speed +10/−5 kt", "Touch down within 400 ft beyond the specified point"],
        "errors": ["Touching down in a crab (side load)", "Releasing aileron after touchdown",
                   "Flaring with crossed controls but letting the nose swing",
                   "Starting the sideslip too high and running out of rudder/aileron"],
        "safety": "If full rudder can't keep the nose straight, the crosswind is too strong for you — "
                  "go around and pick a runway more into the wind.",
        "source": "Airplane Flying Handbook — Approaches and Landings (crosswind)",
    },
    {
        "key": "gusty_wind",
        "title": "Gusty Wind Approach & Landing",
        "acs": "IV-B",
        "summary": "Add half the gust factor to approach speed; fly the airplane onto the runway.",
        "why": "Gusts can suddenly drop airspeed close to the stall on short final.",
        "setup": ["Gust factor = gust − steady wind. Example: 12G20 → 8 kt gust factor → add 4 kt."],
        "steps": [
            "Fly your normal approach speed + ½ the gust factor.",
            "Consider less flap than normal if your POH/CFI recommends it — easier control in gusts.",
            "Expect to work the controls; keep the wings level and the airplane on the centerline.",
            "Minimize float: fly it onto the runway at a slightly flatter attitude rather than holding off.",
            "Once down, hold aileron into the wind and stay on the controls until you've stopped.",
        ],
        "standards": ["Approach speed +10/−5 kt (of the gust-adjusted target)", "Stabilized approach"],
        "errors": ["Chasing every gust with big inputs", "Floating long with extra speed",
                   "Relaxing after touchdown"],
        "safety": "Wind above your personal minimums? It's fine to divert or wait.",
        "source": "Airplane Flying Handbook — Approaches and Landings (turbulent air)",
    },
    {
        "key": "short_field_takeoff",
        "title": "Short-Field Takeoff & Max Performance Climb",
        "acs": "IV-E",
        "summary": "Use all the runway, full power on the brakes, Vx until clear of the obstacle.",
        "why": "Short runways and obstacles at the end leave no margin for a sloppy takeoff.",
        "setup": ["Check takeoff distance (ground roll and over a 50-ft obstacle) in the POH for today's "
                  "density altitude and weight.",
                  "Flaps as your POH specifies for short-field takeoff."],
        "steps": [
            "Taxi to the very beginning of the runway; line up on the centerline.",
            "Hold the brakes, apply full power, check engine instruments, then release brakes.",
            "Hold a slightly nose-low attitude for acceleration; don't raise the nose early.",
            "Rotate at the POH short-field rotation speed and climb at **Vx {vx}** until the obstacle is "
            "cleared (or 50 ft AGL).",
            "Then lower the nose to **Vy {vy}**, and retract flaps in increments.",
        ],
        "standards": ["Vx +10/−5 kt until obstacle cleared or 50 ft AGL", "Then Vy +10/−5 kt"],
        "errors": ["Not using all available runway", "Rotating early (more drag, slower acceleration)",
                   "Letting airspeed drop below Vx in the climb"],
        "safety": "Pick an abort point: if you're not at ~70% of rotation speed by ~50% of the runway, abort.",
        "source": "Airplane Flying Handbook — Takeoffs and Departure Climbs (short-field)",
    },
    {
        "key": "short_field_landing",
        "title": "Short-Field Approach & Landing",
        "acs": "IV-F",
        "summary": "Stabilized, precise-speed approach; touch down on the point; maximum braking.",
        "why": "When runway is limited, every extra knot means hundreds of feet of float.",
        "setup": ["Check landing distance in the POH.", "Full flaps (or as POH specifies)."],
        "steps": [
            "Fly a stabilized approach at the POH short-field approach speed — no faster.",
            "Use power to control the descent rate and pitch to hold speed. Aim at a point slightly "
            "before your touchdown point.",
            "Reduce power smoothly in the flare; minimal float. Touch down at minimum controllable airspeed.",
            "After touchdown: lower the nose, retract flaps (if your POH recommends — more weight on the "
            "wheels), and apply maximum braking without skidding.",
        ],
        "standards": ["Approach speed +10/−5 kt", "Touch down within 200 ft beyond (or on) the specified point",
                      "Stop in the shortest distance consistent with safety"],
        "errors": ["Too fast on final → long float", "Unstable approach chasing the glidepath",
                   "Retracting the wrong lever (gear vs flaps in retractables)"],
        "safety": "Not stabilized by 300–500 ft AGL? Go around.",
        "source": "Airplane Flying Handbook — Approaches and Landings (short-field)",
    },
    {
        "key": "soft_field_takeoff",
        "title": "Soft-Field Takeoff & Climb",
        "acs": "IV-C",
        "summary": "Keep moving, nosewheel light, lift off early and accelerate in ground effect.",
        "why": "Grass, mud, sand, or snow create drag and can dig in the nosewheel.",
        "setup": ["Flaps as your POH specifies for soft-field takeoff.",
                  "Do the run-up on a firm spot if possible."],
        "steps": [
            "Taxi with full back elevator; **don't stop** on the soft surface — roll onto the runway and "
            "into the takeoff with smooth power.",
            "Hold back pressure to get the nosewheel off the surface early; then ease it so the nose "
            "doesn't rise too high.",
            "Lift off at the lowest possible airspeed, then **lower the nose slightly to stay in ground "
            "effect** while accelerating.",
            "At Vx {vx} (obstacle) or Vy {vy}, climb out; retract flaps in increments.",
        ],
        "standards": ["Vx or Vy +10/−5 kt in the climb", "Accelerate in ground effect"],
        "errors": ["Stopping on the soft surface", "Climbing out of ground effect too slowly → settling back",
                   "Too much nose-up → tail strike / high drag"],
        "safety": "Check the field condition and NOTAMs; tall wet grass can more than double the takeoff roll.",
        "source": "Airplane Flying Handbook — Takeoffs and Departure Climbs (soft-field)",
    },
    {
        "key": "soft_field_landing",
        "title": "Soft-Field Approach & Landing",
        "acs": "IV-D",
        "summary": "Touch down as softly and slowly as possible; keep the nosewheel off.",
        "why": "Reduces the load on the nosewheel so it doesn't dig in.",
        "setup": ["Full flaps (or as POH specifies)."],
        "steps": [
            "Normal stabilized approach at POH approach speed.",
            "In the flare, add a little power to slow the descent and touch down gently at the "
            "lowest possible speed, nose high.",
            "Hold back elevator to keep the nosewheel off; let it down gently.",
            "Keep some power and full back elevator while taxiing — don't stop on the soft surface.",
        ],
        "standards": ["Approach speed +10/−5 kt", "Touch down softly with minimum descent rate and groundspeed",
                      "Maintain back pressure and keep moving after touchdown"],
        "errors": ["Letting the nose drop quickly after touchdown", "Braking on a soft surface"],
        "safety": "Verify the runway surface first (Chart Supplement / call the FBO).",
        "source": "Airplane Flying Handbook — Approaches and Landings (soft-field)",
    },
    {
        "key": "forward_slip",
        "title": "Forward Slip to a Landing",
        "acs": "IV-H",
        "summary": "Cross the controls to lose altitude fast without gaining airspeed.",
        "why": "Fixes a too-high approach, and is essential if you have no flaps.",
        "setup": ["Some POHs (including many Cessna 172s) advise avoiding steep slips with more than "
                  "20° of flaps — check yours."],
        "steps": [
            "Power to idle.",
            "Lower one wing (the upwind wing if there's a crosswind) with aileron.",
            "Apply **opposite rudder** so the airplane keeps tracking the runway — the nose points off "
            "to the side.",
            "Lower the nose as needed to hold your approach airspeed (the airspeed indicator may read "
            "inaccurately in a slip).",
            "Recover before the flare: level the wings and neutralize rudder smoothly, so you touch down "
            "aligned and without drift.",
        ],
        "standards": ["Touch down within 400 ft beyond (or on) the specified point",
                      "No drift, aligned with the runway", "Smooth transition out of the slip"],
        "errors": ["Letting airspeed build or decay", "Releasing the slip abruptly near the ground",
                   "Not enough rudder to hold the track"],
        "safety": "Still too high after slipping? Go around.",
        "source": "Airplane Flying Handbook — Approaches and Landings (slips)",
    },
    {
        "key": "go_around",
        "title": "Go-Around / Rejected Landing",
        "acs": "IV-I",
        "summary": "Power up, pitch up, clean up — and fly the airplane.",
        "why": "Every unstable approach, runway incursion, or bad bounce has the same fix: go around early.",
        "setup": ["Decide before every approach: \"If I'm not stabilized by ___ ft, I go around.\""],
        "steps": [
            "**Power:** full power, carb heat off (if equipped). Right rudder.",
            "**Pitch:** raise the nose to a climb attitude; stop the descent. Expect strong nose-up "
            "trim forces — push and re-trim.",
            "**Flaps:** retract to the first increment (e.g. 20° in many 172s) right away, then the rest "
            "gradually once climbing above Vx {vx} / at Vy {vy}.",
            "Side-step to the side of the runway (usually the right of traffic) to see traffic that may "
            "be departing below you.",
            "Communicate: \"going around\" on CTAF / tell tower.",
        ],
        "standards": ["Make a timely decision", "Apply takeoff power and attain the proper pitch attitude",
                      "Retract flaps as appropriate", "Vy +10/−5 kt", "Maintain the runway track or side-step"],
        "errors": ["Waiting too long to decide", "Retracting all flaps at once → sink",
                   "Not enough right rudder / forward pressure"],
        "safety": "A go-around is never a failure. It's the safest option on a bad approach.",
        "source": "Airplane Flying Handbook — Approaches and Landings (go-arounds)",
    },
    {
        "key": "pattern_entry",
        "title": "Non-Towered Airport Pattern Entry",
        "acs": "III-B",
        "summary": "Self-announce, enter on the 45° to downwind at pattern altitude.",
        "why": "There's no controller — traffic separation depends on everyone flying a predictable pattern.",
        "setup": ["Check the Chart Supplement for pattern altitude (typically 1,000 ft AGL), "
                  "pattern direction (left unless noted), and CTAF.",
                  "Listen to AWOS/ASOS ~15 nm out; set altimeter; choose the runway most into the wind."],
        "steps": [
            "~10 nm out: announce position, altitude, and intentions on CTAF.",
            "Descend to pattern altitude well before entering.",
            "Enter on a **45° angle to the downwind leg at midfield**, at pattern altitude.",
            "Announce: entering downwind, base, final, and clear of the runway.",
            "If you arrive on the wrong side, cross well above pattern altitude (or overfly midfield per "
            "AC 90-66 / your CFI), then set up for the 45°.",
            "Straight-in approaches are allowed but don't take priority over traffic in the pattern.",
        ],
        "standards": ["Comply with traffic pattern procedures", "Maintain proper spacing",
                      "Correct for wind drift", "Maintain pattern altitude ±100 ft, airspeed ±10 kt"],
        "errors": ["Not listening before talking", "Entering at the wrong altitude",
                   "Turning base or final into opposite traffic", "Forgetting to look — radios are optional"],
        "safety": "Not all aircraft have radios. Eyes outside, lights on.",
        "source": "AC 90-66 (Non-Towered Airport Flight Operations); AIM 4-1-9",
    },
    {
        "key": "wake_turbulence",
        "title": "Wake Turbulence Avoidance",
        "acs": None,
        "summary": "Stay above and upwind of a larger aircraft's flight path.",
        "why": "Wingtip vortices from airliners and business jets can roll a small airplane beyond its "
               "control authority.",
        "setup": ["Vortices sink several hundred feet per minute, tend to level off roughly 900 ft "
                  "below the generating aircraft's path, and drift with the wind. A light quartering tailwind is the worst case — vortices linger "
                  "on the runway."],
        "steps": [
            "**Landing behind a larger aircraft:** stay at or above its approach path and land "
            "**beyond** its touchdown point.",
            "**Taking off behind a larger aircraft:** rotate **before** its rotation point and climb "
            "above its path, or wait. ATC uses 2–3 minute intervals — you can request more time.",
            "**Crossing behind:** cross above its flight path, never below.",
            "If you encounter wake: go around / escape upwind; don't fight the roll with abrupt control.",
        ],
        "standards": ["Apply wake turbulence avoidance procedures"],
        "errors": ["Assuming a 'cleared for takeoff' means wake is not a factor",
                   "Landing short of a heavy's touchdown point"],
        "safety": "You can always say \"Request delay for wake turbulence.\"",
        "source": "AIM 7-4 (Wake Turbulence)",
    },
    {
        "key": "density_altitude",
        "title": "High Density Altitude Operations",
        "acs": "I-F",
        "summary": "Hot, high, or humid → longer takeoff roll, weaker climb.",
        "why": "The airplane performs as if the airport were thousands of feet higher.",
        "setup": ["Density altitude ≈ pressure altitude + 120 ft × (OAT − ISA temp). Rho computes it in "
                  "the brief when it's significant."],
        "steps": [
            "Use the POH performance charts (takeoff distance and climb rate) for today's DA and weight — "
            "don't guess.",
            "Lean the mixture for best power at run-up if your POH allows at high DA.",
            "Expect a longer ground roll and lower climb rate; plan an abort point.",
            "Reduce weight (fuel/passengers/baggage) if margins are thin.",
            "Fly early in the morning when it's cooler.",
            "True airspeed is higher than indicated — groundspeed on landing will feel fast. Fly the "
            "normal indicated approach speed.",
        ],
        "standards": ["Compute and apply aircraft performance for conditions"],
        "errors": ["Using sea-level numbers on a hot day", "Rotating early to 'help' it fly"],
        "safety": "If the numbers don't work with a healthy margin, don't go.",
        "source": "Pilot's Handbook of Aeronautical Knowledge — Aircraft Performance",
    },
    {
        "key": "inadvertent_imc",
        "title": "Inadvertent Flight into Clouds (VFR into IMC)",
        "acs": "VIII-D",
        "summary": "Trust the instruments, wings level, 180° turn back to VFR.",
        "why": "Low ceilings and haze can trap you between clouds and terrain. Spatial disorientation "
               "can set in within seconds.",
        "setup": ["Prevention: have personal minimums, check the TAF, and turn around early "
                  "when it's getting worse — don't 'scud run'."],
        "steps": [
            "**Recognize and commit** — you're on instruments now. Ignore your body's sensations.",
            "**Wings level** on the attitude indicator; hold altitude; note your heading.",
            "Make a **standard-rate 180° turn** (about 15° bank at training speeds) back to where it was VFR. "
            "Use a timer: 1 minute.",
            "Climb if needed to clear terrain/obstacles — never descend into unknown terrain.",
            "Ask for help: ATC or 121.5. Squawk 7700 if you're in trouble. Say what's happening.",
        ],
        "standards": ["Recover from unusual attitudes using instruments",
                      "Maintain control solely by reference to instruments"],
        "errors": ["Delaying the decision", "Steep turns in cloud (graveyard spiral)",
                   "Looking outside for references that aren't there"],
        "safety": "Your CFI's hood work is training for exactly this. The best fix is never entering cloud.",
        "source": "Airplane Flying Handbook — Emergency Procedures (inadvertent IMC)",
    },
    {
        "key": "lost_procedures",
        "title": "Lost Procedures",
        "acs": "VI-D",
        "summary": "Climb, Communicate, Confess, Comply, Conserve.",
        "why": "Getting disoriented is normal; staying lost is optional.",
        "setup": ["Keep your sectional and nav log open; note checkpoint times."],
        "steps": [
            "**Climb** — better radio and radar coverage, and you see more landmarks.",
            "**Communicate** — call the nearest facility or Flight Service; use GPS / VOR to fix position.",
            "**Confess** — tell ATC you're unsure of your position. They help every day.",
            "**Comply** — follow their instructions; squawk as assigned.",
            "**Conserve** — reduce power to economy cruise; watch fuel.",
            "Pilotage: compare big features (water, highways, cities) on the sectional to what you see. "
            "Fly toward a large catch feature if needed.",
        ],
        "standards": ["Select an appropriate course of action", "Maintain altitude and situational awareness"],
        "errors": ["Wandering without a plan", "Waiting too long to ask for help"],
        "safety": "Fuel is the hard limit — decide early.",
        "source": "Pilot's Handbook of Aeronautical Knowledge — Navigation",
    },
]

ITEMS = {i["key"]: i for i in PROCEDURES + TECHNIQUES}
PROCEDURE_KEYS = {i["key"] for i in PROCEDURES}


# ══════════════════════════════════════════════════════════════════════════════
# Brief recommender
# ══════════════════════════════════════════════════════════════════════════════

_SOFT_SURFACES = ("turf", "grass", "gras", "dirt", "grav", "grvl", "sand", "soil", "snow", "water")


def _density_altitude(elev_ft, altim_inhg, oat_c):
    try:
        pa = float(elev_ft) + (29.92 - float(altim_inhg)) * 1000
        isa = 15 - 2 * pa / 1000
        return round(pa + 120 * (float(oat_c) - isa))
    except (TypeError, ValueError):
        return None


def _active_runway(layout, active):
    if not (layout and active):
        return None
    for rw in layout.get("runways") or []:
        if rw.get("designator") == active.get("designator"):
            return rw
    return None


def recommend_for_brief(brief, comms_o=None, comms_d=None, layouts=None):
    """
    Return techniques relevant to THIS flight, most important first:
        [{key, airport, reason, level}]   level: "key" | "standard"
    layouts: {icao: (layout, active)} from airport_diagram (optional).
    """
    layouts = layouts or {}
    recs = []
    seen = set()

    def add(key, airport, reason, level="key"):
        tag = (key, airport)
        if tag in seen or key not in ITEMS:
            return
        seen.add(tag)
        recs.append({"key": key, "airport": airport, "reason": reason, "level": level})

    origin, dest = brief.get("origin_icao"), brief.get("dest_icao")
    legs = [
        ("DEP", origin, brief.get("origin_apt") or {}, brief.get("origin_assess") or {}, comms_o or {}),
        ("ARR", dest,   brief.get("dest_apt") or {},   brief.get("dest_assess") or {},   comms_d or {}),
    ]

    for role, icao, apt, a, c in legs:
        layout, active = layouts.get(icao, (None, None))
        wind = a.get("wind_kt") or 0
        gust = a.get("wind_gust_kt")

        # Crosswind
        xw = active.get("crosswind") if active else a.get("crosswind_kt")
        side = (active or {}).get("side")
        rwy = (active or {}).get("ident") or a.get("best_runway") or "favored runway"
        if xw is not None and xw >= 5:
            side_s = f" from the {'right' if side == 'R' else 'left'}" if side else ""
            msg = f"~{xw:.0f} kt crosswind{side_s} on Rwy {rwy}"
            if xw > 10:
                msg += " — above the 10 kt student threshold"
            add("crosswind_takeoff" if role == "DEP" else "crosswind_landing", icao, msg)

        # Tailwind on the only usable runway
        if active and (active.get("headwind") or 0) < -2:
            add("go_around", icao,
                f"Tailwind of ~{abs(active['headwind']):.0f} kt on the favored runway — expect a long float")

        # Gusts
        if gust and gust - wind >= 5:
            add("gusty_wind", icao,
                f"Wind {wind} gusting {gust} kt — add ~{round((gust - wind) / 2)} kt to approach speed")

        # Short / soft field
        rw = _active_runway(layout, active)
        length = (rw or {}).get("length_ft") or (active or {}).get("length_ft")
        if not length:
            lens = [r.get("length_ft") for r in (apt.get("runways") or []) if r.get("length_ft")]
            length = max(lens) if lens else None
        if length and length < 3000:
            add("short_field_takeoff" if role == "DEP" else "short_field_landing", icao,
                f"Runway is only {length:,} ft — check POH distances")
        surface = ((rw or {}).get("surface") or "").lower()
        if not surface:
            surfs = [(r.get("surface") or "").lower() for r in (apt.get("runways") or [])]
            surface = surfs[0] if surfs else ""
        if any(s in surface for s in _SOFT_SURFACES):
            add("soft_field_takeoff" if role == "DEP" else "soft_field_landing", icao,
                f"{surface.title()} runway surface")

        # Density altitude
        da = _density_altitude(apt.get("elevation_ft"), a.get("altimeter"), a.get("temp_c"))
        if da is not None and (da >= 2000 or da - (apt.get("elevation_ft") or 0) >= 2000) \
                and not any(r["key"] == "density_altitude" for r in recs):
            add("density_altitude", icao,
                f"Density altitude ~{da:,} ft (field elev {apt.get('elevation_ft') or 0:,} ft) — "
                "longer takeoff roll, weaker climb")

        # Wake turbulence at airports with approach control + tower (jets likely)
        if c.get("has_tower") and c.get("approach"):
            add("wake_turbulence", icao,
                "Towered airport inside Class B/C airspace — expect jets and turboprops", level="standard")

        # Non-towered arrival
        if role == "ARR" and not c.get("has_tower"):
            add("pattern_entry", icao,
                f"Non-towered — self-announce on CTAF {c.get('ctaf') or c.get('unicom') or ''}".strip(),
                level="standard")

    # Low ceilings / visibility anywhere → inadvertent IMC
    for f in brief.get("factors") or []:
        if f.get("type") in ("Low ceiling", "Low visibility", "Fog", "Thunderstorm", "Fog risk") \
                and f.get("level") in ("CAUTION", "NO-GO", "NOTE"):
            add("inadvertent_imc", f.get("airport") or "Route",
                f"{f.get('short', f.get('type'))} — know your escape plan", level="key"
                if f.get("level") != "NOTE" else "standard")
            break

    # VFR weather minimums problems (pattern clearance, cruise vs ceiling)
    for f in brief.get("factors") or []:
        if f.get("type") == "VFR minimums":
            add("vfr_minimums", f.get("airport") or "Route", f.get("short", "VFR minimums"), level="key")
            break

    # Always relevant on any landing
    add("go_around", dest, "Every landing — decide your go-around gate before the approach",
        level="standard")

    recs.sort(key=lambda r: 0 if r["level"] == "key" else 1)
    return recs
