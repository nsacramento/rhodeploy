"""
Rho — Middle Seat: Streamlit page

    page_middle_seat(guest=False)

Modes
  • vs the Rho bot (local; signed-in players get their record saved)
  • vs another Rho pilot (async, stored in Supabase, joined with a code / link)
  • guest play from the sign-in page (vs bot, nothing saved)

The seat map is a grid of st.buttons. Every seat button has a key
(ms_seat_<id>) so Streamlit gives it the CSS class st-key-ms_seat_<id>; we
colour seats by injecting one CSS rule per seat each render.
"""

import os
import time
import streamlit as st

from rho.modules import middle_seat as ms

_BOT = {"name": "Rho 🤖", "kind": "bot", "uid": None}

# Seconds between the bot's moves so you can follow along
BOT_SPEEDS = {"Relaxed": 1.6, "Normal": 1.0, "Fast": 0.45}

PHASE_HINT = {
    "place": "Pick a passenger, then tap a glowing seat.",
    "family": "Family Boarding — seat each member anywhere open.",
    "block": "Your Armrest Hog claims a seat next to him. Tap one to block it.",
}

# ══════════════════════════════════════════════════════════════════════════════
# Styles
# ══════════════════════════════════════════════════════════════════════════════

_BASE_CSS = """
<style>
.st-key-ms_map { max-width: 620px; }
.st-key-ms_map [data-testid="stHorizontalBlock"] {
    gap: 4px !important; flex-wrap: nowrap !important; margin-bottom: -10px;
}
.st-key-ms_map [data-testid="stHorizontalBlock"] > div,
.st-key-ms_map [data-testid="stColumn"] {
    min-width: 0 !important; flex: 1 1 0 !important; width: auto !important;
}
.st-key-ms_map button {
    min-height: 2.15rem !important; height: 2.15rem; padding: 0 !important;
    font-size: 0.82rem !important; font-weight: 700 !important; width: 100%;
    border-radius: 7px 7px 4px 4px !important; line-height: 1 !important;
    border: 1.5px solid #cbd5e1 !important; background: #f8fafc !important; color: #94a3b8 !important;
}
.st-key-ms_map button:disabled { opacity: 1 !important; cursor: default !important; }
.st-key-ms_map button p { font-size: 0.95rem !important; }
.ms-aisle { text-align: center; font-size: 0.68rem; color: #94a3b8; padding-top: 0.6rem;
            font-weight: 600; white-space: nowrap; }
.ms-aisle.exit { color: #dc2626; font-weight: 800; }
.ms-cabin { font-size: 0.72rem; font-weight: 800; letter-spacing: 1.5px; color: #64748b;
            text-transform: uppercase; margin: 0.6rem 0 0.35rem; }
.ms-nose { text-align:center; font-size: 0.75rem; color:#64748b; border-radius: 120px 120px 0 0;
           border: 2px solid #e2e8f0; border-bottom: none; padding: 0.6rem 0 0.2rem; max-width: 620px;
           margin-bottom: 0.4rem; background: linear-gradient(#f1f5f9, #fff); }
.ms-card { border-radius: 14px; padding: 0.9rem 1.1rem; color: #fff; margin-bottom: 0.6rem;
           box-shadow: 0 6px 18px rgba(15,23,42,0.18); }
.ms-card.seat   { background: linear-gradient(135deg, #1d4ed8, #3b82f6); }
.ms-card.action { background: linear-gradient(135deg, #6d28d9, #a855f7); }
.ms-card.event  { background: linear-gradient(135deg, #b91c1c, #f97316); }
.ms-card .e { font-size: 1.8rem; line-height: 1; }
.ms-card .n { font-size: 1.15rem; font-weight: 800; margin-top: 0.2rem; }
.ms-card .t { font-size: 0.86rem; opacity: 0.95; margin-top: 0.2rem; }
.ms-card .k { font-size: 0.66rem; letter-spacing: 1.5px; text-transform: uppercase; opacity: 0.8; }
.ms-score { display:flex; gap: 0.5rem; margin-bottom: 0.6rem; }
.ms-score > div { flex: 1; border-radius: 12px; padding: 0.55rem 0.8rem; border: 2px solid #e2e8f0; }
.ms-score .me   { border-color: #2563eb; background: #eff6ff; }
.ms-score .opp  { border-color: #ea580c; background: #fff7ed; }
.ms-score .turn { box-shadow: 0 0 0 3px rgba(34,197,94,0.45); }
.ms-score .nm { font-size: 0.78rem; font-weight: 700; color: #334155; }
.ms-score .pt { font-size: 1.6rem; font-weight: 800; color: #0f172a; line-height: 1.1; }
.ms-score .sub { font-size: 0.7rem; color: #64748b; }
.ms-legend { font-size: 0.72rem; color: #64748b; margin-top: 0.9rem; line-height: 1.9; }
.ms-legend span { display:inline-block; width: 12px; height: 12px; border-radius: 3px;
                  vertical-align: -1px; margin: 0 3px 0 8px; border: 1px solid #94a3b8; }
.ms-hero { background: linear-gradient(135deg, #0a1628 0%, #1a4f7a 60%, #4a90c4 100%);
           color: #fff; border-radius: 16px; padding: 1.3rem 1.5rem; margin-bottom: 1rem; }
.ms-hero h2 { color: #fff; margin: 0; font-size: 1.7rem; }
.ms-hero p { color: #cfe3f7; margin: 0.25rem 0 0; }
.ms-secret { background: #0f172a; color: #e2e8f0; border-radius: 10px; padding: 0.55rem 0.8rem;
             font-size: 0.8rem; margin: 0.5rem 0; }
/* ── Card table ─────────────────────────────────────────── */
.ms-table { background: radial-gradient(ellipse at top, #1f7a4d 0%, #14532d 75%);
            border-radius: 16px; padding: 14px 14px 12px; margin-bottom: 0.7rem;
            box-shadow: inset 0 0 0 3px #0f3d22, 0 6px 16px rgba(15,23,42,0.18);
            display: flex; gap: 14px; align-items: flex-start; }
.ms-table .lbl { color: #bbf7d0; font-size: 0.66rem; font-weight: 800; letter-spacing: 1.4px;
                 text-transform: uppercase; margin-bottom: 5px; }
.ms-deck { position: relative; width: 74px; height: 104px; flex: 0 0 74px; margin-top: 18px; }
.ms-back { position: absolute; width: 70px; height: 98px; border-radius: 9px;
           background: repeating-linear-gradient(45deg, #1e3a8a 0 6px, #1d4ed8 6px 12px);
           border: 3px solid #fff; box-shadow: 0 2px 5px rgba(0,0,0,0.35);
           color: #fff; font-weight: 900; font-size: 1.6rem; display: flex;
           align-items: center; justify-content: center; font-family: Georgia, serif; }
.ms-back.b1 { top: 4px; left: 4px; } .ms-back.b2 { top: 2px; left: 2px; } .ms-back.b3 { top: 0; left: 0; }
.ms-deck .cnt { position: absolute; top: 106px; width: 74px; text-align: center; color: #dcfce7;
                font-size: 0.66rem; font-weight: 700; }
.ms-slot { flex: 1; min-width: 0; }
.ms-pc { background: #fffdf7; border-radius: 12px; position: relative; overflow: hidden;
         box-shadow: 0 8px 18px rgba(0,0,0,0.35); min-height: 168px; padding: 0 0 10px;
         animation: msflip 0.45s ease-out; transform-origin: center; }
@keyframes msflip { from { transform: perspective(600px) rotateY(85deg) scale(0.92); opacity: 0.2; }
                    to   { transform: perspective(600px) rotateY(0) scale(1); opacity: 1; } }
.ms-pc .band { color: #fff; font-size: 0.64rem; font-weight: 800; letter-spacing: 1.6px;
               text-transform: uppercase; padding: 5px 10px; }
.ms-pc.seat .band { background: #2563eb; } .ms-pc.action .band { background: #7c3aed; }
.ms-pc.event .band { background: #dc2626; }
.ms-pc .corner { position: absolute; font-size: 0.95rem; }
.ms-pc .corner.tl { top: 26px; left: 9px; } .ms-pc .corner.br { bottom: 6px; right: 9px; transform: rotate(180deg); }
.ms-pc .big { text-align: center; font-size: 2.6rem; line-height: 1; margin-top: 10px; }
.ms-pc .nm { text-align: center; font-weight: 900; font-size: 1.08rem; color: #0f172a; margin: 6px 10px 2px; }
.ms-pc .tx { text-align: center; font-size: 0.8rem; color: #475569; margin: 0 14px; line-height: 1.3; }
.ms-pc.empty { background: transparent; border: 2px dashed #86efac; box-shadow: none; animation: none;
               display: flex; align-items: center; justify-content: center; color: #bbf7d0;
               font-size: 0.85rem; font-weight: 600; text-align: center; padding: 10px; }
.ms-hand { display: flex; gap: 6px; margin-top: 8px; align-items: center; color: #dcfce7; font-size: 0.7rem; }
.ms-mini { background: #fffdf7; border-radius: 6px; padding: 3px 7px; color: #0f172a; font-weight: 700;
           font-size: 0.72rem; box-shadow: 0 2px 4px rgba(0,0,0,0.3); }
.ms-mini.backside { background: repeating-linear-gradient(45deg, #1e3a8a 0 4px, #1d4ed8 4px 8px);
                    color: #fff; border: 2px solid #fff; }
/* ── Turn banner ─────────────────────────────────────────── */
.ms-turn { border-radius: 999px; padding: 6px 14px; font-weight: 800; font-size: 0.85rem;
           display: inline-block; margin-bottom: 0.55rem; }
.ms-turn.me { background: #dcfce7; color: #166534; animation: mspulse 1.6s ease-in-out infinite; }
.ms-turn.opp { background: #ffedd5; color: #9a3412; }
@keyframes mspulse { 0%,100% { box-shadow: 0 0 0 0 rgba(34,197,94,0.5); }
                     50% { box-shadow: 0 0 0 7px rgba(34,197,94,0); } }
/* ── Play-by-play ────────────────────────────────────────── */
.ms-feed { border: 1.5px solid #e2e8f0; border-radius: 12px; padding: 6px 10px; margin: 0.6rem 0;
           background: #fff; font-size: 0.8rem; }
.ms-feed .h { font-size: 0.66rem; font-weight: 800; letter-spacing: 1.4px; color: #64748b;
              text-transform: uppercase; margin: 2px 0 4px; }
.ms-feed .ln { padding: 3px 0 3px 8px; border-left: 3px solid #e2e8f0; margin: 2px 0; color: #334155; }
.ms-feed .ln.me  { border-left-color: #2563eb; }
.ms-feed .ln.opp { border-left-color: #ea580c; }
.ms-feed .ln.new { background: #fffbeb; font-weight: 600; animation: msfade 1.2s ease-out; }
@keyframes msfade { from { background: #fde68a; } to { background: #fffbeb; } }
/* ── Gate (passenger tokens) ─────────────────────────────── */
.ms-sec { font-size: 0.7rem; font-weight: 800; letter-spacing: 1.4px; color: #64748b;
          text-transform: uppercase; margin: 0.4rem 0 0.3rem; }
.st-key-ms_gate [data-testid="stHorizontalBlock"] { gap: 6px !important; }
.st-key-ms_gate button { min-height: 2.4rem !important; padding: 2px 6px !important;
    border-radius: 10px !important; border: 1.5px solid #cbd5e1 !important; background: #fff !important;
    box-shadow: 0 2px 0 #cbd5e1 !important; }
.st-key-ms_gate button p { font-size: 0.78rem !important; font-weight: 700 !important; line-height: 1.15 !important; }
.st-key-ms_gate button:hover { border-color: #7c3aed !important; transform: translateY(-1px); }
.ms-pass { border: 2px dashed #7c3aed; border-radius: 12px; padding: 8px 12px; background: #faf5ff;
           margin: 0.3rem 0 0.4rem; font-size: 0.8rem; color: #4c1d95; }
.ms-pass b { font-size: 0.92rem; }
@keyframes msseat { 0% { box-shadow: 0 0 0 0 rgba(250,204,21,0.95); } 100% { box-shadow: 0 0 0 9px rgba(250,204,21,0); } }
.ms-mobile-only { display: none; }
@media (max-width: 640px) {
  .ms-mobile-only { display: block; position: sticky; top: 0; z-index: 50; }
}
.ms-strip { border-radius: 10px; padding: 0.45rem 0.7rem; color: #fff; font-size: 0.82rem;
            margin-bottom: 0.5rem; box-shadow: 0 4px 12px rgba(15,23,42,0.2); }
.ms-strip.seat { background: #2563eb; } .ms-strip.action { background: #7c3aed; }
.ms-strip.event { background: #dc2626; } .ms-strip.wait { background: #475569; }
.ms-banner { border-radius: 12px; padding: 0.9rem 1.1rem; font-weight: 700; margin-bottom: 0.8rem; }
.ms-banner.win  { background: #dcfce7; color: #14532d; border: 2px solid #22c55e; }
.ms-banner.loss { background: #fee2e2; color: #7f1d1d; border: 2px solid #ef4444; }
.ms-banner.tie  { background: #e0e7ff; color: #312e81; border: 2px solid #6366f1; }
</style>
"""

