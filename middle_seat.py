"""
Rho — Middle Seat (game engine)

A two-player boarding game designed by Nic. Players take turns drawing cards
that dictate where their next passenger may sit. Everyone boards the same
roster; groups score when they're seated correctly, middle seats cost points.

This module is pure Python (no Streamlit, no Supabase) so it can be tested and
simulated headless. The whole game lives in one JSON-serialisable dict
(`state`) so it can be stored in Supabase for async player-vs-player games.

Python 3.9 compatible.

Public API (see bottom of file for the full list)
    PLANES, CARDS, TYPES, QUIZ
    new_game(plane_key, mode, players, rng=None) -> state
    get_plane(key)
    draw(state)                     current player draws a card
    legal_seats(state, pid)         seats the selected passenger may take now
    place(state, pid, seat)
    block_seat(state, seat|None)    Armrest Hog's blocked seat
    play_card(state, **target)      play the card in hand
    hold_card(state) / discard_card(state)
    play_held(state)                play held card before drawing
    answer_quiz(state, idx)
    compute_scores(state, final=False)
    bot_step(state)                 one decision for the bot whose move it is
"""

import copy
import random

_rng = random.Random()

# ══════════════════════════════════════════════════════════════════════════════
# Planes
# ══════════════════════════════════════════════════════════════════════════════

PLANES = {
    "a220": {
        "name": "Airbus A220",
        "nickname": "Quick Hop",
        "blurb": "2-3 seating: only one side has a middle seat. Fastest game.",
        "first_rows": [1, 2],
        "first_layout": ["AC", "DF"],
        "econ_rows": [10, 11, 12, 14, 15, 16, 17, 18, 19, 20],
        "econ_layout": ["AC", "DEF"],
        "exit_rows": [15, 16],
        "roster": "small",
    },
    "b737": {
        "name": "Boeing 737",
        "nickname": "Classic",
        "blurb": "3-3 single aisle. The original Middle Seat plane.",
        "first_rows": [1, 2, 3],
        "first_layout": ["AB", "EF"],
        "econ_rows": [7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19],
        "econ_layout": ["ABC", "DEF"],
        "exit_rows": [14, 15],
        "roster": "medium",
    },
    "b787": {
        "name": "Boeing 787",
        "nickname": "Long Haul",
        "blurb": "3-3-3 twin aisle. The middle of the middle (seat E) is -3.",
        "first_rows": [1, 2, 3],
        "first_layout": ["A", "EF", "J"],
        "econ_rows": [20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30],
        "econ_layout": ["ABC", "DEF", "GHJ"],
        "exit_rows": [24, 25],
        "roster": "large",
    },
}

_PLANE_CACHE = {}


def get_plane(key):
    """Build (and cache) seat geometry for a plane."""
    if key in _PLANE_CACHE:
        return _PLANE_CACHE[key]
    p = PLANES[key]
    seats = {}
    rows = []          # [(row, cabin, [[seat ids per section]])]
    all_rows = [(r, "first", p["first_layout"]) for r in p["first_rows"]] + \
               [(r, "econ", p["econ_layout"]) for r in p["econ_rows"]]
    n_econ = len(p["econ_rows"])
    exit_rows = set(p["exit_rows"])
    # Wing rows = exit rows plus the econ row immediately before/after each
    wing = set()
    for i, r in enumerate(p["econ_rows"]):
        if r in exit_rows:
            wing.add(r)
            if i > 0:
                wing.add(p["econ_rows"][i - 1])
            if i < n_econ - 1:
                wing.add(p["econ_rows"][i + 1])

    for ridx, (r, cabin, layout) in enumerate(all_rows):
        sections = []
        nsec = len(layout)
        eidx = p["econ_rows"].index(r) if cabin == "econ" else None
        for si, letters in enumerate(layout):
            sec = []
            for li, letter in enumerate(letters):
                sid = "%d%s" % (r, letter)
                first_in = li == 0
                last_in = li == len(letters) - 1
                is_window = (si == 0 and first_in) or (si == nsec - 1 and last_in)
                is_aisle = (first_in and si > 0) or (last_in and si < nsec - 1)
                if is_window:
                    kind = "window"
                elif is_aisle:
                    kind = "aisle"
                else:
                    kind = "middle"
                if si == 0:
                    side = "left"
                elif si == nsec - 1:
                    side = "right"
                else:
                    side = "center"
                seats[sid] = {
                    "id": sid, "row": r, "letter": letter, "cabin": cabin,
                    "section": si, "pos": li, "kind": kind, "side": side,
                    "ridx": ridx, "eidx": eidx,
                    "exit": r in exit_rows, "wing": r in wing,
                    # middle seat of a centre section (787 seat E) — worst seat
                    "center_middle": kind == "middle" and side == "center",
                    "front_half": eidx is not None and eidx < (n_econ + 1) // 2,
                }
                sec.append(sid)
            sections.append(sec)
        rows.append({"row": r, "cabin": cabin, "sections": sections})

    # Neighbours
    next_to, across, behind, infront = {}, {}, {}, {}
    for row in rows:
        secs = row["sections"]
        for si, sec in enumerate(secs):
            for li, sid in enumerate(sec):
                nt = []
                if li > 0:
                    nt.append(sec[li - 1])
                if li < len(sec) - 1:
                    nt.append(sec[li + 1])
                next_to[sid] = nt
                ac = []
                if li == 0 and si > 0:
                    ac.append(secs[si - 1][-1])
                if li == len(sec) - 1 and si < len(secs) - 1:
                    ac.append(secs[si + 1][0])
                across[sid] = ac
    econ_rows = p["econ_rows"]
    for sid, s in seats.items():
        behind[sid] = None
        infront[sid] = None
        if s["cabin"] != "econ":
            continue
        i = s["eidx"]
        if i < len(econ_rows) - 1:
            b = "%d%s" % (econ_rows[i + 1], s["letter"])
            behind[sid] = b if b in seats else None
        if i > 0:
            f = "%d%s" % (econ_rows[i - 1], s["letter"])
            infront[sid] = f if f in seats else None

    plane = {
        "key": key, "seats": seats, "rows": rows,
        "next_to": next_to, "across": across, "behind": behind, "infront": infront,
        "econ_seats": [sid for sid in seats if seats[sid]["cabin"] == "econ"],
        "first_seats": [sid for sid in seats if seats[sid]["cabin"] == "first"],
        "n_sections": len(p["econ_layout"]),
    }
    _PLANE_CACHE[key] = plane
    return plane


def adjacent(plane, a, b):
    """Side by side, or directly across an aisle, in the same row."""
    return b in plane["next_to"][a] or b in plane["across"][a]


# ══════════════════════════════════════════════════════════════════════════════
# Passengers
# ══════════════════════════════════════════════════════════════════════════════

TYPES = {
    "solo":     {"label": "Solo Traveler",   "emoji": "🧑", "desc": "Just wants to get there. 1 pt."},
    "partner":  {"label": "Couple",          "emoji": "💕", "desc": "+2 when seated next to (or across the aisle from) their partner."},
    "bff":      {"label": "Best Friend",     "emoji": "👯", "desc": "Trio. +3 when all three sit in the same row."},
    "parent":   {"label": "Parent",          "emoji": "🧔", "desc": "Family bonus when every kid sits next to (or across from) a parent and parents are within 1 row."},
    "kid":      {"label": "Kid",             "emoji": "🧒", "desc": "Needs a parent next to them or across the aisle. Not allowed in exit rows."},
    "fa":       {"label": "Flight Attendant", "emoji": "💁", "desc": "Worth 2. 'Get to Work' card pulls them to the galley for +2 more."},
    "marshal":  {"label": "Air Marshal",     "emoji": "👮", "desc": "Play 'Arrest' within 1 row of the opponent's Fugitive: +4 and the Fugitive is gone."},
    "fugitive": {"label": "The Fugitive",    "emoji": "🦹", "desc": "+4 if he's still on the loose at the end."},
    "recliner": {"label": "Recliner",        "emoji": "😴", "desc": "Whoever sits directly behind gets -1. +1 to you if it's an opponent."},
    "chatty":   {"label": "Chatty Cathy",    "emoji": "🗣️", "desc": "+2 if seated beside an opponent's passenger; each such neighbor -1."},
    "hog":      {"label": "Armrest Hog",     "emoji": "💪", "desc": "Blocks one seat next to him for the rest of the game."},
    "nervous":  {"label": "Nervous Flyer",   "emoji": "😰", "desc": "+3 if next to or across from ANY flight attendant."},
    "avgeek":   {"label": "AvGeek",          "emoji": "🛩️", "desc": "+3 in a window seat over the wing (exit rows ±1)."},
}

