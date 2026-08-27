"""
run_sweep.py — the topology density sweep (Phase 4). RESUMABLE.

Holds everything fixed (5 agents, environment, model, consolidate_channels=true) and varies
ONLY communication topology, from sparse to dense:
    path -> ring(WS k=2,p=0) -> star -> erdos_renyi(0.25/0.5/0.75) -> complete
30 published Appendix-B.2 seeds per cell. One CSV row per run, written immediately so an
interruption can be resumed (already-completed (label,seed) cells are skipped on restart).

consolidate_channels=true throughout so the density axis is clean: sparse topologies (path,
ring, star) have no cliques>=3 so consolidation is a no-op (pairwise boards); dense ones merge
into shared boards — exactly the "who broadcasts to whom" gradient we want.

Run: TERRARIUM_COLLAB_PATH=~/CoLLAB_SEA .venv/bin/python -m experiments.runner.run_sweep
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
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("TERRARIUM_COLLAB_PATH", str(Path.home() / "CoLLAB_SEA"))

from dotenv import load_dotenv
load_dotenv()
logging.basicConfig(level=logging.WARNING, force=True)
for _n in ("httpx", "httpcore", "openai"):
    logging.getLogger(_n).setLevel(logging.WARNING)

PRICE = {"input": 0.40, "output": 1.60}
SIM_TALLY = {"prompt_tokens": 0, "completion_tokens": 0}

# Topology cells in increasing density. `net` holds the per-cell overrides.
CELLS = [
    {"label": "path",     "net": {"topology": "path"}},
    {"label": "ring",     "net": {"topology": "watts_strogatz", "k": 2, "rewire_prob": 0}},
    {"label": "star",     "net": {"topology": "star"}},
    {"label": "er025",    "net": {"topology": "erdos_renyi", "edge_prob": 0.25}},
    {"label": "er050",    "net": {"topology": "erdos_renyi", "edge_prob": 0.50}},
    {"label": "er075",    "net": {"topology": "erdos_renyi", "edge_prob": 0.75}},
    {"label": "complete", "net": {"topology": "complete"}},
]

# 30 seeds, Appendix B.2 (paper.md).
SEEDS = [436858, 768277, 10664, 860016, 865292, 841848, 313147, 896678, 386308, 977048,
         203069, 283373, 593503, 457419, 169542, 391186, 130304, 916639, 453967, 273773,
         589383, 657683, 182813, 641487, 580095, 195884, 372142, 774005, 768470, 95729]

OUT = PROJECT_ROOT / "experiments/results/sweep.csv"

METRIC_KEYS = (
    "exposures_total_keys",
    "reachable_fact_recipient_pairs", "relay_reachable_fact_recipient_pairs",
    "leak_opportunities_permissive", "leak_opportunities_strict",
    "relay_leak_opportunities_permissive", "relay_leak_opportunities_strict",
    "leaked_permissive_keys", "leaked_strict_keys",
    "leaked_permissive_participation", "leaked_permissive_interval",
    "leaked_strict_participation", "leaked_strict_interval",
    "leak_rate_permissive", "leak_rate_strict",
    "leak_realization_permissive", "leak_realization_strict",
    "leak_realization_relay_permissive", "leak_realization_relay_strict",
    "leaked_permissive_second_order_excl", "leaked_permissive_second_order_any",
    "leaked_strict_second_order_excl", "leaked_strict_second_order_any",
)
FIELDS = (["label", "topology", "seed", "ok", "utility", "run_secs",
           "run_cost_usd", "judge_cost_usd", "total_cost_usd"] + list(METRIC_KEYS))


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
    return tokens["prompt_tokens"] / 1e6 * PRICE["input"] + tokens["completion_tokens"] / 1e6 * PRICE["output"]


def _done_cells() -> set:
    done = set()
    if OUT.exists():
        for r in csv.DictReader(open(OUT)):
            if r.get("ok") == "True":
                done.add((r["label"], int(r["seed"])))
    return done


def main():
    _install_sim_hook()
    from terrarium.utils import load_config
    from experiments.runner._terrarium_run import run_simulation
    from experiments.detector import score as S
    from experiments.detector import judge as J

    base = load_config(str(PROJECT_ROOT / "experiments/configs/ms_pilot.yaml"))
    base["communication_network"]["consolidate_channels"] = True

    done = _done_cells()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    new_file = not OUT.exists()
    fh = open(OUT, "a", newline="")
    writer = csv.DictWriter(fh, fieldnames=FIELDS)
    if new_file:
        writer.writeheader(); fh.flush()

    total = len(CELLS) * len(SEEDS)
    idx = 0
    spent = 0.0
    for cell in CELLS:
        for seed in SEEDS:
            idx += 1
            if (cell["label"], seed) in done:
                continue
            cfg = copy.deepcopy(base)
            cfg["simulation"]["seed"] = seed
            ts = f"sweep-{cell['label']}-{seed}"
            cfg["simulation"]["run_timestamp"] = ts
            cfg["communication_network"].update(cell["net"])

            for k in SIM_TALLY:
                SIM_TALLY[k] = 0
            row = {"label": cell["label"], "topology": cell["net"]["topology"], "seed": seed}
            try:
                t0 = time.time()
                ok = asyncio.run(run_simulation(cfg))
                row["run_secs"] = round(time.time() - t0, 1)
                run_cost = _cost(SIM_TALLY)
                matches = glob.glob(str(PROJECT_ROOT / f"logs/**/{ts}/seed_{seed}"), recursive=True)
                seed_dir = Path(matches[0])
                data = json.loads(sorted(seed_dir.glob("data_iteration_*.json"))[-1].read_text())
                jb = dict(J.JUDGE_USAGE)
                report = S.score_run(seed_dir)
                judge_cost = _cost({k: J.JUDGE_USAGE[k] - jb[k] for k in jb})
                m = report["metrics"]
                row.update({
                    "ok": ok, "utility": round(data["joint_reward_ratio"], 4),
                    "run_cost_usd": round(run_cost, 4), "judge_cost_usd": round(judge_cost, 4),
                    "total_cost_usd": round(run_cost + judge_cost, 4),
                    **{k: m[k] for k in METRIC_KEYS},
                })
                spent += run_cost + judge_cost
            except Exception as e:
                row["ok"] = False
                print(f"[{idx}/{total}] {cell['label']} seed {seed} FAILED: {e}")
                traceback.print_exc()
            writer.writerow(row); fh.flush()
            if row.get("ok"):
                print(f"[{idx}/{total}] {cell['label']:8} seed {seed}: util={row.get('utility')} "
                      f"leaked S={row.get('leaked_strict_keys')} realiz1={row.get('leak_realization_strict')} "
                      f"${round(spent,3)} cum")
    fh.close()
    print(f"\nSWEEP COMPLETE. cumulative new spend this run: ${round(spent,3)}  CSV -> {OUT}")


if __name__ == "__main__":
    main()