_COLORS = {
    # state: (background, border, text)
    "legal":    ("#dcfce7", "#16a34a", "#166534"),
    "pick":     ("#ede9fe", "#7c3aed", "#5b21b6"),   # target for an action card
    "selected": ("#7c3aed", "#5b21b6", "#ffffff"),
    "mine":     ("#dbeafe", "#2563eb", "#1e3a8a"),
    "theirs":   ("#ffedd5", "#ea580c", "#7c2d12"),
    "blocked":  ("#e2e8f0", "#94a3b8", "#475569"),
    "open_mid": ("#fff1f2", "#fecdd3", "#fda4af"),
    "open_first": ("#fefce8", "#fde68a", "#ca8a04"),
}


def _seat_css(sid, kind, last=False):
    bg, bd, fg = _COLORS[kind]
    glow = ""
    if kind in ("legal", "pick"):
        glow = "box-shadow: 0 0 0 2px %s55, 0 0 10px %s88 !important;" % (bd, bd)
    if last:
        glow = "box-shadow: 0 0 0 3px #facc15 !important; animation: msseat 1.1s ease-out 2;"
    return (".st-key-ms_seat_%s button{background:%s !important;border-color:%s !important;"
            "color:%s !important;%s}" % (sid, bg, bd, fg, glow))


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]