# Who can secretly be the Doctor / Pilot
SECRET_ELIGIBLE = ("solo", "partner", "bff", "parent")
# Who can be upgraded (groups other than couples can't)
UPGRADABLE = ("solo", "partner", "fa", "marshal", "fugitive", "recliner", "chatty",
              "hog", "nervous", "avgeek")

GROUP_BONUS = {"couple": 2, "bff": 3}
FAMILY_BONUS = {3: 3, 4: 5, 5: 6}

ROSTERS = {
    # name: (couples, bff_trios, families [(parents, kids, letter)], solos, extras)
    "small":  {"couples": 2, "bffs": 1, "families": [(2, 2, "A")], "solos": 3, "fas": 2},
    "medium": {"couples": 3, "bffs": 1, "families": [(2, 2, "A"), (2, 1, "B")], "solos": 6, "fas": 2},
    "large":  {"couples": 3, "bffs": 1, "families": [(2, 2, "A"), (2, 1, "B"), (2, 3, "C")],
               "solos": 9, "fas": 2},
}
SPECIALS = ("marshal", "fugitive", "recliner", "chatty", "hog", "nervous", "avgeek")


def _build_roster(owner, roster_key):
    spec = ROSTERS[roster_key]
    out = []
    n = [0]

    def add(ptype, group=None, glabel=None, gkind=None):
        out.append({
            "id": "%d-%02d" % (owner, n[0]), "owner": owner, "type": ptype,
            "group": group, "glabel": glabel, "gkind": gkind,
            "status": "gate", "seat": None, "secret": None, "revealed": False,
        })
        n[0] += 1

    for c in range(spec["couples"]):
        g = "%d-couple%d" % (owner, c + 1)
        add("partner", g, "Couple %d" % (c + 1), "couple")
        add("partner", g, "Couple %d" % (c + 1), "couple")
    for b in range(spec["bffs"]):
        g = "%d-bff%d" % (owner, b + 1)
        for _ in range(3):
            add("bff", g, "Best Friends", "bff")
    for parents, kids, letter in spec["families"]:
        g = "%d-fam%s" % (owner, letter)
        for _ in range(parents):
            add("parent", g, "Family %s" % letter, "family")
        for _ in range(kids):
            add("kid", g, "Family %s" % letter, "family")
    for _ in range(spec["fas"]):
        add("fa")
    for t in SPECIALS:
        add(t)
    for _ in range(spec["solos"]):
        add("solo")
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Cards
# ══════════════════════════════════════════════════════════════════════════════

CARDS = {
    # ── Seat cards ────────────────────────────────────────────────────────────
    "WINDOW":       {"name": "Window Seat",       "kind": "seat", "emoji": "🪟", "text": "Board into any open window seat."},
    "AISLE":        {"name": "Aisle Seat",        "kind": "seat", "emoji": "🚶", "text": "Board into any open aisle seat."},
    "LEFT":         {"name": "Left Side",         "kind": "seat", "emoji": "⬅️", "text": "Board on the left side of the plane."},
    "RIGHT":        {"name": "Right Side",        "kind": "seat", "emoji": "➡️", "text": "Board on the right side of the plane."},
    "CENTER":       {"name": "Center Section",    "kind": "seat", "emoji": "⏺️", "text": "Board in the center section (between the aisles)."},
    "FRONT":        {"name": "Front Cabin",       "kind": "seat", "emoji": "⏫", "text": "Board in the front half of economy."},
    "BACK":         {"name": "Back Cabin",        "kind": "seat", "emoji": "⏬", "text": "Board in the back half of economy."},
    "EVEN":         {"name": "Even Row",          "kind": "seat", "emoji": "2️⃣", "text": "Board in an even-numbered row."},
    "ODD":          {"name": "Odd Row",           "kind": "seat", "emoji": "1️⃣", "text": "Board in an odd-numbered row."},
    "EXIT":         {"name": "Exit Row",          "kind": "seat", "emoji": "🚪", "text": "Board in an exit row. Kids can't sit here."},
    "WINDOW_FRONT": {"name": "Window, Up Front",  "kind": "seat", "emoji": "🌅", "text": "A window seat in the front half of economy."},
    "AISLE_BACK":   {"name": "Aisle, Way Back",   "kind": "seat", "emoji": "🚻", "text": "An aisle seat in the back half — near the lavs."},
    "BASIC":        {"name": "Basic Economy",     "kind": "seat", "emoji": "🥲", "text": "You get what you paid for. Board into a middle seat."},
    "OPEN":         {"name": "Open Seating",      "kind": "seat", "emoji": "🎟️", "text": "Sit anywhere in economy."},
    # ── Action cards (you may hold one) ───────────────────────────────────────
    "UPGRADE":      {"name": "Upgrade!",          "kind": "action", "emoji": "🥂", "text": "Move one of your passengers (seated or at the gate) to First Class: +2 and locked. Couples upgrade together. Groups and kids can't."},
    "GROUP1":       {"name": "Group 1 Boarding",  "kind": "action", "emoji": "⏩", "text": "Cut the line: take another turn."},
    "SWITCH":       {"name": "Can We Switch?",    "kind": "action", "emoji": "🔄", "text": "Swap any two unlocked passengers in economy (either team)."},
    "FORGOT":       {"name": "I Forgot Something", "kind": "action", "emoji": "🎒", "text": "Send one of your opponent's unlocked passengers back to the gate.", "attack": True},
    "OVERBOOKED":   {"name": "Overbooked",        "kind": "action", "emoji": "📛", "text": "Your opponent's next passenger must take a middle seat.", "attack": True},
    "SEATBELT":     {"name": "Seatbelt Sign Is On", "kind": "action", "emoji": "💺", "text": "Held automatically. Cancels the next card your opponent plays against you."},
    "ARREST":       {"name": "Arrest Them!",      "kind": "action", "emoji": "🚔", "text": "If your Air Marshal is within 1 row of the opponent's Fugitive: +4, Fugitive removed.", "attack": True},
    "KICKER":       {"name": "Seat Kicker",       "kind": "action", "emoji": "🦶", "text": "One of your kids kicks the seat in front. You move that passenger to any open middle seat."},
    "WORK":         {"name": "Get to Work",       "kind": "action", "emoji": "☕", "text": "A seated flight attendant heads to the galley: +2 and their seat opens up."},
    "REBOOKED":     {"name": "Rebooked",          "kind": "action", "emoji": "📅", "text": "Remove one of your passengers still at the gate. No points, no penalty."},
    "FAMILY":       {"name": "Family Boarding",   "kind": "action", "emoji": "👨‍👩‍👧", "text": "Board one whole group (still all at the gate) into any open economy seats."},
    # ── Events (resolve the moment they're drawn) ─────────────────────────────
    "EMERGENCY_EXIT": {"name": "Emergency Exit",  "kind": "event", "emoji": "🚨", "text": "If every exit-row seat is filled, someone pops the door and the game ends now."},
    "DOCTOR":       {"name": "Is There a Doctor on Board?", "kind": "event", "emoji": "🩺", "text": "A passenger has a medical emergency. The closest seated secret Doctor saves them: +5."},
    "PILOT":        {"name": "Pilot Incapacitated", "kind": "event", "emoji": "👨‍✈️", "text": "Is anyone here a pilot?! The secret Pilot closest to the cockpit takes the controls. In First Class: answer 2 checkride questions to land it and WIN. Elsewhere: answer 1 for +8. Miss: +2 go-around."},
}

DECK_COUNTS = {
    "WINDOW": 6, "AISLE": 6, "LEFT": 4, "RIGHT": 4, "FRONT": 4, "BACK": 4,
    "EVEN": 3, "ODD": 3, "EXIT": 2, "WINDOW_FRONT": 2, "AISLE_BACK": 2,
    "BASIC": 2, "OPEN": 4,
    "UPGRADE": 2, "GROUP1": 3, "SWITCH": 3, "FORGOT": 2, "OVERBOOKED": 2,
    "SEATBELT": 2, "ARREST": 1, "KICKER": 1, "WORK": 1, "REBOOKED": 1,
    "FAMILY": 1, "EMERGENCY_EXIT": 1, "DOCTOR": 2, "PILOT": 1,
}

MODES = {
    "classic": {"name": "Classic", "blurb": "Board everyone. Highest score wins. Middle seats cost points."},
    "blitz":   {"name": "Blitz",   "blurb": "First player with a passenger in a middle seat — for any reason — loses."},
}


