"""
audit_recall.py — recall audit for the judge. For a run, print every communication
message next to the facts the judge extracted from it, so a human can spot MISSED
disclosures (false negatives) before trusting the metric.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.WARNING, force=True)
for _n in ("httpx", "httpcore", "openai"):
    logging.getLogger(_n).setLevel(logging.WARNING)

from experiments.detector import leakage as L
from experiments.detector import judge as J


def main():
    d = Path(sys.argv[1])
    gt = L.build_ground_truth(d)
    print("MEETINGS:")
    for mid, m in gt.meetings.items():
        print(f"  {mid} {m['type']:6} [{m['start']},{m['end']}) {m['participants']}")
    print()
    for ev in L.parse_blackboards(d):
        if ev.kind != "communication" or ev.poster == "SYSTEM" or not ev.text.strip():
            continue
        print("=" * 80)
        print(f"POSTER: {ev.poster}   (board {ev.blackboard_id}, members {ev.members})")
        print("MESSAGE:")
        print("  " + ev.text.replace("\n", "\n  "))
        print("JUDGE EXTRACTED:")
        ds = J.judge_message(ev.poster, ev.text, gt.meetings, gt.agents)
        if not ds:
            print("  (nothing)")
        for x in ds:
            bits = []
            if x.participation:
                bits.append(f"participation={x.participation}")
            if x.interval:
                bits.append(f"interval={x.interval} ({x.interval_value})")
            print(f"  - {x.subject} @ {x.meeting_id}: {', '.join(bits)}")
        print()
    print(f"[judge cost for this audit: ${J.judge_cost_usd():.4f}]")


if __name__ == "__main__":
    main()
