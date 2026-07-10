"""
Rho — Checkride readiness report + lesson planner PDFs.

generate_readiness_report(latest_per_task, stats, flight_rules="VFR")
    → Checkride-readiness breakdown by ACS area, printable for CFI review.

generate_lesson_plan(plan, latest_per_task, n_lessons=3, flight_rules="VFR")
    → 3-lesson plan targeting the pilot's highest-priority skill gaps.

IFR note: flight_rules param reserved — all ACS areas apply to VFR checkride.
"""

import io
from datetime import date as _date

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    KeepTogether, HRFlowable,
)

from rho.modules.acs import ACS_TASKS, RATING_LABELS

# ── Palette ───────────────────────────────────────────────────────────────────
_NAVY   = colors.HexColor("#1e293b")
_GREEN  = colors.HexColor("#15803d")
_YELLOW = colors.HexColor("#b45309")
_RED    = colors.HexColor("#991b1b")
_SLATE  = colors.HexColor("#475569")
_LIGHT  = colors.HexColor("#f1f5f9")
_BORDER = colors.HexColor("#cbd5e1")
_WHITE  = colors.white

_S = getSampleStyleSheet()


def _style(name, **kw):
    base = kw.pop("parent", _S["Normal"])
    return ParagraphStyle(name, parent=base, **kw)


_TITLE = _style("RPT",  fontSize=13, fontName="Helvetica-Bold",
                textColor=_WHITE,  alignment=TA_CENTER)
_SUB   = _style("RPSB", fontSize=8,  fontName="Helvetica",
                textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER)
_SEC   = _style("RPSC", fontSize=9,  fontName="Helvetica-Bold",
                textColor=_WHITE,  alignment=TA_LEFT)
_KEY   = _style("RPK",  fontSize=7,  fontName="Helvetica-Bold",
                textColor=_SLATE)
_VAL   = _style("RPV",  fontSize=8,  fontName="Helvetica",
                textColor=_NAVY,   leading=10)
_CELL  = _style("RPC",  fontSize=7,  fontName="Helvetica",
                textColor=_NAVY)
_WARN  = _style("RPW",  fontSize=7,  fontName="Helvetica-Bold",
                textColor=_RED)
_NOTE  = _style("RPN",  fontSize=6,  fontName="Helvetica",
                textColor=_SLATE,  alignment=TA_CENTER)


def _banner(text, bg=_NAVY, style=None):
    s = style or _SEC
    tbl = Table([[Paragraph(text, s)]], colWidths=["100%"])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), bg),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    return tbl


def _rating_color(rating):
    return {3: _GREEN, 2: _YELLOW, 1: _RED}.get(rating, _SLATE)


# Literal hex strings for inline ReportLab <font color="..."> tags.
# Do NOT use Color.hexval() — it returns '0xRRGGBBFF' format, not '#RRGGBB'.
_RATING_HEX = {3: "#15803d", 2: "#b45309", 1: "#991b1b"}

def _rating_hex(rating):
    return _RATING_HEX.get(rating, "#475569")


def _rating_label(rating):
    return {3: "Met Standard", 2: "Needs Work", 1: "Below Std", None: "Not Practiced"}.get(rating, "—")


# ── Readiness Report ──────────────────────────────────────────────────────────