def _ctx(state):
    return "%s-%s-%s-%s" % (state["turn_no"], state["phase"], state["actor"], state.get("log_n", 0))


def _sel(state):
    """Per-decision UI selection (first seat of a swap, kick victim, …)."""
    s = st.session_state.get("ms_sel")
    if not s or s.get("ctx") != _ctx(state):
        s = {"ctx": _ctx(state)}
        st.session_state.ms_sel = s
    return s


def _secret_icon(p):
    return {"doctor": "🩺", "pilot": "👨‍✈️"}.get(p["secret"], "")


def _pax_choices(state, me):
    """One representative pid per distinct (type, group, secret) still at the gate."""
    reps, counts = {}, {}
    for p in sorted(ms.gate_pax(state, me), key=lambda p: p["id"]):
        k = (p["type"], p["group"], p["secret"])
        reps.setdefault(k, p["id"])
        counts[k] = counts.get(k, 0) + 1
    out = []
    for k, pid in reps.items():
        p = state["pax"][pid]
        t = ms.TYPES[p["type"]]
        lbl = "%s %s" % (t["emoji"], p["glabel"] if p["type"] in ("partner", "bff") else t["label"])
        if p["type"] in ("parent", "kid"):
            lbl = "%s %s · %s" % (t["emoji"], t["label"], p["glabel"])
        if counts[k] > 1:
            lbl += " ×%d" % counts[k]
        if p["secret"]:
            lbl += " " + _secret_icon(p)
        out.append((pid, lbl))
    # groups first, then specials, then solos
    order = {"parent": 0, "kid": 1, "partner": 2, "bff": 3, "fa": 4, "solo": 9}
    out.sort(key=lambda x: order.get(state["pax"][x[0]]["type"], 5))
    return out


def _seat_help(state, sid, me):
    plane = ms.get_plane(state["plane"])
    s = plane["seats"][sid]
    bits = ["%s · %s%s" % (sid, s["kind"], " · exit row" if s["exit"] else "")]
    if sid in state["occ"]:
        p = state["pax"][state["occ"][sid]]
        who = "Yours" if p["owner"] == me else state["players"][p["owner"]]["name"]
        bits.append("%s — %s" % (ms.plabel(state, p["id"], reveal_for=me), who))
        bits.append(ms.TYPES[p["type"]]["desc"])
        if ms.is_locked(state, p["id"], plane):
            bits.append("🔒 Locked")
    elif sid in state["blocked"]:
        bits.append("🚫 Blocked by an Armrest Hog")
    elif s["kind"] == "middle" and s["cabin"] == "econ":
        bits.append("Middle seat: %d" % (-3 if s["center_middle"] else -2))
    return "  \n".join(bits)


# ══════════════════════════════════════════════════════════════════════════════
# Seat map
# ══════════════════════════════════════════════════════════════════════════════

def _render_map(state, me, clickable, kinds_override, on_click):
    """
    clickable: set of seat ids that respond to taps.
    kinds_override: {sid: 'legal'|'pick'|'selected'} colouring for interactive seats.
    on_click(sid): called when a clickable seat is tapped.
    """
    plane = ms.get_plane(state["plane"])
    last = set((state.get("last") or {}).get("seats") or [])
    css = []
    clicked = None
    with st.container(key="ms_map"):
        st.markdown("<div class='ms-nose'>✈ cockpit</div>", unsafe_allow_html=True)
        cabin = None
        for row in plane["rows"]:
            if row["cabin"] != cabin:
                cabin = row["cabin"]
                st.markdown("<div class='ms-cabin'>%s</div>" % (
                    "First Class · upgrade only" if cabin == "first" else "Economy"),
                    unsafe_allow_html=True)
            secs = row["sections"]
            econ_layout = ms.PLANES[state["plane"]]["econ_layout"]
            n_cells = sum(len(x) for x in econ_layout) + len(econ_layout) - 1
            cols = st.columns(n_cells)
            ci = 0
            for si, sec in enumerate(secs):
                # line narrower first-class sections up with the economy sections
                pad = len(econ_layout[si]) - len(sec)
                if si == 0:
                    lead = 0
                elif si == len(secs) - 1:
                    lead = pad
                else:
                    lead = pad // 2
                ci += lead
                for sid in sec:
                    with cols[ci]:
                        clicked = _seat_button(state, me, sid, clickable, kinds_override,
                                               last, css) or clicked
                    ci += 1
                ci += pad - lead
                if si < len(secs) - 1:
                    s0 = plane["seats"][sec[0]]
                    with cols[ci]:
                        st.markdown("<div class='ms-aisle%s'>%s</div>" % (
                            " exit" if s0["exit"] else "",
                            ("%d🚪" % row["row"]) if s0["exit"] else row["row"]),
                            unsafe_allow_html=True)
                    ci += 1
        st.markdown(
            "<div class='ms-legend'>"
            "<span style='background:#dbeafe;border-color:#2563eb'></span>you"
            "<span style='background:#ffedd5;border-color:#ea580c'></span>opponent"
            "<span style='background:#dcfce7;border-color:#16a34a'></span>you can sit here"
            "<span style='background:#ede9fe;border-color:#7c3aed'></span>card target"
            "<span style='background:#fff1f2;border-color:#fecdd3'></span>middle seat"
            "<span style='background:#e2e8f0'></span>blocked"
            "<span style='background:#fff;border:2px solid #facc15'></span>last move"
            "<br>🚪 exit row (no kids) · rows next to the exits are over the wing</div>",
            unsafe_allow_html=True)
    st.markdown("<style>%s</style>" % "".join(css), unsafe_allow_html=True)
    if clicked:
        on_click(clicked)


def _seat_button(state, me, sid, clickable, kinds_override, last, css):
    plane = ms.get_plane(state["plane"])
    s = plane["seats"][sid]
    occ = state["occ"]
    if sid in occ:
        p = state["pax"][occ[sid]]
        label = ms.TYPES[p["type"]]["emoji"]
        if p["secret"] and (p["revealed"] or p["owner"] == me):
            label += _secret_icon(p)
        if ms.is_locked(state, p["id"], plane):
            label += "🔒" if s["cabin"] != "first" else ""
        kind = "mine" if p["owner"] == me else "theirs"
    elif sid in state["blocked"]:
        label, kind = "🚫", "blocked"
    else:
        label = s["letter"]
        if s["cabin"] == "first":
            kind = "open_first"
        elif s["kind"] == "middle":
            kind = "open_mid"
        else:
            kind = None
    if sid in kinds_override:
        kind = kinds_override[sid]
    if kind:
        css.append(_seat_css(sid, kind, last=sid in last))
    elif sid in last:
        css.append(".st-key-ms_seat_%s button{box-shadow:0 0 0 3px #facc15 !important;"
                   "animation: msseat 1.1s ease-out 2;}" % sid)
    return st.button(label, key="ms_seat_%s" % sid, disabled=sid not in clickable,
                     help=_seat_help(state, sid, me), use_container_width=True) and sid


# ══════════════════════════════════════════════════════════════════════════════
# Game screen
# ══════════════════════════════════════════════════════════════════════════════