def _build_deck(plane_key, mode, rng):
    counts = dict(DECK_COUNTS)
    if get_plane(plane_key)["n_sections"] == 3:
        counts["CENTER"] = 3
    if mode == "blitz":
        # Anything that shoves a passenger into a middle seat would be an instant kill
        for k in ("BASIC", "OVERBOOKED", "KICKER"):
            counts.pop(k, None)
    deck = []
    for k, n in counts.items():
        deck.extend([k] * n)
    rng.shuffle(deck)
    # Pilot Incapacitated always lives in the last third of the deck
    if "PILOT" in deck:
        deck.remove("PILOT")
        lo = (len(deck) * 2) // 3
        deck.insert(rng.randint(lo, len(deck)), "PILOT")
    return deck  # deck[0] is the top card


# ══════════════════════════════════════════════════════════════════════════════
# Quiz (Pilot Incapacitated)
# ══════════════════════════════════════════════════════════════════════════════

QUIZ = [
    {"q": "Cessna 172S best glide speed (max gross)?",
     "options": ["55 KIAS", "62 KIAS", "68 KIAS", "74 KIAS"], "a": 2,
     "why": "68 KIAS is the 172S best-glide speed at max weight. 62 is Vx, 74 is Vy."},
    {"q": "Cessna 172S Vy (best rate of climb)?",
     "options": ["62 KIAS", "68 KIAS", "74 KIAS", "85 KIAS"], "a": 2,
     "why": "Vy = 74 KIAS. Vx = 62 KIAS."},
    {"q": "Cessna 172S Vx (best angle of climb)?",
     "options": ["55 KIAS", "62 KIAS", "70 KIAS", "74 KIAS"], "a": 1,
     "why": "Vx = 62 KIAS — the speed for clearing that obstacle at the end of the runway."},
    {"q": "Light gun on the ground: FLASHING GREEN means…",
     "options": ["Cleared for takeoff", "Cleared to taxi", "Stop", "Return to starting point"], "a": 1,
     "why": "Flashing green = cleared to taxi. Steady green = cleared for takeoff."},
    {"q": "Light gun in the air: STEADY GREEN means…",
     "options": ["Return for landing", "Cleared to land", "Give way, keep circling", "Airport unsafe"], "a": 1,
     "why": "Steady green in flight = cleared to land. Flashing green = return for landing."},
    {"q": "Light gun in the air: FLASHING RED means…",
     "options": ["Give way, keep circling", "Airport unsafe — do not land", "Exercise extreme caution", "Cleared to land"], "a": 1,
     "why": "Flashing red airborne = airport unsafe, do not land. Steady red = give way and continue circling."},
    {"q": "Light gun on the ground: FLASHING WHITE means…",
     "options": ["Taxi clear of the runway", "Cleared to taxi", "Return to starting point on airport", "Stop"], "a": 2,
     "why": "Flashing white (ground only) = return to starting point on the airport."},
    {"q": "Squawk for lost communications?",
     "options": ["1200", "7500", "7600", "7700"], "a": 2,
     "why": "7600 = lost comms. 7700 = emergency. 7500 = hijack. 1200 = VFR."},
    {"q": "Squawk for a general emergency?",
     "options": ["7700", "7600", "7500", "1200"], "a": 0,
     "why": "7700 = emergency. (7500 = hijack — never say it on the radio as a joke.)"},
    {"q": "Class E below 10,000 MSL — VFR visibility & cloud clearance?",
     "options": ["1 SM, clear of clouds", "3 SM, clear of clouds",
                 "3 SM; 500 below, 1,000 above, 2,000 horizontal", "5 SM; 1,000 below, 1,000 above, 1 SM horizontal"], "a": 2,
     "why": "14 CFR 91.155: 3 SM and 500 below / 1,000 above / 2,000 horizontal."},
    {"q": "Class B — VFR cloud clearance?",
     "options": ["Clear of clouds", "500 below, 1,000 above, 2,000 horizontal",
                 "1,000 below, 1,000 above, 1 SM", "1,000 ft above only"], "a": 0,
     "why": "Class B: 3 SM visibility and clear of clouds."},
    {"q": "Class E at or above 10,000 MSL — VFR minimums?",
     "options": ["3 SM; 500/1,000/2,000", "5 SM; 1,000 below, 1,000 above, 1 SM horizontal",
                 "1 SM; clear of clouds", "3 SM; clear of clouds"], "a": 1,
     "why": "At/above 10,000 MSL (and >1,200 AGL): 5 SM, 1,000 below, 1,000 above, 1 SM horizontal."},
    {"q": "Day VFR fuel reserve required by 91.151?",
     "options": ["20 minutes", "30 minutes", "45 minutes", "1 hour"], "a": 1,
     "why": "Day VFR: enough to reach the first point of intended landing plus 30 minutes. Night: 45."},
    {"q": "VFR cruising altitude on a magnetic course of 090°, above 3,000 AGL?",
     "options": ["Even thousands", "Even thousands + 500", "Odd thousands", "Odd thousands + 500"], "a": 3,
     "why": "0–179° magnetic: odd thousands + 500 (e.g. 5,500). 180–359°: even + 500."},
    {"q": "Two aircraft converging at about the same altitude. Who has the right of way?",
     "options": ["The faster one", "The one on the left", "The one on the right", "The higher one"], "a": 2,
     "why": "91.113: the aircraft to the other's right has the right of way."},
    {"q": "Minimum altitude over a congested area (91.119)?",
     "options": ["500 ft AGL", "1,000 ft above the highest obstacle within 2,000 ft",
                 "1,500 ft AGL", "2,000 ft above the highest obstacle within 1,000 ft"], "a": 1,
     "why": "Congested areas: 1,000 ft above the highest obstacle within a 2,000 ft horizontal radius."},
    {"q": "To carry passengers you need how many takeoffs & landings in the preceding 90 days?",
     "options": ["1", "3", "5", "10"], "a": 1,
     "why": "61.57: three takeoffs and landings in the same category, class (and type if required)."},
    {"q": "Entering Class D airspace requires…",
     "options": ["An ATC clearance", "Two-way radio communication established",
                 "A Mode C transponder", "An instrument rating"], "a": 1,
     "why": "Class D: establish two-way radio communication before entering. No clearance needed."},
    {"q": "On the airspeed indicator, the WHITE arc is…",
     "options": ["Normal operating range", "Caution range", "Flap operating range", "Never exceed"], "a": 2,
     "why": "White arc = flap operating range (Vso to Vfe). Green = normal, yellow = caution, red line = Vne."},
    {"q": "Flying from high pressure into low pressure without resetting the altimeter, you are…",
     "options": ["Higher than indicated", "Lower than indicated", "Exactly as indicated", "Climbing"], "a": 1,
     "why": "High to low, look out below — the altimeter reads higher than you really are."},
    {"q": "Runway 23 is aligned with a magnetic heading of about…",
     "options": ["023°", "123°", "230°", "320°"], "a": 2,
     "why": "Runway numbers are the magnetic heading divided by ten, rounded."},
    {"q": "Class G, day, at or below 1,200 AGL — VFR minimums?",
     "options": ["1 SM, clear of clouds", "3 SM, clear of clouds",
                 "1 SM; 500/1,000/2,000", "3 SM; 500/1,000/2,000"], "a": 0,
     "why": "Class G day, ≤1,200 AGL: 1 SM and clear of clouds."},
]


# ══════════════════════════════════════════════════════════════════════════════
# State
# ══════════════════════════════════════════════════════════════════════════════

