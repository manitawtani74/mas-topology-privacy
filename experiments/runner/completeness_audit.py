"""
completeness_audit.py — verify every sweep run actually FINISHED, not just that files exist.

data_iteration_*.json is written from the environment's assignment state and can be present
even for a run that died mid-way, so we do NOT trust file presence. For each run directory we
cross-check THREE signals and flag any disagreement:
  1. sweep.csv `ok` flag            (did run_simulation return without raising?)
  2. variables_assigned == total    (did every decision variable get assigned?)
  3. distinct (agent, meeting) execution actions in the blackboards == total_variables
     (did every agent actually act on every one of its meetings? — independent of #2)

A run is CLEAN only if ok=True AND (2) AND (3) agree. Everything else is listed so it can be
rerun or explicitly reported — never averaged over silently. Deterministic; no API calls.

Run AFTER the sweep: TERRARIUM_COLLAB_PATH=~/CoLLAB_SEA .venv/bin/python -m experiments.runner.completeness_audit
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("TERRARIUM_COLLAB_PATH", str(Path.home() / "CoLLAB_SEA"))

from experiments.detector import leakage as L

SWEEP_CSV = PROJECT_ROOT / "experiments/results/sweep.csv"
EXPECTED_SEEDS = 30
CELLS = ["path", "ring", "star", "er025", "er050", "er075", "complete"]


def csv_ok_map():
    """(label,seed) -> True if ANY row ok=True, else False (present but failed)."""
    ok = {}
    if SWEEP_CSV.exists():
        for r in csv.DictReader(open(SWEEP_CSV)):
            try:
                key = (r["label"], int(r["seed"]))
            except Exception:
                continue
            ok[key] = ok.get(key, False) or (r.get("ok") == "True")
    return ok


def exec_action_pairs(seed_dir: Path) -> int:
    """distinct (agent, meeting_id) execution actions logged to the blackboards."""
    pairs = set()
    for ev in L.parse_blackboards(seed_dir):
        if ev.kind == "action_executed" and ev.meeting_id:
            pairs.add((ev.poster, ev.meeting_id))
    return len(pairs)


def main():
    ok_map = csv_ok_map()
    dirs = sorted(glob.glob(str(PROJECT_ROOT / "logs/**/sweep-*/seed_*"), recursive=True))

    clean = defaultdict(int)
    flags = []
    seen = set()
    for d in dirs:
        dp = Path(d)
        mobj = re.search(r"sweep-([a-z0-9]+)-(\d+)", d)
        if not mobj:
            continue
        label, seed = mobj.group(1), int(mobj.group(2))
        seen.add((label, seed))
        ok = ok_map.get((label, seed), None)

        data_files = sorted(dp.glob("data_iteration_*.json"))
        if not data_files:
            flags.append((label, seed, "no data_iteration file"))
            continue
        data = json.loads(data_files[-1].read_text())
        assigned = int(data.get("variables_assigned", -1))
        total = int(data.get("total_variables", -1))
        actions = exec_action_pairs(dp)

        problems = []
        if ok is not True:
            problems.append(f"csv_ok={ok}")
        if assigned != total or total <= 0:
            problems.append(f"assigned {assigned}/{total}")
        if actions != total:
            problems.append(f"exec_actions {actions} != total {total}")
        if problems:
            flags.append((label, seed, "; ".join(problems)))
        else:
            clean[label] += 1

    # CSV rows whose directory is missing entirely
    for (label, seed), okv in ok_map.items():
        if (label, seed) not in seen:
            flags.append((label, seed, f"csv row (ok={okv}) but NO directory"))

    print("=== CLEAN complete runs per cell (need 30) ===")
    short = []
    for c in CELLS:
        n = clean.get(c, 0)
        mark = "" if n >= EXPECTED_SEEDS else "  <-- SHORT"
        if n < EXPECTED_SEEDS:
            short.append((c, n))
        print(f"  {c:9} {n}/{EXPECTED_SEEDS}{mark}")

    print(f"\n=== {len(flags)} flagged run(s) (excluded / needs attention) ===")
    for label, seed, why in sorted(flags):
        print(f"  {label:9} seed {seed}: {why}")

    if short:
        print("\nCELLS SHORT OF 30 — must be stated in the writeup, not averaged over:")
        for c, n in short:
            print(f"  {c}: {n}/30")
    else:
        print("\nAll cells have 30 clean complete runs.")


if __name__ == "__main__":
    main()
