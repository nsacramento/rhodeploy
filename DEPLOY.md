# Rho — Deploy Checklist

## One-time Supabase setup (new tables)
Run `supabase_setup.sql` in the Supabase Dashboard → SQL editor.
Creates: `profiles`, `instructor_students`, `instructor_invites`, `instructor_skill_ratings`
and adds instructor-read policies to `flights` and `skill_log`.

## Migration 001 (aircraft, tail number, brief timestamps)
Run `supabase_migration_001.sql` in the Supabase Dashboard → SQL editor **after** the setup script.
- Adds `aircraft_type`, `tail_number` columns to `profiles` and `flights`
- Adds `brief_at` (TIMESTAMPTZ) to `flights`
- Adds RLS policy so students can read their own instructor ratings

## Install Python dependencies
```bash
pip3 install contextily --break-system-packages
```
(matplotlib and shapely should already be present from earlier sessions)

## Environment variables
| Variable | Purpose | Default |
|---|---|---|
| `RHO_BASE_URL` | Base URL for invite links | `http://localhost:8501` |
| `SUPABASE_URL` | Supabase project URL | — (required) |
| `SUPABASE_KEY` | Supabase anon key | — (required) |

Set `RHO_BASE_URL` to your public URL in production (e.g. `https://rho.yourdomain.com`).

## Run locally
```bash
cd /Users/nic/Documents/Claude/Projects/Co-Pilot
streamlit run app.py
```

---

## Sprint history

### Tasks 45–50 (latest sprint)
- `app.py` — Home/Dashboard page, aircraft type + tail in briefs, historical brief viewer,
  winds-aloft expander, timestamps, delete confirmation, profile prompt banner,
  instructor ratings + discrepancy view for students, invite URL from env var
- `profile.py` — aircraft_type + tail_number save/load
- `flights.py` — aircraft_type, tail_number, brief_at on create_flight()
- `cheatsheet.py` — V-speeds strip before emergency section
- `kneeboard.py` — V-speeds reference section before pre-departure checklist
- `aircraft.py` — 9 preset aircraft with full POH data (NEW)
- `weather.py` — winds-aloft fetch + decode
- `insights.py` — winds_aloft key in brief dict
- `supabase_migration_001.sql` — columns + student RLS policy (NEW)

### Earlier sprints
- `acs.py` — pilot-friendly skill names (IDs unchanged)
- `profile.py` — NEW: user profile CRUD
- `instructor.py` — NEW: invite + rating logic
- `map_utils.py` — NEW: shared route map (contextily tiles)
- `cheatsheet.py` — replaced private map fn with map_utils
- `kneeboard.py` — replaced private map fn with map_utils
- `app.py` — profile/instructor pages, nav update, map_utils wiring
- `weather.py` — altimeter hPa → inHg fix
- `routing.py` — altitude filtering + route ordering
- `insights.py` — airspace radius + cruise_alt pass-through