def new_game(plane_key="b737", mode="classic", players=None, rng=None):
    """
    players: [{"name": str, "kind": "human"|"bot", "uid": str|None}, x2]
    Player 0 goes first.
    """
    rng = rng or _rng
    if players is None:
        players = [{"name": "You", "kind": "human", "uid": None},
                   {"name": "Rho", "kind": "bot", "uid": None}]
    plane = get_plane(plane_key)
    roster_key = PLANES[plane_key]["roster"]
    pax = {}
    for owner in (0, 1):
        roster = _build_roster(owner, roster_key)
        eligible = [p for p in roster if p["type"] in SECRET_ELIGIBLE]
        doc, pilot = rng.sample(eligible, 2)
        doc["secret"] = "doctor"
        pilot["secret"] = "pilot"
        for p in roster:
            pax[p["id"]] = p
    state = {
        "v": 1,
        "plane": plane_key,
        "mode": mode,
        "players": players,
        "pax": pax,
        "occ": {},                     # seat -> pid
        "blocked": {},                 # seat -> hog pid
        "deck": _build_deck(plane_key, mode, rng),
        "discard": [],
        "turn": 0,                     # whose turn
        "actor": 0,                    # who must act right now
        "turn_no": 1,
        "phase": "start",              # start | place | block | action | family | quiz | over
        "card": None,                  # card in hand (drawn this turn)
        "card_from_hold": False,
        "held": [None, None],
        "overbooked": [False, False],
        "extra_turn": False,
        "queue": [],                   # pids to place freely (Family Boarding)
        "block_for": None,             # hog pid awaiting a block choice
        "quiz": None,                  # {"pid", "owner", "q", "first"}
        "bonus": [[], []],             # [(category, pts, note)]
        "log": [],
        "over": False,
        "winner": None,                # 0, 1, "tie"
        "end_reason": None,
        "forced_note": None,
        "last": None,                  # last move highlight {"seats": [...], "by": int}
        "pilot_done": False,
    }
    _log(state, "✈️ Boarding has begun on the %s. First to board: %s."
         % (PLANES[plane_key]["name"], players[0]["name"]))
    return state


def _log(state, msg):
    msg = msg.replace("!.", "!").replace("?.", "?")
    state["log_n"] = state.get("log_n", 0) + 1
    state["log"].append(msg)
    who = state.setdefault("log_who", [])
    who.append(state.get("turn", 0))
    if len(state["log"]) > 80:
        state["log"] = state["log"][-80:]
        state["log_who"] = who[-80:]


def pname(state, i):
    return state["players"][i]["name"]


def plabel(state, pid, reveal_for=None):
    p = state["pax"][pid]
    t = TYPES[p["type"]]
    lbl = t["label"]
    if p["glabel"] and p["type"] in ("partner", "parent", "kid", "bff"):
        lbl = "%s (%s)" % (lbl, p["glabel"])
    if p["secret"] and (p["revealed"] or reveal_for == p["owner"]):
        lbl += " — secret %s" % p["secret"].capitalize()
    return "%s %s" % (t["emoji"], lbl)


def gate_pax(state, owner):
    return [p for p in state["pax"].values() if p["owner"] == owner and p["status"] == "gate"]


def seated_pax(state, owner=None):
    return [p for p in state["pax"].values()
            if p["status"] == "seated" and (owner is None or p["owner"] == owner)]


def open_seats(state, cabin="econ"):
    plane = get_plane(state["plane"])
    ids = plane["econ_seats"] if cabin == "econ" else plane["first_seats"]
    return [s for s in ids if s not in state["occ"] and s not in state["blocked"]]


def _members(state, gid):
    return [p for p in state["pax"].values() if p["group"] == gid]


def _groups(state):
    g = {}
    for p in state["pax"].values():
        if p["group"]:
            g.setdefault(p["group"], []).append(p)
    return g


def group_complete(state, gid, plane=None, groups=None):
    plane = plane or get_plane(state["plane"])
    mem = groups[gid] if groups is not None else _members(state, gid)
    if not mem or any(m["status"] != "seated" for m in mem):
        return False
    kind = mem[0]["gkind"]
    seats = plane["seats"]
    if kind == "couple":
        return adjacent(plane, mem[0]["seat"], mem[1]["seat"])
    if kind == "bff":
        rows = set(seats[m["seat"]]["row"] for m in mem)
        return len(rows) == 1
    if kind == "family":
        parents = [m for m in mem if m["type"] == "parent"]
        kids = [m for m in mem if m["type"] == "kid"]
        pr = [seats[m["seat"]]["ridx"] for m in parents]
        if max(pr) - min(pr) > 1:
            return False
        for k in kids:
            if not any(adjacent(plane, k["seat"], par["seat"]) for par in parents):
                return False
        return True
    return False


def is_locked(state, pid, plane=None):
    """Locked is locked: First Class, or part of a completed group."""
    plane = plane or get_plane(state["plane"])
    p = state["pax"][pid]
    if p["status"] != "seated":
        return False
    if plane["seats"][p["seat"]]["cabin"] == "first":
        return True
    if p["group"] and group_complete(state, p["group"], plane):
        return True
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Scoring
# ══════════════════════════════════════════════════════════════════════════════

SCORE_ORDER = ["Seated", "Flight attendants", "First Class", "Groups", "Middle seats",
               "Recliner", "Chatty Cathy", "Nervous Flyer", "AvGeek", "Fugitive",
               "Arrest", "Doctor", "Pilot", "Left at gate"]


def compute_scores(state, final=None):
    """
    Returns [{"total": int, "items": {category: pts}}, x2].
    `final` (default: state["over"]) adds the -2 per passenger left at the gate.
    """
    if final is None:
        final = state["over"]
    plane = get_plane(state["plane"])
    seats = plane["seats"]
    occ = state["occ"]
    pax = state["pax"]
    res = [{"total": 0, "items": {}}, {"total": 0, "items": {}}]
    groups = _groups(state)

    def add(owner, cat, pts):
        if pts:
            res[owner]["items"][cat] = res[owner]["items"].get(cat, 0) + pts
            res[owner]["total"] += pts

    done_groups = set()
    for p in pax.values():
        o = p["owner"]
        if p["status"] == "working":
            add(o, "Flight attendants", 4)
            continue
        if p["status"] == "gate" and final:
            add(o, "Left at gate", -2)
        if p["status"] != "seated":
            continue
        sid = p["seat"]
        s = seats[sid]
        t = p["type"]
        if t == "fa":
            add(o, "Flight attendants", 2)
        else:
            add(o, "Seated", 1)
        if s["cabin"] == "first":
            add(o, "First Class", 2)
        # groups
        if p["group"] and p["group"] not in done_groups:
            done_groups.add(p["group"])
            if group_complete(state, p["group"], plane, groups):
                if p["gkind"] == "family":
                    add(o, "Groups", FAMILY_BONUS.get(len(groups[p["group"]]), 4))
                else:
                    add(o, "Groups", GROUP_BONUS[p["gkind"]])
        # middle seat penalty (economy only)
        if s["kind"] == "middle" and s["cabin"] == "econ":
            nbrs = plane["next_to"][sid]
            sandwiched = p["group"] is not None and len(nbrs) == 2 and all(
                n in occ and pax[occ[n]]["group"] == p["group"] for n in nbrs)
            if not sandwiched:
                add(o, "Middle seats", -3 if s["center_middle"] else -2)
        # specials
        if t == "recliner" and s["cabin"] == "econ":
            b = plane["behind"][sid]
            if b and b in occ:
                victim = pax[occ[b]]
                add(victim["owner"], "Recliner", -1)
                if victim["owner"] != o:
                    add(o, "Recliner", 1)
        elif t == "chatty":
            opp_nbrs = [occ[n] for n in plane["next_to"][sid]
                        if n in occ and pax[occ[n]]["owner"] != o]
            if opp_nbrs:
                add(o, "Chatty Cathy", 2)
                for npid in opp_nbrs:
                    add(pax[npid]["owner"], "Chatty Cathy", -1)
        elif t == "nervous":
            near = plane["next_to"][sid] + plane["across"][sid]
            if any(n in occ and pax[occ[n]]["type"] == "fa" for n in near):
                add(o, "Nervous Flyer", 3)
        elif t == "avgeek":
            if s["kind"] == "window" and s["wing"]:
                add(o, "AvGeek", 3)
        elif t == "fugitive":
            add(o, "Fugitive", 4)
    for i in (0, 1):
        for cat, pts, _note in state["bonus"][i]:
            add(i, cat, pts)
    return res


def score_diff(state, me):
    sc = compute_scores(state, final=False)
    return sc[me]["total"] - sc[1 - me]["total"]


# ══════════════════════════════════════════════════════════════════════════════
# Seat legality
# ══════════════════════════════════════════════════════════════════════════════

def _card_match(plane, sid, card):
    s = plane["seats"][sid]
    if card == "WINDOW":
        return s["kind"] == "window"
    if card == "AISLE":
        return s["kind"] == "aisle"
    if card == "BASIC" or card == "_MIDDLE":
        return s["kind"] == "middle"
    if card == "LEFT":
        return s["side"] == "left"
    if card == "RIGHT":
        return s["side"] == "right"
    if card == "CENTER":
        return s["side"] == "center"
    if card == "FRONT":
        return s["front_half"]
    if card == "BACK":
        return not s["front_half"]
    if card == "EVEN":
        return s["row"] % 2 == 0
    if card == "ODD":
        return s["row"] % 2 == 1
    if card == "EXIT":
        return s["exit"]
    if card == "WINDOW_FRONT":
        return s["kind"] == "window" and s["front_half"]
    if card == "AISLE_BACK":
        return s["kind"] == "aisle" and not s["front_half"]
    return True  # OPEN, _ANY


