"""
inspect_instance.py — $0, NO-API inspection of a CoLLAB meeting-scheduling
problem instance.

Goal: expose the *ground truth* of what each agent privately holds, and derive
the need-to-know mapping straight from the DCOP factor graph (not from guesswork).
This is the foundation the leakage metric will be built on, so we look at the
real generated data before writing any judge.

Run:
  TERRARIUM_COLLAB_PATH=~/CoLLAB_SEA .venv/bin/python \
      experiments/detector/inspect_instance.py --seed 436858 --agents 5 --meetings 5
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections import defaultdict
from itertools import combinations
from pathlib import Path

os.environ.setdefault("TERRARIUM_COLLAB_PATH", str(Path.home() / "CoLLAB_SEA"))
sys.path.insert(0, os.environ["TERRARIUM_COLLAB_PATH"])

from problem_layer.meeting_scheduling import MeetingSchedulingConfig, generate_instance  # noqa: E402


def build(seed: int, agents: int, meetings: int):
    cfg = MeetingSchedulingConfig(
        num_agents=agents,
        num_meetings=meetings,
        timeline_length=12,
        min_participants=2,
        max_participants=3,
        soft_meeting_ratio=0.6,
        rng_seed=seed,
    )
    with tempfile.TemporaryDirectory() as td:
        return generate_instance(cfg, Path(td))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=436858)
    ap.add_argument("--agents", type=int, default=5)
    ap.add_argument("--meetings", type=int, default=5)
    ap.add_argument("--focus", default=None, help="agent name to show raw state for")
    args = ap.parse_args()

    inst = build(args.seed, args.agents, args.meetings)
    problem = inst.problem
    agent_names = list(problem.agents.keys())
    focus = args.focus or agent_names[0]

    print("=" * 78)
    print(f"INSTANCE  seed={args.seed}  agents={args.agents}  meetings(req)={args.meetings}")
    print(f"actual meetings generated: {len(inst.meetings)}   timeline={inst.timeline_length}")
    print(f"agents: {', '.join(agent_names)}")
    print("=" * 78)

    # ---- Meeting roster (who is in what, and soft vs strict) -----------------
    print("\n### MEETINGS (title / type / window / participants)")
    soft_meetings, strict_meetings = [], []
    for m in inst.meetings:
        (soft_meetings if m.meeting_type == "soft" else strict_meetings).append(m)
        print(f"  {m.meeting_id}: {m.title!r:34} {m.meeting_type:6} "
              f"[{m.start},{m.end})  participants={list(m.participants)}")

    # ---- RAW private state for ONE agent ------------------------------------
    print("\n" + "=" * 78)
    print(f"### RAW PRIVATE STATE FOR AGENT: {focus}")
    print("=" * 78)
    print("\n-- (1) The literal instruction string this agent is given (its private context):")
    print("    " + inst.explanations[focus].replace("\n", "\n    "))

    print("\n-- (2) This agent's decision variables (its 'slots' to choose) + domains:")
    for v in problem.agent_variables(focus):
        print(f"     {v.name}: owner={v.owner}  domain={list(v.domain)}")

    print("\n-- (3) Factors touching this agent, by type:")
    for f in problem.factors:
        owners = {problem.variables[s].owner for s in f.scope if s in problem.variables}
        if focus in owners:
            print(f"     [{f.factor_type:18}] {f.name}  scope={list(f.scope)}")

    # ---- NEED-TO-KNOW derived from the factor graph -------------------------
    # Rule: two agents have a legitimate need to exchange state about a variable
    # ONLY if they co-appear in the scope of a *coordination* factor (multi-owner).
    # personal_preference factors are unary -> owner-only, never shared.
    coord_pairs = set()          # frozenset({A,B}) that share a coordination factor
    coord_meeting_of_pair = defaultdict(set)
    for f in problem.factors:
        if f.factor_type != "coordination":
            continue
        owners = sorted({problem.variables[s].owner for s in f.scope if s in problem.variables})
        if len(owners) < 2:
            continue  # within-agent coordination (e.g. self overlap penalty) -> private
        for a, b in combinations(owners, 2):
            coord_pairs.add(frozenset((a, b)))
            # recover meeting id from a scoped var name A__mID
            for s in f.scope:
                mid = s.split("__", 1)[1] if "__" in s else None
                if mid:
                    coord_meeting_of_pair[frozenset((a, b))].add(mid)

    # Co-participation (any shared meeting, regardless of type)
    shared_any = defaultdict(set)   # pair -> set(meeting_ids)
    shared_soft = defaultdict(set)
    shared_strict = defaultdict(set)
    for m in inst.meetings:
        for a, b in combinations(sorted(set(m.participants)), 2):
            key = frozenset((a, b))
            shared_any[key].add(m.meeting_id)
            (shared_soft if m.meeting_type == "soft" else shared_strict)[key].add(m.meeting_id)

    print("\n" + "=" * 78)
    print("### NEED-TO-KNOW MAPPING (derived from the factor graph)")
    print("=" * 78)
    print("\n-- Agent pairs that SHARE A COORDINATION FACTOR (legit need to exchange")
    print("   their chosen interval for that meeting):")
    if coord_pairs:
        for pair in sorted(map(lambda s: tuple(sorted(s)), coord_pairs)):
            mids = sorted(coord_meeting_of_pair[frozenset(pair)])
            print(f"     {pair[0]} <-> {pair[1]}   via meetings {mids}")
    else:
        print("     (none)")

    all_pairs = {frozenset(p) for p in combinations(sorted(agent_names), 2)}

    print("\n-- Agent pairs that SHARE NO MEETING AT ALL (zero legitimate need for")
    print("   ANY of each other's state):")
    none_pairs = [tuple(sorted(p)) for p in all_pairs if p not in shared_any]
    for p in sorted(none_pairs):
        print(f"     {p[0]} <-> {p[1]}")
    if not none_pairs:
        print("     (every pair shares at least one meeting)")

    print("\n-- Agent pairs that share ONLY a STRICT meeting (they co-attend, so each")
    print("   appears on the other's roster, but strict utility is unary => NO")
    print("   coordination need; sharing intervals here is NOT task-necessary):")
    strict_only = [p for p in all_pairs if p in shared_strict and p not in shared_soft]
    for p in sorted(strict_only, key=lambda s: tuple(sorted(s))):
        a, b = sorted(p)
        print(f"     {a} <-> {b}   strict meetings {sorted(shared_strict[p])}")
    if not strict_only:
        print("     (none)")

    print("\n-- Sanity: coordination-factor pairs should equal soft-sharing pairs:")
    soft_pairs = {p for p in all_pairs if p in shared_soft}
    print(f"     coordination pairs == soft-sharing pairs ? "
          f"{coord_pairs == soft_pairs}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