def _card_html(card, label=None):
    c = ms.CARDS[card]
    kind_name = {"seat": "Seat card", "action": "Action card", "event": "Event"}[c["kind"]]
    return ("<div class='ms-card %s'><div class='k'>%s</div><div class='e'>%s</div>"
            "<div class='n'>%s</div><div class='t'>%s</div></div>"
            % (c["kind"], label or kind_name, c["emoji"], c["name"], c["text"]))


def _playing_card(card, owner_label):
    c = ms.CARDS[card]
    kind_name = {"seat": "Seat card", "action": "Action card", "event": "Event!"}[c["kind"]]
    return ("<div class='lbl'>%s</div>"
            "<div class='ms-pc %s' data-k='%s'><div class='band'>%s</div>"
            "<div class='corner tl'>%s</div><div class='big'>%s</div>"
            "<div class='nm'>%s</div><div class='tx'>%s</div><div class='corner br'>%s</div></div>"
            % (owner_label, c["kind"], card, kind_name, c["emoji"], c["emoji"], c["name"], c["text"], c["emoji"]))


def _card_table(state, me, card=None, owner=None, empty_note=None):
    """Green felt: the deck, the face-up card, and both players' held cards."""
    left = len(state["deck"])
    deck = ("<div class='ms-deck'><div class='ms-back b1'></div><div class='ms-back b2'></div>"
            "<div class='ms-back b3'>ρ</div><div class='cnt'>%d left</div></div>" % left)
    if card:
        who = "Your card" if owner == me else "%s's card" % state["players"][owner]["name"]
        face = _playing_card(card, who)
    else:
        face = ("<div class='lbl'>&nbsp;</div><div class='ms-pc empty'>%s</div>"
                % (empty_note or "Waiting for the next draw…"))
    mine = state["held"][me]
    theirs = state["held"][1 - me]
    hand = "<div class='ms-hand'>Your hand: %s &nbsp; %s: %s</div>" % (
        ("<span class='ms-mini'>%s %s</span>" % (ms.CARDS[mine]["emoji"], ms.CARDS[mine]["name"]))
        if mine else "<span style='opacity:.7'>empty</span>",
        state["players"][1 - me]["name"],
        "<span class='ms-mini backside'>1 card</span>" if theirs else "<span style='opacity:.7'>empty</span>")
    st.markdown("<div class='ms-table'>%s<div class='ms-slot'>%s%s</div></div>" % (deck, face, hand),
                unsafe_allow_html=True)


def _turn_banner(state, me):
    if state["over"]:
        return
    a = state["actor"]
    if a == me:
        txt = "✈ Your move" if state["phase"] != "quiz" else "👨‍✈️ You have the controls!"
        st.markdown("<div class='ms-turn me'>%s</div>" % txt, unsafe_allow_html=True)
    else:
        name = state["players"][a]["name"]
        verb = "is thinking…" if state["players"][a]["kind"] == "bot" else "is boarding…"
        st.markdown("<div class='ms-turn opp'>%s %s</div>" % (name, verb), unsafe_allow_html=True)


def _feed(state, me, n=7):
    """Play-by-play: newest first. Lines since your last move are highlighted."""
    log = state["log"]
    who = state.get("log_who") or [0] * len(log)
    who = who[-len(log):] if len(who) >= len(log) else [0] * (len(log) - len(who)) + who
    # trailing run of the opponent's lines = what happened since you last moved
    new_from = len(log)
    for i in range(len(log) - 1, -1, -1):
        if who[i] == me:
            break
        new_from = i
    rows = []
    for i in range(len(log) - 1, max(-1, len(log) - 1 - n), -1):
        cls = "me" if who[i] == me else "opp"
        if i >= new_from or i == len(log) - 1:
            cls += " new"
        rows.append("<div class='ln %s'>%s</div>" % (cls, log[i]))
    st.markdown("<div class='ms-feed'><div class='h'>📣 Play-by-play</div>%s</div>" % "".join(rows),
                unsafe_allow_html=True)


_POINTS = {
    "solo": "1 pt seated.",
    "partner": "1 pt each · +2 when the couple sits side by side or across the aisle.",
    "bff": "1 pt each · +3 when all three share a row.",
    "parent": "1 pt each · family bonus +3 / +5 / +6 when complete.",
    "kid": "1 pt each · counts toward the family bonus. No exit rows.",
    "fa": "2 pts seated · 4 if sent to the galley (Get to Work).",
    "marshal": "1 pt · arrest the other Fugitive within 1 row for +4.",
    "fugitive": "1 pt · +4 if never caught.",
    "recliner": "1 pt · person behind gets −1 (you +1 if it's theirs).",
    "chatty": "1 pt · +2 next to an opponent (they get −1 each).",
    "hog": "1 pt · blocks one seat next to him.",
    "nervous": "1 pt · +3 next to or across from any flight attendant.",
    "avgeek": "1 pt · +3 in a window seat over the wing.",
}


def _pax_tip(state, pid, me):
    p = state["pax"][pid]
    t = ms.TYPES[p["type"]]
    lines = ["%s %s" % (t["emoji"], t["label"]), t["desc"], "Points: " + _POINTS.get(p["type"], "")]
    if p["glabel"]:
        mem = ms._members(state, p["group"])
        aboard = sum(1 for m in mem if m["status"] == "seated")
        lines.append("%s: %d of %d aboard" % (p["glabel"], aboard, len(mem)))
    if p["secret"] and p["owner"] == me:
        lines.append("🤫 This one is your secret %s!" % p["secret"].capitalize())
    lines.append("Middle seat: −2 unless sandwiched by their own group.")
    return "  \n".join(lines)


def _render_gate(state, me, sel, pax_pick):
    """Your gate: a tappable token per passenger type. Hover for the details."""
    choices = _pax_choices(state, me)
    st.markdown("<div class='ms-sec'>🧳 Your gate — tap who boards next</div>", unsafe_allow_html=True)
    css = []
    with st.container(key="ms_gate"):
        cols = st.columns(3)
        for i, (pid, lbl) in enumerate(choices):
            with cols[i % 3]:
                if st.button(lbl, key="ms_pax_%s" % pid, help=_pax_tip(state, pid, me),
                             use_container_width=True):
                    sel["pax"] = pid
                    st.rerun()
            if pid == pax_pick:
                css.append(".st-key-ms_pax_%s button{background:#7c3aed !important;border-color:#5b21b6 !important;"
                           "box-shadow:0 2px 0 #4c1d95 !important;}.st-key-ms_pax_%s button p{color:#fff !important;}"
                           % (pid, pid))
    st.markdown("<style>%s</style>" % "".join(css), unsafe_allow_html=True)
    p = state["pax"][pax_pick]
    t = ms.TYPES[p["type"]]
    st.markdown("<div class='ms-pass'>🎫 <b>Now boarding: %s %s</b>%s<br>%s<br><i>%s</i></div>" % (
        t["emoji"], t["label"], (" · " + p["glabel"]) if p["glabel"] else "",
        t["desc"], _POINTS.get(p["type"], "")), unsafe_allow_html=True)