def _kid_ok(plane, ptype, sid):
    return not (ptype == "kid" and plane["seats"][sid]["exit"])


def legal_seats(state, pid, card=None):
    """
    Returns (seats, forced) for placing passenger `pid` right now.
    forced=True means the card's seats were full, so it fell back to middle seats.
    """
    plane = get_plane(state["plane"])
    p = state["pax"][pid]
    if card is None:
        card = "_ANY" if state["phase"] == "family" else state["card"]
    openings = [s for s in open_seats(state) if _kid_ok(plane, p["type"], s)]
    if state["phase"] != "family" and state["overbooked"][p["owner"]]:
        card = "_MIDDLE"
    match = [s for s in openings if _card_match(plane, s, card)]
    if match:
        return match, False
    mids = [s for s in openings if plane["seats"][s]["kind"] == "middle"]
    if mids:
        return mids, True
    return openings, True


def any_legal(state, owner):
    return any(legal_seats(state, p["id"])[0] for p in gate_pax(state, owner))


# ══════════════════════════════════════════════════════════════════════════════
# Turn flow
# ══════════════════════════════════════════════════════════════════════════════

def _draw_card(state, rng=None):
    rng = rng or _rng
    if not state["deck"]:
        state["deck"] = state["discard"]
        state["discard"] = []
        rng.shuffle(state["deck"])
        _log(state, "🔀 The deck is reshuffled.")
    if not state["deck"]:
        return None
    return state["deck"].pop(0)


def draw(state, rng=None):
    """Current player draws. Resolves events immediately."""
    assert state["phase"] == "start" and not state["over"]
    rng = rng or _rng
    me = state["turn"]
    state["_must_draw"] = False
    card = _draw_card(state, rng)
    if card is None:
        _end_game(state, "The deck ran out.")
        return
    state["card"] = card
    state["card_from_hold"] = False
    c = CARDS[card]
    _log(state, "%s drew %s %s." % (pname(state, me), c["emoji"], c["name"]))
    if c["kind"] == "seat":
        if not gate_pax(state, me):
            _log(state, "…but everyone of theirs is already aboard.")
            _discard_and_end(state)
        elif not any_legal(state, me):
            _log(state, "…but there's no open seat left for anyone of theirs.")
            _discard_and_end(state)
        else:
            state["phase"] = "place"
    elif c["kind"] == "event":
        _resolve_event(state, card, rng)
    else:  # action
        if card == "SEATBELT":
            if state["held"][me] is None:
                state["held"][me] = "SEATBELT"
                state["card"] = None
                _log(state, "💺 %s holds the Seatbelt Sign." % pname(state, me))
                _end_turn(state)
            else:
                _discard_and_end(state)
        else:
            state["phase"] = "action"


def _discard_and_end(state):
    if state["card"]:
        if state["card"] != "PILOT":
            state["discard"].append(state["card"])
        state["card"] = None
    _end_turn(state)


def _end_turn(state):
    if state["over"]:
        return
    state["card"] = None
    state["card_from_hold"] = False
    state["forced_note"] = None
    if _check_game_end(state):
        return
    if state["extra_turn"]:
        state["extra_turn"] = False
        _log(state, "⏩ %s goes again." % pname(state, state["turn"]))
    else:
        state["turn"] = 1 - state["turn"]
        state["turn_no"] += 1
    state["actor"] = state["turn"]
    state["phase"] = "start"


def _check_game_end(state):
    if state["over"]:
        return True
    g0, g1 = gate_pax(state, 0), gate_pax(state, 1)
    if not g0 and not g1:
        _end_game(state, "Everyone is aboard. Doors closing!")
        return True
    if not open_seats(state):
        _end_game(state, "The plane is full. Doors closing!")
        return True
    if state["turn_no"] > 400:
        _end_game(state, "Turn limit reached.")
        return True
    return False


def _end_game(state, reason, winner=None):
    state["over"] = True
    state["phase"] = "over"
    state["end_reason"] = reason
    state["card"] = None
    if winner is None:
        sc = compute_scores(state, final=True)
        if sc[0]["total"] > sc[1]["total"]:
            winner = 0
        elif sc[1]["total"] > sc[0]["total"]:
            winner = 1
        else:
            winner = "tie"
    state["winner"] = winner
    for p in state["pax"].values():
        if p["secret"]:
            p["revealed"] = True
    _log(state, "🛬 " + reason)


def _blitz_check(state, actor):
    """Blitz: anyone with a passenger in an economy middle seat loses."""
    if state["mode"] != "blitz" or state["over"]:
        return False
    plane = get_plane(state["plane"])
    losers = set()
    for p in seated_pax(state):
        s = plane["seats"][p["seat"]]
        if s["cabin"] == "econ" and s["kind"] == "middle":
            losers.add(p["owner"])
    if not losers:
        return False
    loser = actor if (len(losers) == 2) else losers.pop()
    _end_game(state, "%s ended up with a passenger in the middle seat!" % pname(state, loser),
              winner=1 - loser)
    return True


# ── Placement ────────────────────────────────────────────────────────────────

def _seat(state, pid, sid):
    p = state["pax"][pid]
    if p["seat"]:
        state["occ"].pop(p["seat"], None)
    p["seat"] = sid
    p["status"] = "seated"
    state["occ"][sid] = pid


def _swap(state, sa, sb):
    a, b = state["occ"][sa], state["occ"][sb]
    state["occ"][sa], state["occ"][sb] = b, a
    state["pax"][a]["seat"], state["pax"][b]["seat"] = sb, sa


def _unseat(state, pid, status="gate"):
    p = state["pax"][pid]
    if p["seat"]:
        state["occ"].pop(p["seat"], None)
    p["seat"] = None
    p["status"] = status
    # an Armrest Hog takes his blocked armrest with him
    for b, hog in list(state["blocked"].items()):
        if hog == pid:
            del state["blocked"][b]


def place(state, pid, sid):
    assert state["phase"] in ("place", "family")
    me = state["actor"]
    p = state["pax"][pid]
    assert p["owner"] == me and p["status"] == "gate"
    if state["phase"] == "family":
        assert state["queue"] and state["queue"][0] == pid
    seats, forced = legal_seats(state, pid)
    if sid not in seats:
        raise ValueError("Seat %s isn't legal for that passenger." % sid)
    plane = get_plane(state["plane"])
    was_overbooked = state["phase"] == "place" and state["overbooked"][me]
    _seat(state, pid, sid)
    state["last"] = {"seats": [sid], "by": me}
    note = ""
    if was_overbooked:
        state["overbooked"][me] = False
        note = " (overbooked!)"
    elif forced:
        note = " (no %s seats left — stuck in a middle)" % CARDS[state["card"]]["name"].lower() \
            if state["phase"] == "place" and state["card"] else ""
    _log(state, "%s seated %s in %s%s." % (pname(state, me), plabel(state, pid), sid, note))
    if _blitz_check(state, me):
        return
    # Armrest Hog picks a seat to block
    if p["type"] == "hog":
        free = [n for n in plane["next_to"][sid] if n not in state["occ"] and n not in state["blocked"]]
        if free:
            state["block_for"] = pid
            state["prev_phase"] = state["phase"]
            state["phase"] = "block"
            return
    _after_place(state)


def _after_place(state):
    if state["phase"] in ("family",) or state.get("prev_phase") == "family":
        state["prev_phase"] = None
        state["phase"] = "family"
        if state["queue"]:
            state["queue"].pop(0)
        # drop any queued passengers that can't be seated
        while state["queue"] and not legal_seats(state, state["queue"][0])[0]:
            _log(state, "No room for %s." % plabel(state, state["queue"][0]))
            state["queue"].pop(0)
        if state["queue"]:
            return
        _finish_action(state)
        return
    state["prev_phase"] = None
    _discard_and_end(state)


def block_options(state):
    plane = get_plane(state["plane"])
    pid = state["block_for"]
    sid = state["pax"][pid]["seat"]
    return [n for n in plane["next_to"][sid] if n not in state["occ"] and n not in state["blocked"]]


def block_seat(state, sid):
    assert state["phase"] == "block"
    pid = state["block_for"]
    if sid is not None:
        if sid not in block_options(state):
            raise ValueError("Can't block that seat.")
        state["blocked"][sid] = pid
        _log(state, "💪 The Armrest Hog spreads out — %s is blocked." % sid)
    state["block_for"] = None
    _after_place(state)


