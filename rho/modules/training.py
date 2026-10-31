"""
Rho — training library: flight PROCEDURES (ACS maneuvers) and TECHNIQUES.

Content follows the FAA Airplane Flying Handbook (FAA-H-8083-3C), the AIM, and
the Private Pilot – Airplane ACS. Standards quoted are Private Pilot ACS
tolerances. Task IDs match acs.py (e.g. "VII-A").

Text may contain aircraft placeholders that are filled from aircraft.py:
    {vx} {vy} {vg} {va} {vfe} {vs0} {vs1} {vno} {ac}
Unknown aircraft -> "POH" wording.

Public API
    PROCEDURES, TECHNIQUES        lists of item dicts
    ITEMS                         {key: item} for both
    fill(text, aircraft)          placeholder substitution
    recommend_for_brief(brief, comms_o, comms_d, layouts)
        -> [{key, airport, reason, level}]   techniques relevant to THIS flight

ALWAYS defer to the aircraft POH and the student's CFI.
"""

# ── Placeholder filling ───────────────────────────────────────────────────────

class _Speeds(dict):
    def __missing__(self, k):
        return "(see POH)"


def fill(text, aircraft=None):
    ac = aircraft or {}
    vals = _Speeds()
    for k in ("vx", "vy", "vg", "va", "vfe", "vs0", "vs1", "vno"):
        if ac.get(k):
            vals[k] = f"{ac[k]} kt"
    vals["ac"] = ac.get("display") or "your aircraft"
    try:
        return text.format_map(vals)
    except (ValueError, IndexError, KeyError):
        return text


# ── Shared snippets ───────────────────────────────────────────────────────────

_CLEARING = ("Clearing turns: two 90° turns (or one 180°) to look for traffic, "
             "and confirm you're over terrain where you could land.")
_ALT_1500 = "Choose an entry altitude so you recover no lower than 1,500 ft AGL."
_STALL_RECOVERY = [
    "**Reduce angle of attack** — forward elevator pressure until the stall warning and buffet stop. "
    "This comes first, always.",
    "**Roll wings level** with coordinated aileron and rudder.",
    "**Add power** as needed — full power, carb heat off (if equipped); expect left-turning tendency, "
    "so add right rudder.",
    "**Return to the desired flight path** — climb attitude at Vx {vx} / Vy {vy}; retract flaps in "
    "increments only after a positive rate of climb and adequate airspeed. Avoid a secondary stall "
    "by not pulling up too quickly.",
]


# ══════════════════════════════════════════════════════════════════════════════
# PROCEDURES — ACS maneuvers
# ══════════════════════════════════════════════════════════════════════════════