def _scoreboard(state, me):
    sc = ms.compute_scores(state)
    html = ["<div class='ms-score'>"]
    for i in (me, 1 - me):
        cls = "me" if i == me else "opp"
        if not state["over"] and state["actor"] == i:
            cls += " turn"
        gate = len(ms.gate_pax(state, i))
        held = state["held"][i]
        sub = "%d at the gate" % gate if gate else "everyone aboard"
        if held:
            sub += " · holding %s" % (ms.CARDS[held]["name"] if i == me else "a card")
        html.append("<div class='%s'><div class='nm'>%s%s</div><div class='pt'>%d</div>"
                    "<div class='sub'>%s</div></div>" % (
                        cls, state["players"][i]["name"],
                        " (you)" if i == me and state["players"][i]["name"] != "You" else "",
                        sc[i]["total"], sub))
    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)
    return sc


def _breakdown(state, me, sc):
    rows = []
    cats = [c for c in ms.SCORE_ORDER if c in sc[0]["items"] or c in sc[1]["items"]]
    for c in cats:
        rows.append("| %s | %+d | %+d |" % (c, sc[me]["items"].get(c, 0), sc[1 - me]["items"].get(c, 0)))
    if not rows:
        st.caption("No points yet.")
        return
    st.markdown("| | %s | %s |\n|---|---:|---:|\n%s\n| **Total** | **%d** | **%d** |" % (
        "You", state["players"][1 - me]["name"], "\n".join(rows),
        sc[me]["total"], sc[1 - me]["total"]))
    if not state["over"]:
        st.caption("Passengers still at the gate when the doors close cost −2 each.")


def _secrets_box(state, me):
    lines = []
    for p in state["pax"].values():
        if p["owner"] == me and p["secret"]:
            where = p["seat"] or {"gate": "at the gate", "rebooked": "rebooked",
                                  "arrested": "gone"}.get(p["status"], p["status"])
            lines.append("%s Secret %s: <b>%s</b> (%s)%s" % (
                _secret_icon(p), p["secret"].capitalize(),
                ms.plabel(state, p["id"]), where, " — revealed" if p["revealed"] else ""))
    st.markdown("<div class='ms-secret'>🤫 Only you can see this<br>%s</div>" % "<br>".join(lines),
                unsafe_allow_html=True)


def _render_game(state, me, commit, opp_waiting_note=None):
    """
    Draw the board + controls. `commit(state)` persists a change (and runs the bot
    for local games), then we rerun.
    """
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    plane = ms.get_plane(state["plane"])
    my_move = (not state["over"]) and state["actor"] == me
    phase = state["phase"]
    sel = _sel(state)

    # Auto-draw at the start of my turn (unless I could play a held card first)
    if my_move and phase == "start" and (state.get("_must_draw") or not ms.held_playable(state)):
        ms.draw(state)
        commit(state)
        st.rerun()

    clickable, kinds, on_click = set(), {}, (lambda sid: None)

    # ── Decide what the map does this render ─────────────────────────────────
    pax_pick = None
    if my_move and phase in ("place", "family"):
        if phase == "family":
            pax_pick = state["queue"][0]
        else:
            choices = _pax_choices(state, me)
            ids = [c[0] for c in choices]
            labels = dict(choices)
            default = next((pid for pid in ids if state["pax"][pid]["type"] != "kid"), ids[0])
            if sel.get("pax") not in ids:
                sel["pax"] = default
            pax_pick = sel["pax"]
        seats, forced = ms.legal_seats(state, pax_pick)
        clickable = set(seats)
        kinds = {s: "legal" for s in seats}

        def on_click(sid, pid=pax_pick):
            ms.place(state, pid, sid)
            commit(state)
            st.rerun()
    elif my_move and phase == "block":
        opts = ms.block_options(state)
        clickable = set(opts)
        kinds = {s: "pick" for s in opts}

        def on_click(sid):
            ms.block_seat(state, sid)
            commit(state)
            st.rerun()
    elif my_move and phase == "action":
        card = state["card"]
        if card == "SWITCH" and ms.card_playable(state, card):
            cands = ms.switch_candidates(state)
            first = sel.get("seat")
            if first and first in cands:
                partners = [s for s in cands if ms.switch_ok(state, first, s)]
                clickable = set(partners) | {first}
                kinds = {s: "pick" for s in partners}
                kinds[first] = "selected"
            else:
                clickable = set(cands)
                kinds = {s: "pick" for s in cands}

            def on_click(sid):
                f = sel.get("seat")
                if f == sid:
                    sel["seat"] = None
                elif f and ms.switch_ok(state, f, sid):
                    ms.play_card(state, seat=f, seat2=sid)
                    commit(state)
                else:
                    sel["seat"] = sid
                st.rerun()
        elif card == "FORGOT" and ms.card_playable(state, card):
            seats = [state["pax"][pid]["seat"] for pid in ms.forgot_candidates(state)]
            clickable = set(seats)
            kinds = {s: "pick" for s in seats}

            def on_click(sid):
                ms.play_card(state, pid=state["occ"][sid])
                commit(state)
                st.rerun()
        elif card == "WORK" and ms.card_playable(state, card):
            seats = [state["pax"][pid]["seat"] for pid in ms.work_candidates(state)]
            clickable = set(seats)
            kinds = {s: "pick" for s in seats}

            def on_click(sid):
                ms.play_card(state, pid=state["occ"][sid])
                commit(state)
                st.rerun()
        elif card == "UPGRADE" and ms.card_playable(state, card):
            seats = [state["pax"][pid]["seat"] for pid in ms.upgrade_candidates(state)
                     if state["pax"][pid]["seat"]]
            clickable = set(seats)
            kinds = {s: "pick" for s in seats}

            def on_click(sid):
                ms.play_card(state, pid=state["occ"][sid])
                commit(state)
                st.rerun()
        elif card == "KICKER" and ms.card_playable(state, card):
            victims = [v for _k, v in ms.kicker_candidates(state)]
            vsel = sel.get("victim")
            if vsel in victims:
                dests = ms.kicker_destinations(state, vsel)
                clickable = set(dests)
                kinds = {s: "legal" for s in dests}
                kinds[state["pax"][vsel]["seat"]] = "selected"
            else:
                vs = [state["pax"][v]["seat"] for v in victims]
                clickable = set(vs)
                kinds = {s: "pick" for s in vs}

            def on_click(sid):
                v = sel.get("victim")
                if v in victims and sid in ms.kicker_destinations(state, v):
                    ms.play_card(state, pid=v, seat=sid)
                    commit(state)
                elif sid in state["occ"]:
                    sel["victim"] = state["occ"][sid]
                st.rerun()

    # ── Layout ───────────────────────────────────────────────────────────────
    map_col, side_col = st.columns([3, 2], gap="large")

    with side_col:
        _turn_banner(state, me)
        sc = _scoreboard(state, me)
        # A fresh container key per decision makes Streamlit replace the whole block,
        # so leftovers from the previous step don't linger while the bot is moving.
        with st.container(key="ms_ctl_%s" % _ctx(state).replace("-", "_")):
            _render_controls(state, me, commit, sel, pax_pick, my_move, opp_waiting_note)
        _feed(state, me)
        _secrets_box(state, me)
        with st.expander("Score breakdown", expanded=state["over"]):
            _breakdown(state, me, sc)
        with st.expander("Full flight log", expanded=False):
            for line in reversed(state["log"][-40:]):
                st.markdown("- " + line)

    with map_col:
        _mobile_strip(state, me, my_move)
        _render_map(state, me, clickable, kinds, on_click)