# ── Holding / discarding ─────────────────────────────────────────────────────

def can_hold(state):
    return (state["phase"] == "action" and not state["card_from_hold"]
            and state["held"][state["turn"]] is None)


def hold_card(state):
    assert can_hold(state)
    me = state["turn"]
    state["held"][me] = state["card"]
    _log(state, "%s holds %s for later." % (pname(state, me), CARDS[state["card"]]["name"]))
    state["card"] = None
    _end_turn(state)


def discard_card(state):
    assert state["phase"] == "action"
    _log(state, "%s discards %s." % (pname(state, state["turn"]), CARDS[state["card"]]["name"]))
    _discard_and_end(state)


def held_playable(state):
    me = state["turn"]
    h = state["held"][me]
    return state["phase"] == "start" and h is not None and h != "SEATBELT" and \
        card_playable(state, h)


def play_held(state):
    """Pull the held card into hand (before drawing). Turn continues with a draw after."""
    assert held_playable(state)
    me = state["turn"]
    state["card"] = state["held"][me]
    state["held"][me] = None
    state["card_from_hold"] = True
    state["phase"] = "action"
    _log(state, "%s plays their held card: %s." % (pname(state, me), CARDS[state["card"]]["name"]))


def _finish_action(state):
    """After an action resolves: held-card plays continue to the draw; drawn ones end the turn."""
    if state["over"]:
        return
    if state["card"] and state["card"] != "PILOT":
        state["discard"].append(state["card"])
    from_hold = state["card_from_hold"]
    state["card"] = None
    state["card_from_hold"] = False
    if from_hold:
        if _check_game_end(state):
            return
        state["phase"] = "start"
        state["actor"] = state["turn"]
        state["_must_draw"] = True
    else:
        _end_turn(state)


def _seatbelt_blocks(state, victim):
    """If the victim holds the Seatbelt Sign, cancel the attack."""
    if state["held"][victim] == "SEATBELT":
        state["held"][victim] = None
        state["discard"].append("SEATBELT")
        _log(state, "💺 Ding! The Seatbelt Sign is on — %s cancels it." % pname(state, victim))
        _finish_action(state)
        return True
    return False


# ── Action targets ───────────────────────────────────────────────────────────

def upgrade_candidates(state):
    me = state["turn"]
    plane = get_plane(state["plane"])
    free_first = open_seats(state, "first")
    out = []
    seen_couples = set()
    for p in state["pax"].values():
        if p["owner"] != me or p["type"] not in UPGRADABLE:
            continue
        if p["status"] not in ("gate", "seated"):
            continue
        if p["status"] == "seated" and (plane["seats"][p["seat"]]["cabin"] == "first"):
            continue
        if p["type"] == "partner":
            if p["group"] in seen_couples:
                continue
            mates = _members(state, p["group"])
            if any(m["status"] not in ("gate", "seated") for m in mates):
                continue
            if any(m["status"] == "seated" and plane["seats"][m["seat"]]["cabin"] == "first" for m in mates):
                continue
            if _first_pair(state) is None:
                continue
            seen_couples.add(p["group"])
        else:
            if not free_first:
                continue
            if p["status"] == "seated" and is_locked(state, p["id"], plane):
                continue
        out.append(p["id"])
    return out


def _first_pair(state):
    plane = get_plane(state["plane"])
    free = set(open_seats(state, "first"))
    for row in plane["rows"]:
        if row["cabin"] != "first":
            continue
        for sec in row["sections"]:
            for a, b in zip(sec, sec[1:]):
                if a in free and b in free:
                    return (a, b)
        # across the aisle also counts as together
        secs = row["sections"]
        for i in range(len(secs) - 1):
            a, b = secs[i][-1], secs[i + 1][0]
            if a in free and b in free:
                return (a, b)
    return None


def switch_candidates(state):
    plane = get_plane(state["plane"])
    return [p["seat"] for p in seated_pax(state)
            if plane["seats"][p["seat"]]["cabin"] == "econ" and not is_locked(state, p["id"], plane)]


def switch_ok(state, a, b):
    plane = get_plane(state["plane"])
    cands = switch_candidates(state)
    if a == b or a not in cands or b not in cands:
        return False
    pa, pb = state["pax"][state["occ"][a]], state["pax"][state["occ"][b]]
    return _kid_ok(plane, pa["type"], b) and _kid_ok(plane, pb["type"], a)


def forgot_candidates(state):
    opp = 1 - state["turn"]
    plane = get_plane(state["plane"])
    return [p["id"] for p in seated_pax(state, opp) if not is_locked(state, p["id"], plane)]


def kicker_candidates(state):
    """[(kid_pid, victim_pid)] where the seat in front is an unlocked passenger."""
    me = state["turn"]
    plane = get_plane(state["plane"])
    if not _middle_destinations(state, None):
        return []
    out = []
    for k in seated_pax(state, me):
        if k["type"] != "kid":
            continue
        f = plane["infront"][k["seat"]]
        if f and f in state["occ"]:
            v = state["occ"][f]
            if not is_locked(state, v, plane) and _middle_destinations(state, v):
                out.append((k["id"], v))
    return out


def _middle_destinations(state, victim_pid):
    plane = get_plane(state["plane"])
    ptype = state["pax"][victim_pid]["type"] if victim_pid else "solo"
    return [s for s in open_seats(state)
            if plane["seats"][s]["kind"] == "middle" and _kid_ok(plane, ptype, s)]


def kicker_destinations(state, victim_pid):
    return _middle_destinations(state, victim_pid)


def work_candidates(state):
    return [p["id"] for p in seated_pax(state, state["turn"]) if p["type"] == "fa"]


def rebook_candidates(state):
    return [p["id"] for p in gate_pax(state, state["turn"])]


def family_candidates(state):
    me = state["turn"]
    groups = {}
    for p in state["pax"].values():
        if p["owner"] == me and p["group"]:
            groups.setdefault(p["group"], []).append(p)
    return [g for g, mem in groups.items() if all(m["status"] == "gate" for m in mem)]


def arrest_possible(state):
    me = state["turn"]
    plane = get_plane(state["plane"])
    mar = [p for p in seated_pax(state, me) if p["type"] == "marshal"]
    fug = [p for p in seated_pax(state, 1 - me) if p["type"] == "fugitive"]
    if not mar or not fug:
        return False
    if is_locked(state, fug[0]["id"], plane):
        return False
    return abs(plane["seats"][mar[0]["seat"]]["ridx"] - plane["seats"][fug[0]["seat"]]["ridx"]) <= 1


def card_playable(state, card):
    me = state["turn"]
    if card == "UPGRADE":
        return bool(upgrade_candidates(state))
    if card == "GROUP1":
        return True
    if card == "SWITCH":
        c = switch_candidates(state)
        return len(c) >= 2
    if card == "FORGOT":
        return bool(forgot_candidates(state))
    if card == "OVERBOOKED":
        return bool(gate_pax(state, 1 - me)) and not state["overbooked"][1 - me]
    if card == "ARREST":
        return arrest_possible(state)
    if card == "KICKER":
        return bool(kicker_candidates(state))
    if card == "WORK":
        return bool(work_candidates(state))
    if card == "REBOOKED":
        return bool(rebook_candidates(state))
    if card == "FAMILY":
        return bool(family_candidates(state)) and bool(open_seats(state))
    return False


# ── Playing action cards ─────────────────────────────────────────────────────

