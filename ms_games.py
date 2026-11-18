"""
Rho — Middle Seat: Supabase persistence

  middle_seat_games    async player-vs-player games, joined by a 6-char code
  middle_seat_results  results of games vs the Rho bot

See supabase_migration_002_middle_seat.sql. All calls go through the shared
client (rho.modules.db) so RLS sees the signed-in user.
"""

import random
import string
from datetime import datetime, timezone

from rho.modules.db import get_client

_CODE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O/1/I


def _uid():
    return get_client().auth.get_user().user.id


def _now():
    return datetime.now(timezone.utc).isoformat()


def _new_code():
    return "".join(random.choice(_CODE_CHARS) for _ in range(6))


# ── Player-vs-player ─────────────────────────────────────────────────────────

def create_challenge(state, my_name):
    """Insert an open game. `state` already has players[0] = me. Returns the row."""
    sb = get_client()
    uid = _uid()
    state["players"][0]["uid"] = uid
    last_err = None
    for _ in range(5):
        code = _new_code()
        try:
            row = sb.table("middle_seat_games").insert({
                "code": code,
                "player1": uid,
                "player1_name": my_name,
                "plane": state["plane"],
                "mode": state["mode"],
                "status": "open",
                "turn_uid": uid,
                "state": state,
            }).execute().data
            return row[0] if row else None
        except Exception as e:  # code collision — try another
            last_err = e
    raise last_err


def find_open_game(code):
    code = (code or "").strip().upper()
    rows = (get_client().table("middle_seat_games").select("*")
            .eq("code", code).execute().data or [])
    return rows[0] if rows else None


def join_challenge(code, my_name):
    """
    Claim player 2 in an open game.
    Returns (row, None) or (None, error message).
    """
    sb = get_client()
    uid = _uid()
    row = find_open_game(code)
    if not row:
        return None, "No game found with that code."
    if row["player1"] == uid or row.get("player2") == uid:
        return row, None   # already in it
    if row["status"] != "open" or row.get("player2"):
        return None, "That game already has two players."
    state = row["state"]
    state["players"][1]["name"] = my_name
    state["players"][1]["uid"] = uid
    state["log"].append("🧳 %s accepted the challenge. Boarding begins!" % my_name)
    res = (sb.table("middle_seat_games").update({
        "player2": uid,
        "player2_name": my_name,
        "status": "active",
        "state": state,
        "rev": row["rev"] + 1,
        "updated_at": _now(),
    }).eq("id", row["id"]).eq("rev", row["rev"]).execute().data or [])
    if not res:
        return None, "Someone else just joined that game."
    return res[0], None


def list_my_games(limit=20):
    uid = _uid()
    rows = (get_client().table("middle_seat_games")
            .select("id,code,player1,player1_name,player2,player2_name,plane,mode,status,"
                    "turn_uid,winner,updated_at,rev")
            .or_("player1.eq.%s,player2.eq.%s" % (uid, uid))
            .order("updated_at", desc=True).limit(limit).execute().data or [])
    return rows


def load_game(game_id):
    rows = (get_client().table("middle_seat_games").select("*")
            .eq("id", game_id).execute().data or [])
    return rows[0] if rows else None


def get_rev(game_id):
    rows = (get_client().table("middle_seat_games").select("rev,status")
            .eq("id", game_id).execute().data or [])
    return rows[0] if rows else None


def save_game(row, state):
    """
    Save a state for `row` (the dict we loaded). Uses `rev` as an optimistic lock.
    Returns the updated row, or None if someone else saved first.
    """
    p = state["players"]
    if state["over"]:
        status = "finished"
        w = state["winner"]
        winner = "tie" if w == "tie" else ("p1" if w == 0 else "p2")
        turn_uid = None
    else:
        status = "active" if row.get("player2") else "open"
        winner = None
        turn_uid = p[state["actor"]].get("uid")
    res = (get_client().table("middle_seat_games").update({
        "state": state,
        "status": status,
        "winner": winner,
        "turn_uid": turn_uid,
        "rev": row["rev"] + 1,
        "updated_at": _now(),
    }).eq("id", row["id"]).eq("rev", row["rev"]).execute().data or [])
    return res[0] if res else None


def delete_game(game_id):
    get_client().table("middle_seat_games").delete().eq("id", game_id).execute()


# ── Bot results / record ─────────────────────────────────────────────────────

def record_bot_result(plane, mode, my_score, opp_score, result, end_reason=None):
    get_client().table("middle_seat_results").insert({
        "opponent": "bot", "plane": plane, "mode": mode,
        "my_score": my_score, "opp_score": opp_score,
        "result": result, "end_reason": (end_reason or "")[:200],
    }).execute()


def my_record():
    """{'bot': {'win': n, 'loss': n, 'tie': n}, 'pilots': {...}}"""
    uid = _uid()
    out = {"bot": {"win": 0, "loss": 0, "tie": 0}, "pilots": {"win": 0, "loss": 0, "tie": 0}}
    try:
        rows = (get_client().table("middle_seat_results").select("result")
                .eq("user_id", uid).execute().data or [])
        for r in rows:
            if r["result"] in out["bot"]:
                out["bot"][r["result"]] += 1
    except Exception:
        pass
    try:
        games = (get_client().table("middle_seat_games").select("player1,player2,winner")
                 .eq("status", "finished")
                 .or_("player1.eq.%s,player2.eq.%s" % (uid, uid)).execute().data or [])
        for g in games:
            mine = "p1" if g["player1"] == uid else "p2"
            if g["winner"] == "tie":
                out["pilots"]["tie"] += 1
            elif g["winner"] == mine:
                out["pilots"]["win"] += 1
            else:
                out["pilots"]["loss"] += 1
    except Exception:
        pass
    return out
