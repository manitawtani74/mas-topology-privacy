"""
run_one.py — run a single Terrarium meeting-scheduling simulation and record
EXACT token usage + estimated cost.

Why this exists:
  Terrarium's base_main runs one seed and does not print a cost summary. For a
  budget-constrained sweep we need exact per-run token counts. The OpenAI client
  already computes usage via the static method `OpenAIClient.get_usage`; we wrap
  that method to accumulate a global tally, then run the normal simulation.

Usage:
  .venv/bin/python experiments/runner/run_one.py --config experiments/configs/ms_dev.yaml
  optional overrides: --seed 42 --topology complete --num-agents 3 --edge-prob 0.5

This does NOT modify any framework file — it only monkeypatches at runtime.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# --- make the repo importable (project root = two levels up from this file) ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

# CoLLAB must be importable BEFORE terrarium.environments.dcops is imported.
# We set it here so import order can never bite us (belt-and-suspenders with .env).
os.environ.setdefault("TERRARIUM_COLLAB_PATH", str(Path.home() / "CoLLAB_SEA"))

from dotenv import load_dotenv  # noqa: E402
load_dotenv()

import logging  # noqa: E402
logging.basicConfig(level=logging.WARNING, force=True)
for _n in ("httpx", "httpcore", "openai"):
    logging.getLogger(_n).setLevel(logging.WARNING)

# --- gpt-4.1-mini pricing (USD per 1M tokens). VERIFY against current OpenAI ---
# pricing before trusting the dollar figures; token counts are always exact.
PRICE_PER_1M = {
    "input": 0.40,
    "output": 1.60,
}

# Global accumulator, filled by the wrapped get_usage.
TALLY = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _install_usage_hook() -> None:
    """Wrap OpenAIClient.get_usage so every accounted response also updates TALLY."""
    from terrarium.llm.clients.openai_client import OpenAIClient

    original = OpenAIClient.get_usage

    def wrapped(response, current_usage):
        before = dict(current_usage)
        result = original(response, current_usage)
        # get_usage mutates+returns current_usage; the per-call delta is result-before.
        for k in TALLY:
            TALLY[k] += result.get(k, 0) - before.get(k, 0)
        return result

    OpenAIClient.get_usage = staticmethod(wrapped)


def _estimate_cost() -> float:
    return (
        TALLY["prompt_tokens"] / 1_000_000 * PRICE_PER_1M["input"]
        + TALLY["completion_tokens"] / 1_000_000 * PRICE_PER_1M["output"]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--topology", default=None)
    ap.add_argument("--num-agents", type=int, default=None)
    ap.add_argument("--edge-prob", type=float, default=None)
    ap.add_argument("--consolidate", default=None,
                    help="'true'/'false' to override consolidate_channels")
    args = ap.parse_args()

    _install_usage_hook()

    # Import after hook + path setup.
    from terrarium.utils import load_config
    from experiments.runner._terrarium_run import run_simulation

    config = load_config(args.config)

    # Apply CLI overrides (used by the sweep to vary one knob at a time).
    if args.seed is not None:
        config["simulation"]["seed"] = args.seed
    net = config.setdefault("communication_network", {})
    if args.topology is not None:
        net["topology"] = args.topology
    if args.num_agents is not None:
        net["num_agents"] = args.num_agents
    if args.edge_prob is not None:
        net["edge_prob"] = args.edge_prob
    if args.consolidate is not None:
        net["consolidate_channels"] = args.consolidate.strip().lower() == "true"

    seed = config["simulation"]["seed"]
    started = datetime.now()
    ok = asyncio.run(run_simulation(config))
    elapsed = (datetime.now() - started).total_seconds()

    cost = _estimate_cost()
    summary = {
        "ok": ok,
        "config": args.config,
        "seed": seed,
        "topology": net.get("topology"),
        "num_agents": net.get("num_agents"),
        "edge_prob": net.get("edge_prob"),
        "consolidate_channels": net.get("consolidate_channels"),
        "elapsed_seconds": round(elapsed, 1),
        "prompt_tokens": TALLY["prompt_tokens"],
        "completion_tokens": TALLY["completion_tokens"],
        "total_tokens": TALLY["total_tokens"],
        "estimated_cost_usd": round(cost, 4),
        "pricing_per_1M": PRICE_PER_1M,
    }
    # Persist so cost is never lost to stdout flooding.
    results_dir = PROJECT_ROOT / "experiments" / "results" / "run_costs"
    results_dir.mkdir(parents=True, exist_ok=True)
    stamp = started.strftime("%Y%m%d-%H%M%S")
    (results_dir / f"cost_{net.get('topology')}_seed{seed}_{stamp}.json").write_text(
        json.dumps(summary, indent=2))

    print("\n===== RUN COST SUMMARY =====")
    print(json.dumps(summary, indent=2))
    print("============================")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