def play_card(state, pid=None, seat=None, seat2=None, group=None):
    """
    Play the action card in hand. Targets by card:
      UPGRADE pid · SWITCH seat, seat2 · FORGOT pid · KICKER pid (victim), seat (middle dest)
      WORK pid · REBOOKED pid · FAMILY group · GROUP1/OVERBOOKED/ARREST none
    """
    assert state["phase"] == "action"
    card = state["card"]
    me = state["turn"]
    opp = 1 - me
    plane = get_plane(state["plane"])
    if not card_playable(state, card):
        raise ValueError("That card can't be played right now.")

    if card == "GROUP1":
        state["extra_turn"] = True
        _log(state, "⏩ %s cuts the line!" % pname(state, me))
        _finish_action(state)
    elif card == "OVERBOOKED":
        if _seatbelt_blocks(state, opp):
            return
        state["overbooked"][opp] = True
        _log(state, "📛 Overbooked! %s's next passenger gets a middle seat." % pname(state, opp))
        _finish_action(state)
    elif card == "UPGRADE":
        if pid not in upgrade_candidates(state):
            raise ValueError("Can't upgrade that passenger.")
        p = state["pax"][pid]
        if p["type"] == "partner":
            a, b = _first_pair(state)
            mates = _members(state, p["group"])
            for m, s in zip(mates, (a, b)):
                _seat(state, m["id"], s)
            state["last"] = {"seats": [a, b], "by": me}
            _log(state, "🥂 %s's %s upgraded to First Class (%s, %s)." % (pname(state, me), p["glabel"], a, b))
        else:
            s = open_seats(state, "first")[0]
            _seat(state, pid, s)
            state["last"] = {"seats": [s], "by": me}
            _log(state, "🥂 %s upgraded to First Class (%s)." % (plabel(state, pid), s))
        _finish_action(state)
    elif card == "SWITCH":
        if not switch_ok(state, seat, seat2):
            raise ValueError("Those two can't switch.")
        a, b = state["occ"][seat], state["occ"][seat2]
        owners = {state["pax"][a]["owner"], state["pax"][b]["owner"]}
        if opp in owners and _seatbelt_blocks(state, opp):
            return
        _swap(state, seat, seat2)
        # hogs that move lose their armrest
        for b2, hog in list(state["blocked"].items()):
            if hog in (a, b):
                del state["blocked"][b2]
        state["last"] = {"seats": [seat, seat2], "by": me}
        _log(state, "🔄 %s swaps %s and %s." % (pname(state, me), seat, seat2))
        if _blitz_check(state, me):
            return
        _finish_action(state)
    elif card == "FORGOT":
        if pid not in forgot_candidates(state):
            raise ValueError("Can't send that passenger back.")
        if _seatbelt_blocks(state, opp):
            return
        old = state["pax"][pid]["seat"]
        _unseat(state, pid, "gate")
        state["last"] = {"seats": [old], "by": me}
        _log(state, "🎒 %s forgot something — back to the gate!" % plabel(state, pid))
        _finish_action(state)
    elif card == "ARREST":
        if _seatbelt_blocks(state, opp):
            return
        fug = [p for p in seated_pax(state, opp) if p["type"] == "fugitive"][0]
        old = fug["seat"]
        _unseat(state, fug["id"], "arrested")
        state["bonus"][me].append(("Arrest", 4, "Fugitive caught"))
        state["last"] = {"seats": [old], "by": me}
        _log(state, "🚔 The Air Marshal arrests the Fugitive! +4 to %s." % pname(state, me))
        _finish_action(state)
    elif card == "KICKER":
        pairs = [v for _k, v in kicker_candidates(state)]
        if pid not in pairs or seat not in kicker_destinations(state, pid):
            raise ValueError("Not a legal kick.")
        if state["pax"][pid]["owner"] == opp and _seatbelt_blocks(state, opp):
            return
        old = state["pax"][pid]["seat"]
        _seat(state, pid, seat)
        for b2, hog in list(state["blocked"].items()):
            if hog == pid:
                del state["blocked"][b2]
        state["last"] = {"seats": [old, seat], "by": me}
        _log(state, "🦶 Kick, kick, kick… %s moves from %s to middle seat %s." % (plabel(state, pid), old, seat))
        if _blitz_check(state, me):
            return
        _finish_action(state)
    elif card == "WORK":
        if pid not in work_candidates(state):
            raise ValueError("Not a seated flight attendant.")
        old = state["pax"][pid]["seat"]
        _unseat(state, pid, "working")
        state["last"] = {"seats": [old], "by": me}
        _log(state, "☕ A flight attendant heads to the galley. Seat %s opens up." % old)
        _finish_action(state)
    elif card == "REBOOKED":
        if pid not in rebook_candidates(state):
            raise ValueError("Not at the gate.")
        state["pax"][pid]["status"] = "rebooked"
        _log(state, "📅 %s takes a later flight." % plabel(state, pid))
        _finish_action(state)
    elif card == "FAMILY":
        if group not in family_candidates(state):
            raise ValueError("That group isn't all at the gate.")
        mem = _members(state, group)
        # parents first so kids can sit beside them
        mem.sort(key=lambda m: 0 if m["type"] == "parent" else 1)
        state["queue"] = [m["id"] for m in mem]
        state["phase"] = "family"
        _log(state, "👨‍👩‍👧 Family Boarding! %s boards %s together." % (pname(state, me), mem[0]["glabel"]))
        while state["queue"] and not legal_seats(state, state["queue"][0])[0]:
            state["queue"].pop(0)
        if not state["queue"]:
            _finish_action(state)
    else:
        raise ValueError("Unknown card %s" % card)


def finish_family_turn(state):
    """Called internally when the family queue empties (handled by _after_place)."""
    pass


# ── Events ───────────────────────────────────────────────────────────────────

def _resolve_event(state, card, rng):
    me = state["turn"]
    plane = get_plane(state["plane"])
    if card == "EMERGENCY_EXIT":
        exit_seats = [s for s in plane["econ_seats"] if plane["seats"][s]["exit"]]
        if all(s in state["occ"] for s in exit_seats):
            _end_game(state, "🚨 %s pops the emergency exit! Everyone off — game over." % pname(state, me))
            return
        _log(state, "🚨 Someone eyes the exit door… but the exit rows aren't full. Nothing happens.")
        _discard_and_end(state)
    elif card == "DOCTOR":
        docs = [p for p in seated_pax(state) if p["secret"] == "doctor"]
        others = [p for p in seated_pax(state) if p["secret"] != "doctor"]
        if not others:
            _log(state, "🩺 False alarm — nobody's sick.")
            _discard_and_end(state)
            return
        patient = rng.choice(others)
        ps = plane["seats"][patient["seat"]]
        _log(state, "🩺 Medical emergency in %s! Is there a doctor on board?" % patient["seat"])
        if not docs:
            _log(state, "No doctor aboard… the passenger turns out to be fine. Just dramatic.")
            _discard_and_end(state)
            return

        def dist(d):
            s = plane["seats"][d["seat"]]
            return (abs(s["ridx"] - ps["ridx"]), abs(s["section"] * 10 + s["pos"] - ps["section"] * 10 - ps["pos"]))
        for d in docs:
            d["revealed"] = True
        docs.sort(key=dist)
        if len(docs) == 2 and dist(docs[0]) == dist(docs[1]):
            for d in docs:
                state["bonus"][d["owner"]].append(("Doctor", 2, "Shared save"))
            _log(state, "Both doctors arrive at once (%s, %s) — +2 each." % (docs[0]["seat"], docs[1]["seat"]))
        else:
            d = docs[0]
            state["bonus"][d["owner"]].append(("Doctor", 5, "Saved a passenger"))
            _log(state, "🩺 %s's secret Doctor in %s saves the day! +5." % (pname(state, d["owner"]), d["seat"]))
        state["last"] = {"seats": [patient["seat"]] + [d["seat"] for d in docs], "by": me}
        _discard_and_end(state)
    elif card == "PILOT":
        state["pilot_done"] = True
        pilots = [p for p in seated_pax(state) if p["secret"] == "pilot"]
        _log(state, "👨‍✈️ The captain is incapacitated! Is anyone here a pilot?!")
        if not pilots:
            _log(state, "No pilots aboard. The first officer lands it just fine. Phew.")
            state["card"] = None
            _end_turn(state)
            return
        for p in pilots:
            p["revealed"] = True
        pilots.sort(key=lambda p: (plane["seats"][p["seat"]]["ridx"], p["seat"]))
        p = pilots[0]
        first = plane["seats"][p["seat"]]["cabin"] == "first"
        qs = rng.sample(range(len(QUIZ)), 2 if first else 1)
        state["quiz"] = {"pid": p["id"], "owner": p["owner"], "qs": qs, "i": 0, "q": qs[0],
                         "first": first, "answered": None}
        state["phase"] = "quiz"
        state["actor"] = p["owner"]
        state["last"] = {"seats": [p["seat"]], "by": p["owner"]}
        _log(state, "%s's secret Pilot in %s heads for the cockpit%s." % (
            pname(state, p["owner"]), p["seat"], " from First Class" if first else ""))