PROCEDURES = [
    {
        "key": "slow_flight",
        "title": "Slow Flight",
        "acs": "VII-A",
        "summary": "Controlling the airplane at an airspeed just above the stall warning.",
        "why": "Builds feel for the airplane at the low speeds you'll be at during takeoff and landing, "
               "where controls are sluggish and a stall is close.",
        "setup": [_CLEARING, _ALT_1500,
                  "Pick a heading and an outside reference (landmark on the horizon).",
                  "Carb heat ON (if equipped) before reducing power."],
        "steps": [
            "Reduce power well below cruise. Hold altitude by gradually raising the nose as speed bleeds off.",
            "Below Vfe ({vfe}), extend flaps in increments to the configuration your CFI/examiner specifies "
            "(often full landing flaps).",
            "Approach the target airspeed — a speed where any increase in angle of attack, load factor, or "
            "reduction in power would trigger the stall warning. Typically a few knots above stall "
            "(Vs0 {vs0} / Vs1 {vs1}).",
            "Add power to hold the target speed. In slow flight, **pitch controls airspeed and power "
            "controls altitude.**",
            "Keep the ball centered — high power at low speed needs noticeable right rudder.",
            "Fly straight-and-level, level turns, climbs and descents as assigned. Use shallow, "
            "coordinated turns.",
            "Recover: full power (carb heat off), lower the nose to hold altitude as you accelerate, "
            "retract flaps in increments (first one notch, then the rest as speed passes Vx/Vy), and "
            "return to cruise.",
        ],
        "standards": ["Altitude ±100 ft", "Heading ±10°", "Airspeed +10 / −0 kt",
                      "Specified bank angle ±10°", "No stall warning"],
        "errors": [
            "Triggering the stall horn — you went too slow or pulled too hard.",
            "Losing altitude while slowing down (not enough back pressure / power added too late).",
            "Not enough right rudder; ball out to the right.",
            "Staring at the airspeed indicator instead of flying an attitude outside.",
            "Dumping all the flaps at once on recovery — causes a sink.",
        ],
        "safety": "Stall warning = you've exceeded the standard. Keep scanning for traffic; you're slow and nose-high.",
        "source": "Airplane Flying Handbook — Maintaining Aircraft Control (slow flight)",
    },
    {
        "key": "power_off_stall",
        "title": "Power-Off Stall (approach to landing)",
        "acs": "VII-B",
        "summary": "Simulates stalling on approach or in the flare, in landing configuration.",
        "why": "Most stall/spin accidents happen in the pattern — especially the base-to-final turn. "
               "This teaches you to recognize and recover.",
        "setup": [_CLEARING, _ALT_1500, "Carb heat ON (if equipped)."],
        "steps": [
            "Reduce power and slow below Vfe ({vfe}). Configure as for landing (flaps as specified).",
            "Establish a stabilized descent at your normal approach speed, straight ahead or in a turn "
            "of up to 20° bank if assigned.",
            "Reduce power to idle and smoothly raise the nose to an attitude that will cause a stall. "
            "Keep the ball centered.",
            "Recognize the cues: stall horn, buffet, mushy controls, high nose attitude, then the break / sink.",
            "Recover promptly when the stall occurs (or when your CFI calls it):",
        ] + _STALL_RECOVERY,
        "standards": ["Heading ±10° (straight) or bank ±10° (turning, up to 20°)",
                      "Recover promptly after the stall occurs",
                      "Recover no lower than 1,500 ft AGL",
                      "No secondary stall, excessive altitude loss, or spin"],
        "errors": [
            "Adding power before lowering the nose — the wing is still stalled.",
            "Too much forward pressure (floating in your seat / large altitude loss).",
            "Pulling up too fast after the break → secondary stall.",
            "Retracting all flaps at once → sink, possible re-stall.",
            "Uncoordinated controls → a wing drops. Fix with coordinated rudder, not aggressive aileron.",
        ],
        "safety": "If a wing drops sharply or rotation starts, apply spin-recovery thinking: power idle, "
                  "ailerons neutral, opposite rudder, nose down.",
        "source": "Airplane Flying Handbook — Maintaining Aircraft Control (stalls)",
    },
    {
        "key": "power_on_stall",
        "title": "Power-On Stall (departure)",
        "acs": "VII-C",
        "summary": "Simulates stalling on takeoff or climb-out with power on.",
        "why": "Pulling too steeply right after takeoff — or while distracted on departure — leads to "
               "this stall close to the ground.",
        "setup": [_CLEARING, _ALT_1500],
        "steps": [
            "Reduce power and slow to about liftoff speed. Configure for takeoff (flaps as your POH "
            "specifies for takeoff).",
            "At liftoff speed, set takeoff or climb power (ACS allows no less than 65% of available power).",
            "Smoothly raise the nose to an attitude that will induce a stall — straight ahead or in a "
            "turn of up to 20° bank as assigned.",
            "Hold heading with **plenty of right rudder**; power + high angle of attack = strong left yaw.",
            "Recognize the cues and recover promptly when the stall occurs:",
        ] + _STALL_RECOVERY,
        "standards": ["Heading ±10° (straight) or bank ±10° (turning, up to 20°)",
                      "Power no less than 65% available",
                      "Recover promptly after the stall occurs",
                      "Recover no lower than 1,500 ft AGL"],
        "errors": [
            "Not enough right rudder → left wing drops at the break.",
            "Extremely high pitch attitude — use reduced power (≥65%) to keep it reasonable.",
            "Slow recovery or holding back pressure through the stall.",
        ],
        "safety": "Power-on stalls can break sharply. Have your CFI demonstrate first.",
        "source": "Airplane Flying Handbook — Maintaining Aircraft Control (stalls)",
    },
    {
        "key": "steep_turns",
        "title": "Steep Turns",
        "acs": "V-A",
        "summary": "360° turns at 45° bank in both directions while holding altitude.",
        "why": "Develops smooth coordination, energy control, and orientation at higher load factors.",
        "setup": [_CLEARING, _ALT_1500,
                  "Airspeed at or below maneuvering speed Va ({va} at max gross — Va is lower at lighter weights).",
                  "Note your heading and pick a landmark to roll out on."],
        "steps": [
            "Roll smoothly into a 45° bank with coordinated aileron and rudder.",
            "Passing about 30° of bank, add back pressure to hold altitude and a little power to hold airspeed.",
            "Hold the sight picture: the nose position on the horizon is your primary reference; "
            "cross-check altimeter and attitude indicator.",
            "Correct small altitude deviations with back pressure; correct big ones by shallowing the "
            "bank slightly first.",
            "Lead the rollout by about half the bank angle (~20° before your heading).",
            "On rollout, release back pressure and reduce the added power so you don't balloon.",
            "Roll directly into a turn the other way if assigned.",
        ],
        "standards": ["Bank 45° ±5°", "Altitude ±100 ft", "Airspeed ±10 kt",
                      "Roll out on entry heading ±10°"],
        "errors": [
            "Losing altitude in the first 90° (back pressure too late).",
            "Overbanking tendency — bank creeps past 45°.",
            "Ballooning on rollout from holding back pressure.",
            "Head-down flying; forgetting to look for traffic.",
        ],
        "safety": "Stay at or below Va. Load factor is 1.4 G at 45° — stall speed rises about 19%.",
        "source": "Airplane Flying Handbook — Performance Maneuvers",
    },
    {
        "key": "ground_reference",
        "title": "Ground Reference Maneuvers",
        "acs": "V-B",
        "summary": "Rectangular course, S-turns, and turns around a point — flying a ground track in wind.",
        "why": "This is the traffic pattern in disguise: wind correction while dividing attention "
               "inside and outside.",
        "setup": ["Altitude 600–1,000 ft AGL; pick an area clear of obstacles and people, "
                  "with a forced-landing field in mind.",
                  "Determine wind direction (smoke, water, drift) and enter downwind.",
                  "Clearing turn first."],
        "steps": [
            "**Rule of thumb: steepest bank when groundspeed is highest (directly downwind); shallowest "
            "when groundspeed is lowest (directly upwind).**",
            "*Rectangular course:* fly parallel to the field boundaries ~¼–½ mile out. Crab into the wind "
            "on each leg. Turns from downwind are steeper; turns into headwind are shallower.",
            "*S-turns:* cross a straight road perpendicular to the wind, flying semicircles of equal radius "
            "on each side. Wings level exactly as you cross the road.",
            "*Turns around a point:* enter downwind; bank no more than about 45° at the steepest point; "
            "adjust bank continuously to keep a constant distance from the point.",
            "Hold altitude and airspeed throughout; keep your eyes outside.",
        ],
        "standards": ["Altitude 600–1,000 ft AGL, ±100 ft", "Airspeed ±10 kt",
                      "Correct for wind drift to maintain the track", "Divide attention inside/outside"],
        "errors": ["Fixed bank angle (track drifts)", "Slipping or skidding in turns",
                   "Altitude creep while looking at the ground", "Poor entry (not downwind)"],
        "safety": "Low altitude — keep a landing spot in mind and watch for towers, birds, and wires.",
        "source": "Airplane Flying Handbook — Ground Reference Maneuvers",
    },
    {
        "key": "emergency_landing",
        "title": "Emergency Approach & Landing (engine failure)",
        "acs": "IX-B",
        "summary": "Engine-out glide to a field: A-B-C-D-E.",
        "why": "Engines rarely fail — but when they do, having the steps memorized is what saves you.",
        "setup": ["In training your CFI pulls the power; they'll call a go-around at a safe altitude "
                  "(often around 500 ft AGL away from an airport)."],
        "steps": [
            "**A — Airspeed:** pitch for best glide **{vg}** immediately and trim. Every knot off "
            "best glide costs distance.",
            "**B — Best field:** pick a landing spot within gliding distance — into the wind if possible, "
            "long and flat, no wires. Turn toward it now.",
            "**C — Checklist (restart):** fuel selector BOTH/on, mixture RICH, carb heat ON, "
            "primer IN & LOCKED, magnetos BOTH (try L/R), fuel pump ON if equipped. Use your POH flow.",
            "**D — Declare:** 121.5 or the frequency you're on — \"MAYDAY ×3, callsign, position, "
            "intentions.\" Squawk 7700.",
            "**E — Execute:** fly a pattern to the field (a high key / low key or a normal downwind-base-final "
            "if you have the altitude). Aim about one-third into the field; use flaps to steepen once you "
            "have it made.",
            "Before touchdown (if no restart): mixture idle cut-off, fuel OFF, magnetos OFF, master OFF "
            "after final flap setting, doors unlatched. Touch down as slowly as possible, nose high.",
            "**Engine failure right after takeoff:** lower the nose immediately and land roughly straight "
            "ahead (within ~30° either side). Do not attempt to turn back unless you've trained it and "
            "have the altitude.",
        ],
        "standards": ["Best glide airspeed ±10 kt", "Select a suitable landing area within gliding distance",
                      "Plan and follow a flight pattern to it", "Complete checklists and configure"],
        "errors": ["Not establishing best glide immediately", "Picking a field behind you or too far",
                   "Stretching the glide (pulling the nose up) — this shortens it",
                   "Too fast / too high on final from not using a pattern"],
        "safety": "Your POH checklist governs. Fly the airplane first — don't let the checklist distract "
                  "you below ~1,000 ft AGL.",
        "source": "Airplane Flying Handbook — Emergency Procedures",
    },
    {
        "key": "emergency_descent",
        "title": "Emergency Descent",
        "acs": "IX-A",
        "summary": "Getting down fast — for fire, smoke, or a medical issue.",
        "why": "When you need to be on the ground now, a steep spiraling descent loses altitude quickly "
               "while keeping you over a spot.",
        "setup": ["Clear the area below you."],
        "steps": [
            "Power to idle; carb heat ON (if equipped).",
            "Roll into a 30–45° bank (keeps positive G and lets you see below).",
            "Lower the nose to establish a descent at a speed no higher than Vno ({vno}) — or Va ({va}) "
            "if in turbulence. Use flaps only within Vfe ({vfe}) and as your POH recommends.",
            "Monitor airspeed closely; roll out on a heading and level off at the target altitude.",
        ],
        "standards": ["Appropriate airspeed +0 / −10 kt", "Level off at specified altitude ±100 ft"],
        "errors": ["Exceeding Vno / Vfe", "Insufficient bank (slow descent rate)",
                   "Forgetting to look below for traffic"],
        "safety": "For an engine fire, follow your POH — it may call for a very high airspeed to blow out the fire.",
        "source": "Airplane Flying Handbook — Emergency Procedures",
    },
    {
        "key": "spin_awareness",
        "title": "Spin Awareness",
        "acs": "VII-D",
        "summary": "A spin = stalled wing + yaw. Know what causes it and how to recover.",
        "why": "Base-to-final skidding turns, low and slow, are the classic stall/spin accident.",
        "setup": ["Knowledge task — most training airplanes are not approved for intentional spins "
                  "(check the POH category and placards)."],
        "steps": [
            "Prevention: stay coordinated (ball centered), especially in turns at low airspeed. Never "
            "\"rudder the nose around\" on base-to-final.",
            "Recovery (**PARE**), per POH:",
            "**P** — Power to idle.",
            "**A** — Ailerons neutral.",
            "**R** — Rudder full opposite the rotation.",
            "**E** — Elevator briskly forward to break the stall.",
            "When rotation stops: neutralize rudder, roll wings level, smoothly recover from the dive.",
        ],
        "standards": ["Explain aerodynamic factors, flight situations, and recovery procedure"],
        "errors": ["Using aileron to pick up a dropping wing in a stall",
                   "Skidding turns with inside rudder at low speed"],
        "safety": "If you overshoot final, go around — don't tighten the turn with rudder.",
        "source": "Airplane Flying Handbook — Maintaining Aircraft Control (spins)",
    },
]


# ══════════════════════════════════════════════════════════════════════════════
# TECHNIQUES — takeoffs, landings, and situational skills
# ══════════════════════════════════════════════════════════════════════════════

TECHNIQUES = [
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

    # Always relevant on any landing
    add("go_around", dest, "Every landing — decide your go-around gate before the approach",
        level="standard")

    recs.sort(key=lambda r: 0 if r["level"] == "key" else 1)
    return recs
