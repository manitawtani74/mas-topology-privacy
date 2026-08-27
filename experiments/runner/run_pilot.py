"""
run_pilot.py — pilot at the two ENDS of the density range.

Cells: (path, consolidate=false)  and  (complete, consolidate=true), 3 seeds each.
For each cell we measure the SIMULATION cost and the JUDGE cost separately, read utility
(normalized joint reward) from the run logs, and score leakage under both definitions plus
the exposure-opportunity denominators. Emits one CSV row per run and a full-grid projection.

Run: TERRARIUM_COLLAB_PATH=~/CoLLAB_SEA .venv/bin/python -m experiments.runner.run_pilot
"""
from __future__ import annotations

import asyncio
import copy
import csv
import glob
import json
import logging
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("TERRARIUM_COLLAB_PATH", str(Path.home() / "CoLLAB_SEA"))

from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.WARNING, force=True)
for _n in ("httpx", "httpcore", "openai"):
    logging.getLogger(_n).setLevel(logging.WARNING)

PRICE = {"input": 0.40, "output": 1.60}  # gpt-4.1-mini per 1M tokens (verify vs current)
SIM_TALLY = {"prompt_tokens": 0, "completion_tokens": 0}

CELLS = [("path", False), ("complete", True)]
SEEDS = [436858, 768277, 10664]


def _install_sim_hook():
    from terrarium.llm.clients.openai_client import OpenAIClient
    original = OpenAIClient.get_usage

    def wrapped(response, current_usage):
        before = dict(current_usage)
        result = original(response, current_usage)
        for k in SIM_TALLY:
            SIM_TALLY[k] += result.get(k, 0) - before.get(k, 0)
        return result

    OpenAIClient.get_usage = staticmethod(wrapped)


def _cost(tokens: dict) -> float:
    return (tokens["prompt_tokens"] / 1e6 * PRICE["input"]
            + tokens["completion_tokens"] / 1e6 * PRICE["output"])


def main():
    _install_sim_hook()
    from terrarium.utils import load_config
    from experiments.runner._terrarium_run import run_simulation
    from experiments.detector import score as S
    from experiments.detector import judge as J

    base = load_config(str(PROJECT_ROOT / "experiments/configs/ms_pilot.yaml"))
    rows = []
    for topology, consolidate in CELLS:
        for seed in SEEDS:
            cfg = copy.deepcopy(base)
            cfg["simulation"]["seed"] = seed
            ts = f"pilot-{topology}-{seed}"
            cfg["simulation"]["run_timestamp"] = ts
            net = cfg["communication_network"]
            net["topology"] = topology
            net["consolidate_channels"] = consolidate

            for k in SIM_TALLY:
                SIM_TALLY[k] = 0
            t0 = time.time()
            ok = asyncio.run(run_simulation(cfg))
            run_secs = round(time.time() - t0, 1)
            run_cost = _cost(SIM_TALLY)

            matches = glob.glob(str(PROJECT_ROOT / f"logs/**/{ts}/seed_{seed}"), recursive=True)
            seed_dir = Path(matches[0])
            data = json.loads(sorted(seed_dir.glob("data_iteration_*.json"))[-1].read_text())
            utility = data["joint_reward_ratio"]

            jb = dict(J.JUDGE_USAGE)
            report = S.score_run(seed_dir)
            judge_cost = _cost({k: J.JUDGE_USAGE[k] - jb[k] for k in jb})
            m = report["metrics"]

            row = {
                "topology": topology, "consolidate": consolidate, "seed": seed,
                "ok": ok, "utility": round(utility, 3),
                "run_secs": run_secs,
                "run_cost_usd": round(run_cost, 4), "judge_cost_usd": round(judge_cost, 4),
                "total_cost_usd": round(run_cost + judge_cost, 4),
                **{k: m[k] for k in (
                    "exposures_total_keys", "reachable_fact_recipient_pairs",
                    "leak_opportunities_permissive", "leak_opportunities_strict",
                    "leaked_permissive_keys", "leaked_strict_keys",
                    "leak_rate_permissive", "leak_rate_strict",
                    "leak_realization_permissive", "leak_realization_strict",
                    "leaked_permissive_second_order_excl", "leaked_permissive_second_order_any",
                )},
            }
            rows.append(row)
            print(f"[{topology:8} seed {seed}] util={row['utility']} "
                  f"leak% perm={row['leak_rate_permissive']} strict={row['leak_rate_strict']} "
                  f"realiz perm={row['leak_realization_permissive']} "
                  f"| run=${row['run_cost_usd']} judge=${row['judge_cost_usd']}")

    out = PROJECT_ROOT / "experiments/results/pilot.csv"
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # ---- summary + projection ----
    def cell_rows(topo):
        return [r for r in rows if r["topology"] == topo]

    def avg(rs, k):
        return round(sum(r[k] for r in rs) / len(rs), 4)

    print("\n===== PILOT SUMMARY (mean over 3 seeds) =====")
    for topo in ("path", "complete"):
        rs = cell_rows(topo)
        print(f"{topo:8}: util={avg(rs,'utility')}  "
              f"leak_rate perm={avg(rs,'leak_rate_permissive')} strict={avg(rs,'leak_rate_strict')}  "
              f"realization perm={avg(rs,'leak_realization_permissive')} strict={avg(rs,'leak_realization_strict')}  "
              f"cost=${avg(rs,'total_cost_usd')}/run")

    total_spent = round(sum(r["total_cost_usd"] for r in rows), 4)
    mean_cost = round(sum(r["total_cost_usd"] for r in rows) / len(rows), 4)
    print(f"\nPilot spend: ${total_spent} over {len(rows)} runs (mean ${mean_cost}/run).")
    print("Full-grid projection (topologies x seeds), mean cost/run:")
    for topos in (6,):
        for nseeds in (10, 20, 30):
            print(f"  {topos} topologies x {nseeds} seeds = {topos*nseeds} runs "
                  f"-> ${round(topos*nseeds*mean_cost, 2)}")
    print(f"CSV -> {out}")


if __name__ == "__main__":
    main()