def answer_quiz(state, choice):
    assert state["phase"] == "quiz"
    qz = state["quiz"]
    q = QUIZ[qz["q"]]
    owner = qz["owner"]
    correct = choice == q["a"]
    qz["answered"] = choice
    qz["correct"] = correct
    state["last_quiz"] = dict(qz)
    if correct and qz["i"] + 1 < len(qz["qs"]):
        qz["i"] += 1
        qz["q"] = qz["qs"][qz["i"]]
        qz["answered"] = None
        _log(state, "✅ Correct! One more before touchdown…")
        return
    state["quiz"] = None
    state["card"] = None
    if correct and qz["first"]:
        state["bonus"][owner].append(("Pilot", 0, "Landed the plane"))
        _end_game(state, "👨‍✈️ %s's secret Pilot lands the plane! Instant win." % pname(state, owner),
                  winner=owner)
        return
    if correct:
        state["bonus"][owner].append(("Pilot", 8, "Landed the plane"))
        _log(state, "👨‍✈️ Greaser! %s's Pilot lands it. +8." % pname(state, owner))
    else:
        state["bonus"][owner].append(("Pilot", 2, "Go-around"))
        _log(state, "👨‍✈️ Wrong answer — go around! The Pilot still gets it down. +2.")
    state["actor"] = state["turn"]
    _end_turn(state)


def whose_move(state):
    return None if state["over"] else state["actor"]


# ══════════════════════════════════════════════════════════════════════════════
# Bot
# ══════════════════════════════════════════════════════════════════════════════

BOT_QUIZ_ACCURACY = 0.7


def _potential(state, me, plane):
    """Cheap lookahead: reward partial groups that are still close together."""
    val = 0.0
    for gid, mem in _groups(state).items():
        if mem[0]["owner"] != me:
            continue
        seated = [m for m in mem if m["status"] == "seated"]
        if not seated or len(seated) == len(mem):
            continue
        rows = [plane["seats"][m["seat"]]["ridx"] for m in seated]
        spread = max(rows) - min(rows)
        # open seats near the seated members (room for the rest)
        room = 0
        for m in seated:
            for n in plane["next_to"][m["seat"]] + plane["across"][m["seat"]]:
                if n not in state["occ"] and n not in state["blocked"]:
                    room += 1
        need = len(mem) - len(seated)
        val += 0.6 * min(room, need) - 0.5 * spread
    # Pilot wants to be near the front
    for p in seated_pax(state, me):
        if p["secret"] == "pilot":
            val += 0.05 * (len(plane["rows"]) - plane["seats"][p["seat"]]["ridx"])
    return val


def _eval(state, me):
    plane = get_plane(state["plane"])
    return score_diff(state, me) + _potential(state, me, plane)


def _best_placement(state, me, rng):
    """Try (passenger-type, seat) combos; return (pid, seat)."""
    reps = {}
    for p in gate_pax(state, me):
        key = (p["type"], p["group"], p["secret"])
        reps.setdefault(key, p["id"])
    best, best_v = None, None
    base_gate = len(gate_pax(state, me))
    for pid in reps.values():
        seats, _forced = legal_seats(state, pid)
        for s in seats:
            # place temporarily
            state["occ"][s] = pid
            p = state["pax"][pid]
            p["seat"], p["status"] = s, "seated"
            v = _eval(state, me) + rng.random() * 0.25
            # board groups/specials early when they fit; save solos for leftovers
            if p["type"] == "solo":
                v -= 0.3
            if state["mode"] == "blitz" and get_plane(state["plane"])["seats"][s]["kind"] == "middle":
                v -= 100
            del state["occ"][s]
            p["seat"], p["status"] = None, "gate"
            if best_v is None or v > best_v:
                best, best_v = (pid, s), v
    _ = base_gate
    return best


def _try(state, me, fn):
    """Evaluate a hypothetical change on a deep copy."""
    st = copy.deepcopy(state)
    fn(st)
    return _eval(st, me)


def bot_step(state, rng=None):
    """Make exactly one decision for the bot whose move it is. Returns False if not a bot's move."""
    rng = rng or _rng
    if state["over"]:
        return False
    me = state["actor"]
    if state["players"][me]["kind"] != "bot":
        return False
    phase = state["phase"]
    plane = get_plane(state["plane"])

    if phase == "start":
        if held_playable(state) and not state.get("_must_draw"):
            h = state["held"][me]
            if h in ("ARREST", "GROUP1", "KICKER", "FORGOT", "OVERBOOKED", "UPGRADE", "WORK") or \
                    (h == "REBOOKED" and _should_rebook(state, me)):
                play_held(state)
                return True
        state["_must_draw"] = False
        draw(state, rng)
        return True

    if phase == "quiz":
        q = QUIZ[state["quiz"]["q"]]
        if rng.random() < BOT_QUIZ_ACCURACY:
            ans = q["a"]
        else:
            ans = rng.choice([i for i in range(len(q["options"])) if i != q["a"]])
        answer_quiz(state, ans)
        return True

    if phase in ("place", "family"):
        if phase == "family":
            pid = state["queue"][0]
            seats, _ = legal_seats(state, pid)
            best_s, best_v = None, None
            for s in seats:
                v = _try(state, me, lambda st, s=s: _seat(st, pid, s)) + rng.random() * 0.1
                if best_v is None or v > best_v:
                    best_s, best_v = s, v
            place(state, pid, best_s)
        else:
            pid, s = _best_placement(state, me, rng)
            place(state, pid, s)
        return True

    if phase == "block":
        opts = block_options(state)
        # squeeze the opponent: block a window/aisle if possible
        opts.sort(key=lambda s: 0 if plane["seats"][s]["kind"] != "middle" else 1)
        block_seat(state, opts[0] if opts else None)
        return True

    if phase == "action":
        _bot_action(state, me, rng)
        return True
    return False


def _should_rebook(state, me):
    # rebook when more of my passengers are at the gate than seats left
    return len(gate_pax(state, me)) > len(open_seats(state)) // 2 + 1


def _bot_action(state, me, rng):
    card = state["card"]
    plane = get_plane(state["plane"])
    base = _eval(state, me)
    playable = card_playable(state, card)

    def hold_or_discard():
        if can_hold(state):
            hold_card(state)
        else:
            discard_card(state)

    if not playable:
        hold_or_discard()
        return
    if card in ("GROUP1", "OVERBOOKED", "ARREST"):
        play_card(state)
        return
    if card == "UPGRADE":
        cands = upgrade_candidates(state)
        sneaky = rng.random() < 0.5   # sometimes the bot goes for the pilot win
        best = max(cands, key=lambda pid: (sneaky and state["pax"][pid]["secret"] == "pilot",
                                           state["pax"][pid]["status"] == "seated" and
                                           plane["seats"][state["pax"][pid]["seat"]]["kind"] == "middle",
                                           state["pax"][pid]["type"] == "partner"))
        play_card(state, pid=best)
        return
    if card == "FORGOT":
        cands = forgot_candidates(state)
        best = max(cands, key=lambda pid: -_try(state, 1 - me, lambda st, pid=pid: _unseat(st, pid)))
        play_card(state, pid=best)
        return
    if card == "WORK":
        play_card(state, pid=work_candidates(state)[0])
        return
    if card == "KICKER":
        best, bv = None, None
        for _k, v in kicker_candidates(state):
            for d in kicker_destinations(state, v):
                val = _try(state, me, lambda st, v=v, d=d: _seat(st, v, d))
                if bv is None or val > bv:
                    best, bv = (v, d), val
        if bv is not None and bv > base:
            play_card(state, pid=best[0], seat=best[1])
        else:
            hold_or_discard()
        return
    if card == "SWITCH":
        cands = switch_candidates(state)
        pairs = []
        for i in range(len(cands)):
            for j in range(i + 1, len(cands)):
                pairs.append((cands[i], cands[j]))
        rng.shuffle(pairs)
        best, bv = None, None
        for a, b in pairs[:250]:
            if not switch_ok(state, a, b):
                continue

            def sw(st, a=a, b=b):
                _swap(st, a, b)
            val = _try(state, me, sw)
            if bv is None or val > bv:
                best, bv = (a, b), val
        if best and bv > base + 0.9:
            play_card(state, seat=best[0], seat2=best[1])
        else:
            hold_or_discard()
        return
    if card == "REBOOKED":
        if _should_rebook(state, me):
            # drop a lowly solo first
            cands = rebook_candidates(state)
            cands.sort(key=lambda pid: 0 if state["pax"][pid]["type"] == "solo" else 1)
            play_card(state, pid=cands[0])
        else:
            hold_or_discard()
        return
    if card == "FAMILY":
        cands = family_candidates(state)
        cands.sort(key=lambda g: -len(_members(state, g)))
        play_card(state, group=cands[0])
        return
    hold_or_discard()


def run_bots(state, rng=None, limit=500):
    """Advance the game while it's a bot's move."""
    n = 0
    while not state["over"] and state["players"][state["actor"]]["kind"] == "bot" and n < limit:
        bot_step(state, rng)
        n += 1
    return n
