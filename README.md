# Incidental Privacy Leakage vs. Communication Topology in a Cooperative Multi-Agent System

**How much private information leaks incidentally between LLM agents during ordinary
cooperative coordination — no adversary — as a function of communication-topology density?**

A rigorous evaluation built on [Terrarium](https://github.com/umass-aisec/Terrarium)
(Nakamura et al., [arXiv:2510.14312](https://arxiv.org/abs/2510.14312)). Terrarium is an
**unmodified pip dependency**; the contribution here is the study.

## The question
In Terrarium's meeting-scheduling task with **no attacker**, agents hold private state (which
meetings they're in, their chosen attendance intervals). Coordination requires sharing some of
it. Does private state reach agents with **no task need** for it, and does denser blackboard
connectivity make it worse? We hold the task instance, model (gpt-4.1-mini), and all parameters
fixed and vary **only** the communication topology across 30 published seeds/cell.

> This environment generates **no private valuations or preferences** — we measure leakage of
> *participation structure* and *intervals*, never "preferences."

## Two findings

**1. A null result (the headline).** Agents disclose essentially **all reachable** private state
regardless of topology. Per-opportunity leakage (`realization`) is flat at ~1.0 and per-broadcast
information gain is flat at ~0.73 across every topology. Density governs only *reachability*, so
absolute leakage scales ~2.2× from path to complete as **arithmetic, not carelessness** — and
task utility stays flat (~0.69), so denser communication bought no benefit.

**2. Relay routing is structural, not density-driven.** In topologies with *multiple distinct
relay intermediaries* (path, ring, Erdős–Rényi), private state travels beyond the direct graph
via relay (~4–5 "learned-only-via-relay" facts/run). A **star** — equally sparse — funnels all
relay through one hub and shows almost none (0.67); `complete` shows zero. The driver is the
number of distinct intermediaries a topology provides, **not** its density.

| ![Fig 1](figures/fig1_realization.png) | ![Fig 2](figures/fig2_informative.png) |
|:---:|:---:|
| **Per-opportunity leakage ≈ 1.0 everywhere** (null result) | **Informative fraction flat ~0.73** (a pre-registered prediction that *failed*) |
| ![Fig 3](figures/fig3_absolute.png) | ![Fig 4](figures/fig4_utility.png) |
| **Absolute leakage tracks reachability** (mechanical) | **Utility flat across density** (no benefit) |

Predictions were **pre-registered** before the sweep: **P1 ✓, P2 ✓, P3 ✗, P4 ⚠ (mechanism
corrected), P5 ✓** — reported as they landed, including the failure and the correction. Full
detail, method, and honest limitations in **[`writeup.md`](writeup.md)**.

## Setup
```bash
pip install -e .                       # installs terrarium-agents + study deps
git clone https://github.com/Saad-Mahmud/CoLLAB_SEA.git ~/CoLLAB_SEA
export TERRARIUM_COLLAB_PATH=~/CoLLAB_SEA
cp .env.example .env                   # then add your OPENAI_API_KEY
```

## Verify it runs first (smoke test — ~2¢, under a minute)
Before committing to the full sweep, confirm the install, CoLLAB path, and API key all work with
one tiny run (2 agents, 1 iteration, single topology):
```bash
python -m experiments.runner.run_one --config experiments/configs/ms_dev.yaml
```
Expect a `RUN COST SUMMARY` with `ok: true` and a cost around **$0.003**. If that prints, you're
wired up correctly.

## Full reproduction
```bash
python -m experiments.runner.run_sweep            # 7 topologies × 30 seeds  (see gotchas)
python -m experiments.runner.rescore_all          # score leakage from the logs
python -m experiments.runner.completeness_audit   # verify every run actually finished
python -m experiments.analysis.analyze            # figures + tables + P1–P5 scorecard
```

### The three things that will bite you
- **The sweep is ~3.5 h of _continuous_ compute.** macOS suspends it on idle-sleep, stretching
  wall-clock into days. Hold sleep off for the duration: `caffeinate -i -w <sweep_pid>`.
- **Cost ≈ $3** on gpt-4.1-mini (sweep ~$2.6 + re-judge ~$0.6). Budget accordingly.
- **CoLLAB is required and is _not_ in the pip package** — clone it separately and point
  `TERRARIUM_COLLAB_PATH` at it, or the meeting-scheduling environment won't import.

## Limitations (short)
One environment, one model, one task, 5 agents, 30 seeds; an LLM-judge metric whose error is
bounded to relay/intention facts (first-order leakage is judge-independent via a deterministic
action backstop) and is measurably prompt-sensitive in sparse topologies — quantified, not
hidden (see writeup §5). This is **not** a claim that "Terrarium is insecure" or that "MAS leak
data"; it measures *how much* incidental leakage varies with density — proportionally in absolute
terms, not at all per-opportunity.

## Attribution & license
This study is MIT-licensed ([`LICENSE`](LICENSE)). It uses [Terrarium](https://github.com/umass-aisec/Terrarium)
(MIT) unmodified as a dependency; the DCOP instances use [CoLLAB](https://github.com/Saad-Mahmud/CoLLAB_SEA).
`experiments/runner/_terrarium_run.py` is copied verbatim from Terrarium's `examples/base_main.py`
(MIT), with attribution in its header. If you use this, please cite Terrarium (arXiv:2510.14312).

## AI assistance
Built with AI assistance (Claude Code). All analysis decisions, parameter choices, and
interpretations are mine.
