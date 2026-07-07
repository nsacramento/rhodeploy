"""Quick smoke test for the ACS module — run from /Users/nic/rho"""
import sys
sys.path.insert(0, ".")
from rho.modules.acs      import (log_skill, get_skill_matrix, get_training_plan,
                                   get_readiness_summary, get_skill_warnings, ACS_TASKS,
                                   PROFICIENCY_LABELS)
from rho.modules.insights import get_preflight_brief

SEP = "=" * 55

# ── Show full ACS task list ───────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  PRIVATE PILOT ACS — {len(ACS_TASKS)} TASKS")
print(f"{SEP}")
current_area = None
for task_id, t in ACS_TASKS.items():
    if t["area_name"] != current_area:
        current_area = t["area_name"]
        print(f"\n  Area {t['area']} — {t['area_name']}")
    print(f"    {task_id:<8}  {t['name']}")

# ── Log some sample proficiency entries ──────────────────────────────────────
print(f"\n{SEP}")
print(f"  LOGGING SAMPLE PROFICIENCY")
print(f"{SEP}\n")

sample = [
    ("II-A", 3, "Preflight walkaround to ACS standard"),
    ("II-C", 3, "Engine start, taxi, runup solid"),
    ("IV-A", 3, "Normal T/O good"),
    ("IV-B", 2, "Landing consistent but slightly long"),
    ("IV-G", 1, "First crosswind attempt — needs work"),
    ("VII-B", 2, "Power-off stalls practiced"),
    ("VII-C", 1, "Power-on stalls introduced"),
    ("IX-B", 2, "Emergency landing practiced over practice area"),
    ("I-C",  3, "Weather briefing and go/no-go solid"),
    ("VI-A", 2, "Pilotage XC practiced with CFI"),
]

for task_id, prof, notes in sample:
    log_skill(task_id, prof, cfi_notes=notes)
    print(f"  {task_id:<8} {PROFICIENCY_LABELS[prof]:<14}  {ACS_TASKS[task_id]['name']}")

# ── Skill matrix summary ──────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  CHECKRIDE READINESS")
print(f"{SEP}\n")

matrix = get_skill_matrix()
print(f"  {get_readiness_summary(matrix)}")

# ── Training plan ─────────────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  TRAINING PLAN — TOP 10 PRIORITIES")
print(f"{SEP}\n")

plan = get_training_plan(matrix)
for item in plan[:10]:
    print(f"  [{item['priority']}] {item['task_id']:<8} {item['proficiency_label']:<14}  "
          f"{item['name']}")
    print(f"           {item['area_name']} — {item['reason']}")

# ── Skill-aware go/no-go ──────────────────────────────────────────────────────
print(f"\n{SEP}")
print(f"  SKILL-AWARE GO/NO-GO: KSRQ → KVNC")
print(f"{SEP}\n")

brief = get_preflight_brief("KSRQ", "KVNC")
skill_warnings = get_skill_warnings(brief, matrix)

if skill_warnings:
    for w in skill_warnings:
        print(f"  ⚠  {w}")
else:
    print("  ✓ Flight conditions within demonstrated skill level")

print(f"\n{SEP}\n")