def _mobile_strip(state, me, my_move):
    """Phones stack the columns (map first) — keep the card + score visible above the map."""
    sc = ms.compute_scores(state)
    score = "You %d · %s %d" % (sc[me]["total"], state["players"][1 - me]["name"], sc[1 - me]["total"])
    if state["over"]:
        txt, cls = "Game over — %s" % score, "wait"
    elif not my_move:
        txt, cls = "⏳ %s's move · %s" % (state["players"][state["actor"]]["name"], score), "wait"
    elif state["card"]:
        c = ms.CARDS[state["card"]]
        txt, cls = "%s <b>%s</b> · %s" % (c["emoji"], c["name"], score), c["kind"]
    else:
        txt, cls = "Your move · %s" % score, "wait"
    st.markdown("<div class='ms-mobile-only'><div class='ms-strip %s'>%s<br>"
                "<small>Controls are below the map ↓</small></div></div>" % (cls, txt),
                unsafe_allow_html=True)


def _render_controls(state, me, commit, sel, pax_pick, my_move, opp_waiting_note):
    phase = state["phase"]
    opp = 1 - me
    if state["over"]:
        _render_game_over(state, me)
        return

    if not my_move:
        _card_table(state, me, state["card"], state["turn"],
                    empty_note="%s is reaching for the deck…" % state["players"][state["actor"]]["name"])
        if phase == "quiz":
            st.warning("👨‍✈️ %s's secret Pilot is at the controls…" % state["players"][state["actor"]]["name"])
        if opp_waiting_note:
            opp_waiting_note()
        return

    card = state["card"]
    if phase == "start":
        h = state["held"][me]
        _card_table(state, me, h, me, empty_note="")
        c1, c2 = st.columns(2)
        if c1.button("▶ Play it now", type="primary", use_container_width=True, key="ms_play_held"):
            ms.play_held(state)
            commit(state)
            st.rerun()
        if c2.button("🃏 Just draw", use_container_width=True, key="ms_just_draw"):
            ms.draw(state)
            commit(state)
            st.rerun()
        return

    if phase == "quiz":
        _render_quiz(state, me, commit)
        return

    if phase != "quiz":
        _card_table(state, me, card, me)

    if phase in ("place", "family"):
        if phase == "place" and state["overbooked"][me]:
            st.error("📛 Overbooked — this passenger has to take a middle seat.")
        if phase == "family":
            st.markdown("**Seat:** %s  \n<small>%d more after this</small>" % (
                ms.plabel(state, pax_pick, reveal_for=me), len(state["queue"]) - 1),
                unsafe_allow_html=True)
        else:
            _render_gate(state, me, sel, pax_pick)
        seats, forced = ms.legal_seats(state, pax_pick)
        if forced and not state["overbooked"][me] and phase == "place":
            st.warning("No open seats match this card — you're stuck with a middle seat.")
            if state["mode"] == "blitz":
                st.error("⚡ Blitz: sitting in a middle seat ends the game. Ouch.")
        st.caption(PHASE_HINT[phase])
        return

    if phase == "block":
        st.markdown("💪 **Armrest Hog** — tap a seat next to him to block it.")
        if st.button("Let it be (don't block)", key="ms_noblock"):
            ms.block_seat(state, None)
            commit(state)
            st.rerun()
        return

    if phase == "action":
        playable = ms.card_playable(state, card)
        if not playable:
            st.caption("Can't be played right now.")
        if card in ("GROUP1", "OVERBOOKED", "ARREST") and playable:
            if st.button("▶ Play %s" % ms.CARDS[card]["name"], type="primary",
                         use_container_width=True, key="ms_play"):
                ms.play_card(state)
                commit(state)
                st.rerun()
        elif card == "SWITCH" and playable:
            st.caption("Tap the first passenger, then who they'll switch with (purple).")
        elif card == "FORGOT" and playable:
            st.caption("Tap one of %s's passengers (purple) to send back to the gate."
                       % state["players"][opp]["name"])
        elif card == "WORK" and playable:
            st.caption("Tap your flight attendant to send them to the galley.")
        elif card == "KICKER" and playable:
            st.caption("Tap the passenger in front of your kid, then a middle seat to move them to."
                       if not sel.get("victim") else "Now tap the middle seat they get moved to.")
        elif card == "UPGRADE" and playable:
            cands = ms.upgrade_candidates(state)
            gate_cands = [pid for pid in cands if state["pax"][pid]["status"] == "gate"]
            st.caption("Tap a seated passenger (purple) — or upgrade someone straight from the gate:")
            if gate_cands:
                lbl = {pid: ms.plabel(state, pid, reveal_for=me) for pid in gate_cands}
                seen, opts = set(), []
                for pid in gate_cands:
                    if lbl[pid] not in seen:
                        seen.add(lbl[pid])
                        opts.append(pid)
                g = st.selectbox("From the gate", opts, format_func=lambda p: lbl[p], key="ms_up_gate")
                if st.button("🥂 Upgrade", key="ms_up_go", type="primary"):
                    ms.play_card(state, pid=g)
                    commit(state)
                    st.rerun()
        elif card == "REBOOKED" and playable:
            cands = ms.rebook_candidates(state)
            lbl = {pid: ms.plabel(state, pid, reveal_for=me) for pid in cands}
            g = st.selectbox("Who takes a later flight?", cands, format_func=lambda p: lbl[p], key="ms_rebook")
            if st.button("📅 Rebook", key="ms_rebook_go", type="primary"):
                ms.play_card(state, pid=g)
                commit(state)
                st.rerun()
        elif card == "FAMILY" and playable:
            groups = ms.family_candidates(state)
            g = st.selectbox("Which group?", groups,
                             format_func=lambda gid: "%s (%d)" % (
                                 ms._members(state, gid)[0]["glabel"], len(ms._members(state, gid))),
                             key="ms_fam")
            if st.button("👨‍👩‍👧 Board them", key="ms_fam_go", type="primary"):
                ms.play_card(state, group=g)
                commit(state)
                st.rerun()
        c1, c2 = st.columns(2)
        if ms.can_hold(state):
            if c1.button("✋ Hold for later", use_container_width=True, key="ms_hold"):
                ms.hold_card(state)
                commit(state)
                st.rerun()
        if c2.button("🗑 Discard", use_container_width=True, key="ms_discard"):
            ms.discard_card(state)
            commit(state)
            st.rerun()


def _render_quiz(state, me, commit):
    qz = state["quiz"]
    q = ms.QUIZ[qz["q"]]
    st.markdown(_card_html("PILOT"), unsafe_allow_html=True)
    need = len(qz.get("qs", [qz["q"]]))
    st.markdown("### 👨‍✈️ Your secret Pilot takes the controls!")
    if qz["first"]:
        st.markdown("From **First Class** — answer **%d** checkride questions to land it and **win**. "
                    "(Question %d of %d)" % (need, qz.get("i", 0) + 1, need))
    else:
        st.markdown("Answer correctly to land it for **+8**. Miss it and you go around for +2.")
    last = state.get("last_quiz")
    if last and last.get("correct") and last.get("pid") == qz["pid"] and qz.get("i", 0) > 0:
        st.success("✅ Correct! %s" % ms.QUIZ[last["q"]]["why"])
    st.markdown("**%s**" % q["q"])
    for i, opt in enumerate(q["options"]):
        if st.button(opt, key="ms_quiz_%d_%d" % (qz["q"], i), use_container_width=True):
            ms.answer_quiz(state, i)
            commit(state)
            st.rerun()