def generate_readiness_report(latest_per_task, stats, pilot_name=None,
                              flight_rules="VFR"):
    """
    Generate a checkride readiness report PDF.

    Parameters
    ----------
    latest_per_task : dict {task_id: rating} from get_flight_skill_matrix
    stats           : dict from get_readiness_summary
    pilot_name      : str or None
    flight_rules    : "VFR" | "IFR"

    Returns
    -------
    bytes — PDF
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.45*inch, bottomMargin=0.45*inch,
    )
    W = letter[0] - 1.0*inch

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    pilot_str = f"  |  Pilot: {pilot_name}" if pilot_name else ""
    hdr = Table([[
        Paragraph("CHECKRIDE READINESS REPORT", _TITLE),
        Paragraph(f"Private Pilot ACS  |  {_date.today()}{pilot_str}", _SUB),
    ]], colWidths=[W * 0.55, W * 0.45])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 6))

    # ── Overall score summary ─────────────────────────────────────────────────
    pct    = stats["pct"]
    green  = stats["green"]
    yellow = stats["yellow"]
    red    = stats["red"]
    blank  = stats["blank"]
    total  = stats["total"]

    score_clr = _GREEN if pct >= 80 else (_YELLOW if pct >= 50 else _RED)
    score_data = [[
        Paragraph(f"<b>{pct}%</b>", _style("SCR", fontSize=22,
                  fontName="Helvetica-Bold", textColor=score_clr,
                  alignment=TA_CENTER)),
        Paragraph(
            f"<b>Checkride Readiness — {pct}%</b><br/>"
            f"<font color='#15803d'>&#9632; {green} at standard</font>  "
            f"<font color='#b45309'>&#9632; {yellow} needs work</font>  "
            f"<font color='#991b1b'>&#9632; {red} below standard</font>  "
            f"<font color='#6b7280'>&#9632; {blank} not yet practiced</font>  "
            f"of {total} total ACS tasks",
            _style("SCS", fontSize=8, fontName="Helvetica",
                   textColor=_NAVY, leading=12),
        ),
    ]]
    score_tbl = Table(score_data, colWidths=[0.8*inch, W - 0.8*inch])
    score_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW",     (0, 0), (-1, 0),  1.0, _BORDER),
    ]))
    story.append(score_tbl)
    story.append(Spacer(1, 10))

    # ── Per-area breakdown ────────────────────────────────────────────────────
    # Group tasks by area
    areas = {}
    for task_id, task in ACS_TASKS.items():
        area = task["area_name"]
        if area not in areas:
            areas[area] = []
        areas[area].append(task_id)

    for area_name, task_ids in areas.items():
        area_green  = sum(1 for tid in task_ids if latest_per_task.get(tid) == 3)
        area_total  = len(task_ids)
        area_pct    = round(100 * area_green / area_total)
        area_clr    = _GREEN if area_pct >= 80 else (_YELLOW if area_pct >= 40 else _RED)

        # Area banner with score
        banner_data = [[
            Paragraph(f"  {area_name}", _SEC),
            Paragraph(f"{area_green}/{area_total} at standard  ({area_pct}%)",
                      _style("ABS", fontSize=8, fontName="Helvetica-Bold",
                             textColor=_WHITE, alignment=TA_LEFT)),
        ]]
        banner_tbl = Table(banner_data, colWidths=[W * 0.72, W * 0.28])
        banner_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), area_clr),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))

        # Task rows for this area
        task_rows = [[
            Paragraph("<b>Task</b>", _KEY),
            Paragraph("<b>Skill</b>", _KEY),
            Paragraph("<b>Status</b>", _KEY),
            Paragraph("<b>CFI Notes</b>", _KEY),
        ]]
        for tid in task_ids:
            rating = latest_per_task.get(tid)
            r_lbl  = _rating_label(rating)
            task_rows.append([
                Paragraph(tid, _CELL),
                Paragraph(ACS_TASKS[tid]["name"], _CELL),
                Paragraph(f'<font color="{_rating_hex(rating)}">'
                          f'<b>{r_lbl}</b></font>', _CELL),
                Paragraph("_" * 30, _NOTE),
            ])

        area_tbl = Table(task_rows,
                         colWidths=[0.55*inch, 2.6*inch, 1.0*inch, W - 4.15*inch])
        area_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0),  (-1, 0),  colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_WHITE, _LIGHT]),
            ("GRID",          (0, 0),  (-1, -1), 0.3, _BORDER),
            ("TOPPADDING",    (0, 0),  (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0),  (-1, -1), 3),
            ("LEFTPADDING",   (0, 0),  (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0),  (-1, -1), 4),
            ("VALIGN",        (0, 0),  (-1, -1), "TOP"),
        ]))

        story.append(KeepTogether([
            banner_tbl,
            area_tbl,
            Spacer(1, 6),
        ]))

    # ── Signature block ───────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
    story.append(Spacer(1, 6))
    sig_data = [[
        Paragraph("Student Pilot:  ______________________________  Date: ________", _CELL),
        Paragraph("CFI:  ______________________________  Cert #: _______________  Date: ________", _CELL),
    ]]
    sig_tbl = Table(sig_data, colWidths=[W * 0.42, W * 0.58])
    sig_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 4),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
    ]))
    story.append(sig_tbl)

    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Generated by Rho — Student Pilot Co-Pilot (rhocopilot.com). "
        "Ratings are self-reported unless marked CFI. "
        "Verify all standards against current FAA Private Pilot ACS (PAR-ACS-9).",
        _NOTE,
    ))

    doc.build(story)
    return buf.getvalue()


# ── Lesson Planner ────────────────────────────────────────────────────────────

# Lesson clusters: which tasks naturally belong in the same lesson
_LESSON_CLUSTERS = [
    {
        "theme": "Takeoffs & Climbs",
        "tasks": ["IV-A", "IV-C", "IV-E", "IV-G"],
        "objectives": [
            "Perform normal, soft-field, and short-field takeoffs to ACS standards.",
            "Demonstrate proper crosswind technique throughout the takeoff roll.",
            "Establish Vx and Vy climb airspeeds accurately within +10/-5 kt.",
        ],
        "drill": "3-4 takeoffs per variation. Debrief between each: airspeed control, rudder use, obstacle clearance.",
    },
    {
        "theme": "Landings & Pattern Work",
        "tasks": ["IV-B", "IV-D", "IV-F", "IV-H", "IV-I"],
        "objectives": [
            "Achieve consistent touchdown within 200 ft of target for each landing type.",
            "Demonstrate stabilized approach at correct airspeed and configuration.",
            "Execute a go-around at any point CFI calls 'go around'.",
        ],
        "drill": "Fly the full pattern. Alternate: normal → soft-field → short-field → go-around. Forward slip on approach.",
    },
    {
        "theme": "Slow Flight, Stalls & Spin Awareness",
        "tasks": ["VII-A", "VII-B", "VII-C", "VII-D"],
        "objectives": [
            "Maintain coordinated slow flight at minimum controllable airspeed ±10 kt.",
            "Recognize and recover from power-off and power-on stalls before secondary stall.",
            "Articulate spin entry conditions, visual cues, and recovery procedure (PARE).",
        ],
        "drill": "Climb to safe altitude (3,000+ AGL). Slow flight 2 min. Power-off stall. Power-on stall. Verbal spin awareness. Unusual attitude recovery.",
    },
    {
        "theme": "Ground Reference & Steep Turns",
        "tasks": ["V-A", "V-B"],
        "objectives": [
            "Complete 360° steep turn at 45° bank, hold ±100 ft altitude and ±10 kt airspeed.",
            "Fly S-turns and turns around a point coordinating with wind to maintain constant ground track.",
        ],
        "drill": "Choose prominent ground feature. S-turns × 4 passes. Turns around point × 2 (each direction). Steep turns both directions.",
    },
    {
        "theme": "Navigation — Pilotage, Dead Reckoning & Diversion",
        "tasks": ["VI-A", "VI-B", "VI-C", "VI-D"],
        "objectives": [
            "Navigate a planned cross-country leg using pilotage and dead reckoning without GPS.",
            "Intercept and track a VOR radial; use GPS for situational awareness.",
            "Divert to an alternate airport in flight using sectional and time/distance calculation.",
        ],
        "drill": "Pre-plan 3-leg XC. Fly leg 1 pilotage only. Leg 2 use VOR. CFI calls divert mid-leg 3. Practice lost-comms / lost procedures.",
    },
    {
        "theme": "Emergencies",
        "tasks": ["IX-A", "IX-B", "IX-C", "IX-D"],
        "objectives": [
            "Execute simulated engine-out landing to a suitable field from any altitude.",
            "Identify and respond to simulated partial panel / equipment failure.",
            "State emergency equipment locations and survival priorities from memory.",
        ],
        "drill": "CFI pulls throttle unexpectedly. Pilot runs ABCDE checklist, picks field, flies pattern. Debrief glide ratio and field selection.",
    },
    {
        "theme": "Basic Instrument Flight (Hood)",
        "tasks": ["VIII-A", "VIII-B", "VIII-C", "VIII-D", "VIII-E"],
        "objectives": [
            "Maintain straight-and-level flight under hood within ±200 ft, ±20° heading.",
            "Recover from unusual attitudes on partial panel.",
            "Intercept and track radio nav aid under hood.",
        ],
        "drill": "Don hood. Straight-and-level 3 min. Standard-rate turns to assigned headings. Climbs and descents. CFI induces unusual attitude; pilot recovers.",
    },
    {
        "theme": "Preflight Knowledge & ADM",
        "tasks": ["I-A", "I-B", "I-C", "I-D", "I-E", "I-F", "I-G", "I-H"],
        "objectives": [
            "Pass oral questioning on ARROW documents, airspace rules, and weather interpretation.",
            "Demonstrate W&B and performance calculation for the specific aircraft.",
            "Apply ADM framework (DECIDE, PAVE) to a simulated go/no-go scenario.",
        ],
        "drill": "Oral session with CFI. Scenario: marginal weather XC. Student walks through PAVE, weather products, W&B, flight plan filing.",
    },
    {
        "theme": "Pre-Flight Procedures & Airport Ops",
        "tasks": ["II-A", "II-B", "II-C", "II-D", "II-E", "II-F",
                  "III-A", "III-B"],
        "objectives": [
            "Complete walk-around and cockpit setup checklist without prompting.",
            "Taxi correctly following airport signs and ATC instructions.",
            "Make proper radio calls at all stages of flight (ATIS, ground, tower, CTAF).",
        ],
        "drill": "CFI observes walk-around and grades each item. Taxi to runway: pilot leads all calls. Run-up: every item verbalized.",
    },
]


def generate_lesson_plan(plan, latest_per_task, n_lessons=3, pilot_name=None,
                         flight_rules="VFR"):
    """
    Generate a lesson plan PDF targeting the pilot's highest-priority skill gaps.

    Parameters
    ----------
    plan            : list from get_training_plan()
    latest_per_task : dict {task_id: rating}
    n_lessons       : number of lessons to generate (default 3)
    pilot_name      : str or None
    flight_rules    : "VFR" | "IFR"

    Returns
    -------
    bytes — PDF
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.5*inch, rightMargin=0.5*inch,
        topMargin=0.45*inch, bottomMargin=0.45*inch,
    )
    W = letter[0] - 1.0*inch

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    pilot_str = f"  |  Pilot: {pilot_name}" if pilot_name else ""
    hdr = Table([[
        Paragraph("LESSON PLAN", _TITLE),
        Paragraph(f"Next {n_lessons} Lessons  |  {_date.today()}{pilot_str}", _SUB),
    ]], colWidths=[W * 0.4, W * 0.6])
    hdr.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), _NAVY),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 6))

    # ── Identify which clusters are needed ────────────────────────────────────
    # Score each cluster by how many of its tasks are in the gap list (priority 1 or 2)
    gap_task_ids = {item["task_id"] for item in plan if item["priority"] <= 2}

    def _cluster_score(cluster):
        gap_hits  = sum(1 for tid in cluster["tasks"] if tid in gap_task_ids)
        red_hits  = sum(1 for tid in cluster["tasks"]
                        if latest_per_task.get(tid) == 1)
        blank_hits = sum(1 for tid in cluster["tasks"]
                         if latest_per_task.get(tid) is None)
        return (gap_hits * 3 + red_hits * 2 + blank_hits)

    scored = sorted(_LESSON_CLUSTERS, key=_cluster_score, reverse=True)
    lessons = scored[:n_lessons]

    if not lessons:
        story.append(Paragraph("No skill gaps found — all ACS tasks at standard!", _VAL))
        doc.build(story)
        return buf.getvalue()

    # ── Gap summary ───────────────────────────────────────────────────────────
    total_gaps    = len(plan)
    priority1     = sum(1 for item in plan if item["priority"] == 1)
    priority2     = sum(1 for item in plan if item["priority"] == 2)

    gap_style = _style("GPST", fontSize=8, fontName="Helvetica",
                       textColor=_NAVY, leading=12)
    story.append(Paragraph(
        f"<b>{total_gaps} tasks below ACS standard</b> — "
        f"{priority1} high priority (not practiced / below standard), "
        f"{priority2} medium priority (in progress). "
        "Lessons below target the highest-impact gaps.",
        gap_style,
    ))
    story.append(Spacer(1, 8))

    # ── Lessons ───────────────────────────────────────────────────────────────
    for lesson_num, cluster in enumerate(lessons, start=1):
        lesson_tasks = cluster["tasks"]

        # Which tasks in this lesson still have gaps
        gap_in_lesson = [
            tid for tid in lesson_tasks
            if latest_per_task.get(tid) != 3
        ]
        ready_in_lesson = [
            tid for tid in lesson_tasks
            if latest_per_task.get(tid) == 3
        ]

        lesson_clr = _RED if any(
            latest_per_task.get(tid) == 1 for tid in lesson_tasks
        ) else _YELLOW if gap_in_lesson else _GREEN

        story.append(KeepTogether([
            _banner(f"  Lesson {lesson_num}  —  {cluster['theme']}", bg=lesson_clr),
            Spacer(1, 4),
        ]))

        # Objectives
        obj_rows = [[
            Paragraph("<b>Objectives</b>", _KEY),
            Paragraph(
                "<br/>".join(f"• {o}" for o in cluster["objectives"]),
                _style("OBJ", fontSize=7, fontName="Helvetica",
                       textColor=_NAVY, leading=11)
            ),
        ]]
        obj_tbl = Table(obj_rows, colWidths=[0.85*inch, W - 0.85*inch])
        obj_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, -1), _LIGHT),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.3, _BORDER),
        ]))
        story.append(obj_tbl)

        # Drill sequence
        drill_rows = [[
            Paragraph("<b>Drill</b>", _KEY),
            Paragraph(cluster["drill"],
                      _style("DRL", fontSize=7, fontName="Helvetica",
                             textColor=_NAVY, leading=11)),
        ]]
        drill_tbl = Table(drill_rows, colWidths=[0.85*inch, W - 0.85*inch])
        drill_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, -1), _LIGHT),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
            ("LINEBELOW",     (0, 0), (-1, 0),  0.3, _BORDER),
        ]))
        story.append(drill_tbl)

        # Task status grid
        task_header = [
            Paragraph("<b>Task</b>", _KEY),
            Paragraph("<b>Skill</b>", _KEY),
            Paragraph("<b>Current</b>", _KEY),
            Paragraph("<b>Target</b>", _KEY),
            Paragraph("<b>CFI Sign-off</b>", _KEY),
        ]
        task_data = [task_header]
        for tid in lesson_tasks:
            rating = latest_per_task.get(tid)
            r_lbl  = _rating_label(rating)
            task_data.append([
                Paragraph(tid, _CELL),
                Paragraph(ACS_TASKS[tid]["name"], _CELL),
                Paragraph(f'<font color="{_rating_hex(rating)}">{r_lbl}</font>', _CELL),
                Paragraph("Met Standard", _CELL),
                Paragraph("______________", _NOTE),
            ])

        task_tbl = Table(task_data,
                         colWidths=[0.55*inch, 2.4*inch, 0.9*inch, 0.9*inch,
                                    W - 4.75*inch])
        task_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#e2e8f0")),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [_WHITE, _LIGHT]),
            ("GRID",          (0, 0), (-1, -1), 0.3, _BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(task_tbl)
        story.append(Spacer(1, 4))

        # Debrief box
        debrief_data = [[
            Paragraph("<b>Debrief notes</b>", _KEY),
            Paragraph("", _CELL),
        ]]
        debrief_tbl = Table(debrief_data, colWidths=[1.0*inch, W - 1.0*inch],
                            rowHeights=[0.7*inch])
        debrief_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (0, 0), _LIGHT),
            ("BOX",           (0, 0), (-1, -1), 0.5, _BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 5),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(debrief_tbl)
        story.append(Spacer(1, 10))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=_BORDER))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Lesson plan generated by Rho (rhocopilot.com) based on logged skill ratings. "
        "Clusters prioritize highest-impact gaps. CFI discretion overrides all suggested sequencing. "
        "Verify tasks against current FAA Private Pilot ACS (PAR-ACS-9).",
        _NOTE,
    ))

    doc.build(story)
    return buf.getvalue()
