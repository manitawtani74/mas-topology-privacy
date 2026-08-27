"""
rescore_all.py — recompute leakage metrics for ALL sweep runs FROM THE EXISTING LOGS.

Does NOT re-run any simulation. It re-reads each run's blackboard logs, re-derives ground
truth, and re-scores under all THREE definitions (permissive / strict / strict-but-only-new)
plus both denominators. Writes one authoritative row per run to sweep_full.csv. Each run's
leakage_report.json is cached so a future definition can be recomputed with zero judging.

Run AFTER the sweep completes:
  TERRARIUM_COLLAB_PATH=~/CoLLAB_SEA .venv/bin/python -m experiments.runner.rescore_all
"""
from __future__ import annotations

import csv
import glob
import json
import logging
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("TERRARIUM_COLLAB_PATH", str(Path.home() / "CoLLAB_SEA"))
logging.basicConfig(level=logging.WARNING, force=True)
for _n in ("httpx", "httpcore", "openai"):
    logging.getLogger(_n).setLevel(logging.WARNING)

from experiments.detector import score as S
from experiments.detector import judge as J

OUT = PROJECT_ROOT / "experiments/results/sweep_full.csv"
DIR_RE = re.compile(r"sweep-([a-z0-9]+)-(\d+)/seed_\1?\d+$")


def cost_lookup() -> dict:
    """Pull run/judge cost from the sweep progress CSV, keyed by (label, seed)."""
    p = PROJECT_ROOT / "experiments/results/sweep.csv"
    out = {}
    if p.exists():
        for r in csv.DictReader(open(p)):
            try:
                out[(r["label"], int(r["seed"]))] = (
                    float(r.get("run_cost_usd") or 0), float(r.get("run_secs") or 0))
            except Exception:
                pass
    return out


def ok_set() -> set:
    """(label, seed) pairs the sweep marked ok=True. A failed run can still leave a
    directory with a misleading data_iteration_*.json, so we trust the CSV's ok flag,
    not the presence of files. A pair is OK if ANY row for it is ok=True (covers reruns)."""
    p = PROJECT_ROOT / "experiments/results/sweep.csv"
    ok = set()
    if p.exists():
        for r in csv.DictReader(open(p)):
            if r.get("ok") == "True":
                try:
                    ok.add((r["label"], int(r["seed"])))
                except Exception:
                    pass
    return ok


def main():
    dirs = sorted(glob.glob(str(PROJECT_ROOT / "logs/**/sweep-*/seed_*"), recursive=True))
    costs = cost_lookup()
    ok = ok_set()
    rows = []
    failed = []
    reused = judged = skipped_notok = incomplete = 0
    for d in dirs:
        dp = Path(d)
        mobj = re.search(r"sweep-([a-z0-9]+)-(\d+)", d)
        if not mobj:
            continue
        label, seed = mobj.group(1), int(mobj.group(2))
        # EXCLUSION AUTHORITY = the sweep CSV's ok flag, NOT file presence. A failed run can
        # leave a directory with a misleading data_iteration_*.json (verified: er025/774005),
        # so we never score a (label,seed) unless a row for it is marked ok=True.
        if (label, seed) not in ok:
            skipped_notok += 1
            continue
        data_files = sorted(dp.glob("data_iteration_*.json"))
        if not data_files:
            skipped_notok += 1
            continue
        data = json.loads(data_files[-1].read_text())
        # INDEPENDENT completion check (not trusting the file's mere existence): every decision
        # variable was actually assigned. Recorded, never silently dropped.
        assigned = int(data.get("variables_assigned", -1))
        total = int(data.get("total_variables", -1))
        complete = (assigned == total and total > 0)
        if not complete:
            incomplete += 1

        report_path = dp / "leakage_report.json"
        if report_path.exists():  # reuse cached judging
            report = json.loads(report_path.read_text())
            reused += 1
        else:
            try:
                report = S.score_run(dp, use_judge=True, save=True)
                judged += 1
            except Exception as e:  # transient API error etc. — skip, resume later reuses cache
                print(f"  SKIP {label}/{seed}: {e}")
                failed.append((label, seed))
                continue
        run_cost, run_secs = costs.get((label, seed), (None, None))
        rows.append({"label": label, "seed": seed,
                     "utility": data["joint_reward_ratio"],
                     "variables_assigned": assigned, "total_variables": total,
                     "complete": complete,
                     "run_cost_usd": run_cost, "run_secs": run_secs,
                     **report["metrics"]})
        if (reused + judged) % 20 == 0:
            print(f"  processed {reused+judged} (reused {reused}, judged {judged})")
    print(f"included {len(rows)} runs; skipped {skipped_notok} not-ok; "
          f"{incomplete} included runs flagged incomplete (assigned<total); "
          f"{len(failed)} failed-to-judge (rerun to retry): {failed}")

    if not rows:
        print("No sweep run directories found yet.")
        return
    fields = list(rows[0].keys())
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {len(rows)} rows to {OUT} (reused {reused} cached, judged {judged}).")
    print(f"judge cost this pass: ${J.judge_cost_usd():.4f}")


if __name__ == "__main__":
    main()
