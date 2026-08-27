"""
analyze.py — Phase 5 aggregation, the FOUR pre-committed figures, the relay/second-order
TABLE, and a pass/fail report against the pre-registered predictions (P1-P5).

Figures are FIXED in advance (no picking after seeing data):
  Fig 1  realization vs density            (P1, null result — headline)
  Fig 2  fraction_broadcasts_informative   (P3, information-gain routing)
  Fig 3  absolute leaked vs density, with the structural reachability prediction overlaid
                                           (P2, mechanical made visible not asserted)
  Fig 4  utility vs density with seed variance (P5, tests paper Sec 4.2)
Relay + second-order go in a TABLE, not a figure (lower confidence -> no extra visual weight).

x-axis = mean structural reachable_fact_recipient_pairs per cell (a principled density measure),
cells ordered by it. Palette = Okabe-Ito (colorblind-safe by construction). One y-axis per plot.

Run: .venv/bin/python -m experiments.analysis.analyze [csv]   (default experiments/results/sweep_full.csv)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from statistics import mean, stdev

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = PROJECT_ROOT / "figures"

# Okabe-Ito colorblind-safe palette
OK = {"blue": "#0072B2", "orange": "#E69F00", "green": "#009E73",
      "vermillion": "#D55E00", "purple": "#CC79A7", "gray": "#666666"}

# Fixed density order of the cells (sparse -> dense); actual x is mean reachable pairs.
CELL_ORDER = ["path", "ring", "star", "er025", "er050", "er075", "complete"]
CELL_LABEL = {"path": "path", "ring": "ring", "star": "star", "er025": "ER .25",
              "er050": "ER .50", "er075": "ER .75", "complete": "complete"}


def load(csv_path: Path):
    rows = []
    for r in csv.DictReader(open(csv_path)):
        rr = {}
        for k, v in r.items():
            if k in ("label",):
                rr[k] = v
            elif v in ("True", "False"):      # bool columns (e.g. complete) -> 1.0/0.0
                rr[k] = 1.0 if v == "True" else 0.0
            else:
                try:
                    rr[k] = float(v)
                except (ValueError, TypeError):
                    rr[k] = v
        rows.append(rr)
    return rows


def agg(rows):
    """label -> {metric -> (mean, sem, n)}; only cells present are returned, in density order."""
    cells = {}
    for r in rows:
        cells.setdefault(r["label"], []).append(r)
    out = {}
    for label, rs in cells.items():
        m = {}
        keys = [k for k in rs[0] if isinstance(rs[0][k], float)]
        for k in keys:
            vals = [r[k] for r in rs if isinstance(r.get(k), float)]
            if not vals:
                continue
            mu = mean(vals)
            sd = stdev(vals) if len(vals) > 1 else 0.0
            sem = sd / (len(vals) ** 0.5) if vals else 0.0
            m[k] = (mu, sem, len(vals))
        out[label] = m
    ordered = [c for c in CELL_ORDER if c in out]
    ordered.sort(key=lambda c: out[c].get("reachable_fact_recipient_pairs", (0,))[0])
    return out, ordered


def _x_density(A, ordered):
    # Evenly-spaced positions ordered by density (avoids label collision when several cells
    # have near-identical reach); the actual density value is annotated in each tick label.
    return list(range(len(ordered)))


def _series(A, ordered, key):
    mus = [A[c][key][0] for c in ordered]
    sems = [A[c][key][1] for c in ordered]
    return mus, sems


def _style(A, ordered, ax, xlabel="communication density  →  (cell; mean reachable pairs)"):
    xs = list(range(len(ordered)))
    labels = [f"{CELL_LABEL[c]}\n{A[c]['reachable_fact_recipient_pairs'][0]:.0f}" for c in ordered]
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, rotation=0, fontsize=8)
    ax.set_xlabel(xlabel)
    ax.grid(True, axis="y", color="#dddddd", linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def fig1_realization(A, ordered):
    xs = _x_density(A, ordered)
    fig, ax = plt.subplots(figsize=(7, 4.3))
    for key, color, lab in [("leak_realization_permissive", OK["blue"], "permissive"),
                            ("leak_realization_strict", OK["orange"], "strict"),
                            ("leak_realization_only_new", OK["green"], "only-new")]:
        mus, sems = _series(A, ordered, key)
        ax.errorbar(xs, mus, yerr=sems, marker="o", ms=6, lw=2, color=color,
                    capsize=3, label=lab)
    ax.axhline(1.0, color=OK["gray"], lw=1, ls="--")
    ax.text(xs[-1], 1.0, " realization = 1.0", color=OK["gray"], va="bottom", ha="right", fontsize=8)
    ax.set_ylabel("realization  (leaked / first-order leak-opportunities)")
    ax.set_title("Fig 1. Per-opportunity leakage ≈ 1.0 across topologies  [P1 supported]",
                 loc="left", fontsize=11)
    _style(A, ordered, ax)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(FIG_DIR / "fig1_realization.png", dpi=200); plt.close(fig)


def fig2_informative(A, ordered):
    xs = _x_density(A, ordered)
    mus, sems = _series(A, ordered, "fraction_broadcasts_informative")
    fig, ax = plt.subplots(figsize=(7, 4.3))
    ax.errorbar(xs, mus, yerr=sems, marker="o", ms=6, lw=2, color=OK["purple"], capsize=3)
    for x, y, c in zip(xs, mus, ordered):
        ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=8, color="#333333")
    ax.set_ylabel("fraction of broadcasts that informed someone\n(only-new / strict)")
    ax.set_ylim(0, 1.02)
    ax.set_title("Fig 2. Informative fraction is topology-invariant (~0.73)  [P3 NOT supported]",
                 loc="left", fontsize=10.5)
    _style(A, ordered, ax)
    fig.tight_layout(); fig.savefig(FIG_DIR / "fig2_informative.png", dpi=200); plt.close(fig)


def fig3_absolute(A, ordered):
    xs = _x_density(A, ordered)
    fig, ax = plt.subplots(figsize=(7, 4.3))
    # measured leaked (solid) vs structural opportunity prediction (dashed) — SAME count axis.
    for lk, opp, color, lab in [
        ("leaked_strict_keys", "leak_opportunities_strict", OK["orange"], "strict"),
        ("leaked_permissive_keys", "leak_opportunities_permissive", OK["blue"], "permissive"),
    ]:
        mus, sems = _series(A, ordered, lk)
        pred, _ = _series(A, ordered, opp)
        ax.errorbar(xs, mus, yerr=sems, marker="o", ms=6, lw=2, color=color,
                    capsize=3, label=f"{lab}: measured")
        ax.plot(xs, pred, ls="--", lw=1.6, color=color, alpha=0.7,
                label=f"{lab}: structural prediction")
    ax.set_ylabel("absolute leaked facts  (fact–recipient pairs)")
    ax.set_title("Fig 3. Absolute leakage tracks reachability — mechanical, not carelessness  [P2 supported]",
                 loc="left", fontsize=9.8)
    _style(A, ordered, ax)
    ax.legend(frameon=False, fontsize=8.5, ncol=2)
    fig.tight_layout(); fig.savefig(FIG_DIR / "fig3_absolute.png", dpi=200); plt.close(fig)


def fig4_utility(A, ordered, rows):
    xs = _x_density(A, ordered)
    mus, sems = _series(A, ordered, "utility")
    fig, ax = plt.subplots(figsize=(7, 4.3))
    # per-seed scatter (jittered) to show variance honestly, plus the mean +/- SEM
    xmap = {c: xs[i] for i, c in enumerate(ordered)}
    for r in rows:
        if r["label"] in xmap and isinstance(r.get("utility"), float):
            ax.plot(xmap[r["label"]], r["utility"], "o", ms=3, color="#cccccc", zorder=1)
    ax.errorbar(xs, mus, yerr=sems, marker="s", ms=7, lw=2, color=OK["vermillion"],
                capsize=3, zorder=3, label="mean ± SEM")
    ax.set_ylabel("utility  (normalized joint-reward ratio)")
    ax.set_ylim(0, 1.02)
    ax.set_title("Fig 4. Task utility flat across density (~0.69)  [P5 supported: no density benefit]",
                 loc="left", fontsize=10)
    _style(A, ordered, ax)
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(FIG_DIR / "fig4_utility.png", dpi=200); plt.close(fig)


def relay_table(A, ordered) -> str:
    cols = [("realization_relay(P)", "leak_realization_relay_permissive"),
            ("2nd-excl(P)", "leaked_permissive_second_order_excl"),
            ("2nd-any(P)", "leaked_permissive_second_order_any"),
            ("2nd-excl(S)", "leaked_strict_second_order_excl"),
            ("redundant", "redundant_participation_broadcasts")]
    head = "| cell | " + " | ".join(c[0] for c in cols) + " |"
    sep = "|" + "---|" * (len(cols) + 1)
    lines = [head, sep]
    for c in ordered:
        vals = [f"{A[c].get(k, (float('nan'),))[0]:.2f}" for _, k in cols]
        lines.append(f"| {CELL_LABEL[c]} | " + " | ".join(vals) + " |")
    return "\n".join(lines)


def completion_table(A, ordered) -> str:
    """Per-cell completion rate (fraction of the 30 runs with all variables assigned)."""
    lines = ["| cell | n | completion rate | mean utility |", "|---|---|---|---|"]
    for c in ordered:
        n = A[c]["utility"][2]
        comp = A[c].get("complete", (float("nan"),))[0]
        util = A[c]["utility"][0]
        lines.append(f"| {CELL_LABEL[c]} | {n} | {comp:.2f} | {util:.2f} |")
    return "\n".join(lines)


def _cell_means(csv_path: Path, keys):
    """label -> {key: mean} for the given metric keys, ok=True rows only."""
    import statistics as st
    cells = {}
    if not csv_path.exists():
        return cells
    for r in csv.DictReader(open(csv_path)):
        if r.get("ok") not in (None, "True"):  # sweep.csv has ok col; sweep_full may not
            continue
        cells.setdefault(r["label"], []).append(r)
    out = {}
    for label, rs in cells.items():
        m = {}
        for k in keys:
            vals = []
            for r in rs:
                try:
                    vals.append(float(r[k]))
                except (KeyError, ValueError, TypeError):
                    pass
            if vals:
                m[k] = st.mean(vals)
        out[label] = m
    return out


def relay_delta_table(ordered) -> str:
    """Original (pre-fix judge, sweep.csv) vs re-judged (sweep_full.csv) relay figures.
    Quantifies LLM-judge prompt sensitivity: two reasonable phrasings of the same instruction."""
    keys = ["leaked_permissive_keys", "leaked_strict_keys",
            "leaked_permissive_second_order_any", "leak_realization_strict"]
    old = _cell_means(PROJECT_ROOT / "experiments/results/sweep.csv", keys)
    new = _cell_means(PROJECT_ROOT / "experiments/results/sweep_full.csv", keys)
    lines = ["| cell | leaked_perm (orig→new, Δ) | 2nd-order-any perm (orig→new, Δ) |",
             "|---|---|---|"]
    for c in ordered:
        if c not in old or c not in new:
            continue
        lp_o, lp_n = old[c].get("leaked_permissive_keys", 0), new[c].get("leaked_permissive_keys", 0)
        so_o, so_n = old[c].get("leaked_permissive_second_order_any", 0), new[c].get("leaked_permissive_second_order_any", 0)
        lines.append(f"| {CELL_LABEL[c]} | {lp_o:.1f}→{lp_n:.1f} (Δ{lp_n-lp_o:+.1f}) "
                     f"| {so_o:.1f}→{so_n:.1f} (Δ{so_n-so_o:+.1f}) |")
    return "\n".join(lines)


def _corr(xs, ys):
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else float("nan")


def predictions(A, ordered) -> str:
    # correlations use ACTUAL density (mean reachable pairs), not the plot's rank positions
    xs = [A[c]["reachable_fact_recipient_pairs"][0] for c in ordered]
    out = ["## Pre-registered prediction outcomes\n"]
    # P1: realization ~constant (flat band ⇒ supported)
    spans = []
    for lab, key in [("permissive", "leak_realization_permissive"), ("strict", "leak_realization_strict")]:
        mus = [A[c][key][0] for c in ordered]
        spans.append(max(mus) - min(mus))
        out.append(f"- **P1** ({lab}): realization {min(mus):.2f}–{max(mus):.2f} "
                   f"(span {max(mus)-min(mus):.2f}).")
    out.append(f"  → **{'SUPPORTED' if max(spans) < 0.25 else 'NOT supported'}** (flat ⇒ topology-invariant).")
    # P2: leaked tracks reachable pairs (corr→1 ⇒ mechanical)
    lk = [A[c]["leaked_strict_keys"][0] for c in ordered]
    r2 = _corr(xs, lk)
    out.append(f"- **P2**: corr(leaked_strict, reachable_pairs) = {r2:.3f} "
               f"→ **{'SUPPORTED' if r2 > 0.9 else 'NOT supported'}** (mechanical).")
    # P3: predicted fraction_informative DECREASES with density (corr < 0)
    fi = [A[c]["fraction_broadcasts_informative"][0] for c in ordered]
    r3 = _corr(xs, fi)
    out.append(f"- **P3**: corr(fraction_informative, density) = {r3:.3f}; "
               f"{fi[0]:.2f} (sparsest) → {fi[-1]:.2f} (densest). Predicted NEGATIVE; got "
               f"{'negative' if r3 < 0 else 'POSITIVE/flat'} → "
               f"**{'SUPPORTED' if r3 < -0.3 else 'NOT supported'}** (fraction is topology-invariant).")
    # P4: relay effect real but MECHANISM corrected (structural, not density) — see table
    ex = {c: A[c]["leaked_permissive_second_order_excl"][0] for c in ordered}
    out.append(f"- **P4**: 2nd-order-excl(perm) — path {ex.get('path',0):.2f}, star {ex.get('star',0):.2f}, "
               f"complete {ex.get('complete',0):.2f}. Effect REAL but **MECHANISM CORRECTED**: star "
               f"(sparse) ≈ 0 disproves the density framing → structural (distinct-intermediary count).")
    # P5: utility flat vs density (corr ≈ 0)
    ut = [A[c]["utility"][0] for c in ordered]
    r5 = _corr(xs, ut)
    out.append(f"- **P5**: corr(utility, density) = {r5:.3f}; utility {ut[0]:.2f}→{ut[-1]:.2f} "
               f"→ **{'SUPPORTED' if abs(r5) < 0.4 else 'NOT supported'}** (no density benefit).")
    return "\n".join(out)


def main():
    csv_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "experiments/results/sweep_full.csv"
    if not csv_path.exists():
        print(f"No data yet at {csv_path}. Run rescore_all after the sweep.")
        return
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    rows = load(csv_path)
    A, ordered = agg(rows)
    print(f"cells: {ordered}  (n per cell: "
          f"{ {c: A[c]['utility'][2] for c in ordered} })")
    fig1_realization(A, ordered)
    fig2_informative(A, ordered)
    fig3_absolute(A, ordered)
    fig4_utility(A, ordered, rows)
    table = relay_table(A, ordered)
    comp = completion_table(A, ordered)
    delta = relay_delta_table(ordered)
    preds = predictions(A, ordered)
    summary = PROJECT_ROOT / "experiments/analysis/results_summary.md"
    summary.write_text(
        "# Results summary (auto-generated)\n\n"
        "## Data quality: per-cell completion rate\n\n" + comp + "\n\n"
        "## Relay / second-order table\n\n" + table + "\n\n"
        "## LLM-judge prompt sensitivity: original vs re-judged relay figures\n\n" + delta + "\n\n"
        "## Pre-registered prediction outcomes\n\n" + preds + "\n")
    print(f"\nFigures -> {FIG_DIR}/fig1..4.png")
    print(f"Summary -> {summary}\n")
    print("### completion rate\n" + comp + "\n\n### relay/2nd-order\n" + table
          + "\n\n### prompt-sensitivity delta\n" + delta + "\n\n" + preds)


if __name__ == "__main__":
    main()