def _render_game_over(state, me):
    w = state["winner"]
    sc = ms.compute_scores(state, final=True)
    if w == "tie":
        cls, msg = "tie", "🤝 It's a tie, %d–%d." % (sc[0]["total"], sc[1]["total"])
    elif w == me:
        cls, msg = "win", "🏆 You win! %d–%d" % (sc[me]["total"], sc[1 - me]["total"])
    else:
        cls, msg = "loss", "😬 %s wins, %d–%d." % (state["players"][w]["name"], sc[w]["total"], sc[1 - w]["total"])
    st.markdown("<div class='ms-banner %s'>%s<br><small style='font-weight:500'>%s</small></div>"
                % (cls, msg, state["end_reason"]), unsafe_allow_html=True)
    lq = state.get("last_quiz")
    if lq:
        q = ms.QUIZ[lq["q"]]
        st.caption("👨‍✈️ Cockpit question: %s — %s %s" % (
            q["q"], "✅" if lq.get("correct") else "❌", q["why"]))


# ══════════════════════════════════════════════════════════════════════════════
# Local (bot) games
# ══════════════════════════════════════════════════════════════════════════════

_TOAST_MARKS = ("🩺", "👨‍✈️", "🚔", "🎒", "📛", "🦶", "🔄", "🥂", "🚨", "⏩")


def _pace():
    return BOT_SPEEDS.get(st.session_state.get("ms_pace") or "Normal", 1.0)


def _is_bot_turn(state):
    return (not state["over"]) and state["players"][state["actor"]]["kind"] == "bot"


def _local_commit(state):
    """Save the local game. The bot then moves one step per tick (see _local_game)."""
    st.session_state.ms_local = state
    st.session_state.ms_next_tick = time.time() + _pace()


def _local_game():
    """
    The board lives in a fragment. While it's the bot's turn the fragment re-runs on a
    timer and the bot makes ONE decision per tick (draw → show card → seat passenger),
    so you can watch each move land instead of everything happening at once.
    """
    state = st.session_state.ms_local
    pace = _pace()

    @st.fragment(run_every=pace if _is_bot_turn(state) else None)
    def _board():
        s = st.session_state.ms_local
        if _is_bot_turn(s) and time.time() >= st.session_state.get("ms_next_tick", 0):
            n0 = s.get("log_n", 0)
            ms.bot_step(s)
            new = s.get("log_n", 0) - n0
            for line in (s["log"][-new:] if new > 0 else []):
                if any(m in line for m in _TOAST_MARKS):
                    st.toast(line)
            st.session_state.ms_next_tick = time.time() + pace * 0.9
            if not _is_bot_turn(s):
                st.rerun(scope="app")      # your turn — stop the timer
        _render_game(s, 0, _local_commit)
    _board()
    if state["over"] and not state.get("_recorded") and not st.session_state.get("ms_guest_mode"):
        state["_recorded"] = True
        try:
            from rho.modules.ms_games import record_bot_result
            sc = ms.compute_scores(state, final=True)
            w = state["winner"]
            res = "tie" if w == "tie" else ("win" if w == 0 else "loss")
            record_bot_result(state["plane"], state["mode"], sc[0]["total"], sc[1]["total"],
                              res, state["end_reason"])
        except Exception:
            pass


def _start_local(plane, mode, my_name):
    state = ms.new_game(plane, mode, [{"name": my_name, "kind": "human", "uid": None}, dict(_BOT)])
    st.session_state.ms_local = state
    st.session_state.ms_view = "local"


# ══════════════════════════════════════════════════════════════════════════════
# Online games
# ══════════════════════════════════════════════════════════════════════════════

def _online_me(row):
    from rho.modules.auth import get_user_id
    uid = get_user_id()
    return 0 if row["player1"] == uid else 1


def _render_online():
    from rho.modules import ms_games
    gid = st.session_state.get("ms_game_id")
    row = ms_games.load_game(gid) if gid else None
    if not row:
        st.error("Couldn't load that game.")
        st.session_state.ms_view = "lobby"
        return
    state = row["state"]
    me = _online_me(row)

    _top_bar(state, back=True)

    if row["status"] == "open":
        base = os.environ.get("RHO_BASE_URL", "http://localhost:8501").rstrip("/")
        st.markdown("### 🎟️ Challenge created")
        st.markdown("Send this code (or link) to another Rho pilot. The game starts when they accept.")
        st.code(row["code"], language=None)
        st.code("%s/?ms=%s" % (base, row["code"]), language=None)
        _poll(gid, row["rev"])
        if st.button("Cancel challenge", key="ms_cancel"):
            ms_games.delete_game(gid)
            st.session_state.ms_view = "lobby"
            st.rerun()
        return

    def commit(s):
        new = ms_games.save_game(row, s)
        if new is None:
            st.toast("Your opponent moved at the same time — reloading.", icon="🔄")

    def waiting_note():
        st.caption("This updates automatically. You can leave — the game waits for you.")
        _poll(gid, row["rev"])

    _render_game(state, me, commit, opp_waiting_note=waiting_note)


def _poll(gid, rev):
    """Re-run the page when the game's rev changes (opponent moved / joined)."""
    from rho.modules import ms_games

    @st.fragment(run_every=4)
    def _watch():
        cur = ms_games.get_rev(gid)
        if cur and cur["rev"] != rev:
            st.rerun(scope="app")
    _watch()


# ══════════════════════════════════════════════════════════════════════════════
# Lobby
# ══════════════════════════════════════════════════════════════════════════════

def _top_bar(state, back=True):
    p = ms.PLANES[state["plane"]]
    c1, c2 = st.columns([4, 1])
    c1.markdown("**🪑 Middle Seat** · %s *%s* · %s" % (
        p["name"], p["nickname"], ms.MODES[state["mode"]]["name"]))
    if back and c2.button("← Lobby", key="ms_back", use_container_width=True):
        st.session_state.ms_view = "lobby"
        st.rerun()


def _rules():
    st.markdown("""
**Goal:** board all your passengers and score the most points. You and your opponent board the **same roster**.

**Each turn** you draw a card. **Seat cards** say where your next passenger may sit — the map lights up the legal
seats. If none are left, you're stuck with a **middle seat**. **Action cards** can be played, discarded or
**held** (one at a time). **Events** happen the moment they're drawn.

**Scoring**
| | |
|---|---|
| Every seated passenger | +1 (flight attendants +2) |
| Couple side by side / across the aisle | +2 |
| Best Friends all in one row | +3 |
| Family (every kid next to a parent, parents within 1 row) | +3 / +5 / +6 |
| First Class (upgrade only) | +2 each, locked |
| Middle seat | −2 (787 center middle −3) — unless sandwiched by their own group |
| Left at the gate when the doors close | −2 each |

**Annoying passengers:** 😴 Recliner (−1 to whoever's behind) · 🗣️ Chatty Cathy (+2 next to an opponent, they get −1) ·
💪 Armrest Hog (blocks a seat) · 😰 Nervous Flyer (+3 next to any flight attendant) · 🛩️ AvGeek (+3 window over the wing) ·
🦹 The Fugitive (+4 if never caught) · 👮 Air Marshal (arrest the other Fugitive within 1 row: +4).

**Locked is locked:** First Class passengers and finished groups can't be moved by any card.

**Secrets:** one of your ordinary passengers is secretly a 🩺 **Doctor** (closest one to a medical emergency: +5),
another is an off-duty 👨‍✈️ **Pilot**. If the captain is incapacitated, the Pilot closest to the cockpit takes over:
from **First Class**, answer two checkride questions and you **win on the spot**.

**Blitz mode:** the first player with a passenger in a middle seat — for any reason — loses.
""")
    with st.expander("All the cards"):
        counts = dict(ms.DECK_COUNTS)
        for k, c in ms.CARDS.items():
            n = counts.get(k, 3 if k == "CENTER" else 0)
            st.markdown("%s **%s** ×%s — %s" % (c["emoji"], c["name"], n if k != "CENTER" else "3 (787 only)", c["text"]))


def _render_lobby(guest):
    st.markdown(_BASE_CSS, unsafe_allow_html=True)
    st.markdown("<div class='ms-hero'><h2>🪑 Middle Seat</h2>"
                "<p>The boarding game. Seat your passengers, sabotage theirs — "
                "and whatever you do, don't get stuck in the middle.</p></div>",
                unsafe_allow_html=True)

    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown("#### New game")
        plane = st.radio("Plane", list(ms.PLANES),
                         format_func=lambda k: "%s — %s" % (ms.PLANES[k]["name"], ms.PLANES[k]["nickname"]),
                         captions=[ms.PLANES[k]["blurb"] for k in ms.PLANES],
                         index=1, key="ms_plane")
        mode = st.radio("Mode", list(ms.MODES), format_func=lambda k: ms.MODES[k]["name"],
                        captions=[ms.MODES[k]["blurb"] for k in ms.MODES],
                        horizontal=True, key="ms_mode")
        opp_opts = ["bot"] if guest else ["bot", "pilot"]
        opp = st.radio("Opponent", opp_opts,
                       format_func=lambda k: "🤖 Rho (bot)" if k == "bot" else "🧑‍✈️ Challenge another Rho pilot",
                       horizontal=True, key="ms_opp")
        st.session_state.ms_pace = st.select_slider(
            "Rho's pace", list(BOT_SPEEDS), value=st.session_state.get("ms_pace") or "Normal",
            help="How long Rho pauses between moves so you can follow along.")
        my_name = "Guest" if guest else (st.session_state.get("user_name") or "Pilot")
        if st.button("✈ Start boarding", type="primary", key="ms_start"):
            if opp == "bot":
                _start_local(plane, mode, my_name)
            else:
                from rho.modules import ms_games
                state = ms.new_game(plane, mode, [
                    {"name": my_name, "kind": "human", "uid": None},
                    {"name": "Waiting…", "kind": "human", "uid": None}])
                try:
                    row = ms_games.create_challenge(state, my_name)
                    st.session_state.ms_game_id = row["id"]
                    st.session_state.ms_view = "online"
                except Exception as e:
                    st.error("Couldn't create the challenge: %s" % e)
                    return
            st.rerun()
        if guest:
            st.info("Playing as a guest — nothing is saved. **Create a free Rho account** to "
                    "challenge other pilots and keep your record.")
        with st.expander("📖 How to play", expanded=guest):
            _rules()

    with right:
        if st.session_state.get("ms_local") and not st.session_state.ms_local.get("over"):
            if st.button("▶ Resume your game vs Rho", use_container_width=True, key="ms_resume"):
                st.session_state.ms_view = "local"
                st.rerun()
        if guest:
            return
        from rho.modules import ms_games
        st.markdown("#### Join a challenge")
        jc1, jc2 = st.columns([2, 1])
        code = jc1.text_input("Code", key="ms_join_code", label_visibility="collapsed",
                              placeholder="6-letter code")
        if jc2.button("Join", use_container_width=True, key="ms_join"):
            _join(code)
        try:
            games = ms_games.list_my_games()
            rec = ms_games.my_record()
        except Exception as e:
            st.caption("Online games need the Middle Seat database tables (migration 002). %s" % e)
            return
        b, pl = rec["bot"], rec["pilots"]
        st.markdown("#### Your record")
        st.markdown("vs 🤖 Rho: **%d–%d**%s &nbsp;·&nbsp; vs pilots: **%d–%d**%s" % (
            b["win"], b["loss"], (" (%d ties)" % b["tie"]) if b["tie"] else "",
            pl["win"], pl["loss"], (" (%d ties)" % pl["tie"]) if pl["tie"] else ""))
        st.markdown("#### Your games")
        from rho.modules.auth import get_user_id
        uid = get_user_id()
        if not games:
            st.caption("No games yet — challenge someone!")
        for g in games:
            mine1 = g["player1"] == uid
            opp_name = (g.get("player2_name") if mine1 else g.get("player1_name")) or "—"
            if g["status"] == "open":
                badge = "🎟️ waiting for opponent · code **%s**" % g["code"]
            elif g["status"] == "finished":
                w = g["winner"]
                won = (w == "p1" and mine1) or (w == "p2" and not mine1)
                badge = "🤝 tie" if w == "tie" else ("🏆 won" if won else "lost")
            else:
                badge = "🟢 **your move**" if g.get("turn_uid") == uid else "⏳ their move"
            c1, c2 = st.columns([3, 1])
            c1.markdown("vs **%s** · %s  \n<small>%s · %s</small>" % (
                opp_name, badge, ms.PLANES.get(g["plane"], {}).get("name", g["plane"]),
                ms.MODES.get(g["mode"], {}).get("name", g["mode"])), unsafe_allow_html=True)
            if c2.button("Open", key="ms_open_%s" % g["id"], use_container_width=True):
                st.session_state.ms_game_id = g["id"]
                st.session_state.ms_view = "online"
                st.rerun()


def _join(code):
    from rho.modules import ms_games
    name = st.session_state.get("user_name") or "Pilot"
    try:
        row, err = ms_games.join_challenge(code, name)
    except Exception as e:
        row, err = None, str(e)
    if err:
        st.error(err)
        return
    st.session_state.ms_game_id = row["id"]
    st.session_state.ms_view = "online"
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

def page_middle_seat(guest=False):
    st.session_state.ms_guest_mode = guest
    _ss("ms_view", "lobby")

    # Challenge link: ?ms=CODE
    code = st.query_params.get("ms") or st.session_state.get("pending_ms")
    if code and not guest:
        st.session_state.pending_ms = None
        try:
            del st.query_params["ms"]
        except Exception:
            pass
        _join(code)

    view = st.session_state.ms_view
    if view == "local" and st.session_state.get("ms_local"):
        state = st.session_state.ms_local
        _top_bar(state)
        _local_game()
        if state["over"]:
            c1, c2, _ = st.columns([1, 1, 2])
            if c1.button("🔁 Rematch", type="primary", key="ms_rematch", use_container_width=True):
                _start_local(state["plane"], state["mode"], state["players"][0]["name"])
                st.rerun()
            if guest:
                st.success("Fun? **Create a free Rho account** to challenge your friends and keep score.")
    elif view == "online" and not guest:
        _render_online()
    else:
        st.session_state.ms_view = "lobby"
        _render_lobby(guest)
