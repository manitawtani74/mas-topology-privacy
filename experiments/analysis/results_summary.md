# Results summary (auto-generated)

## Data quality: per-cell completion rate

| cell | n | completion rate | mean utility |
|---|---|---|---|
| path | 30 | 1.00 | 0.71 |
| star | 30 | 0.97 | 0.70 |
| ER .25 | 30 | 0.90 | 0.70 |
| ER .50 | 30 | 0.90 | 0.68 |
| ring | 30 | 0.97 | 0.67 |
| ER .75 | 30 | 1.00 | 0.66 |
| complete | 30 | 1.00 | 0.71 |

## Relay / second-order table

| cell | realization_relay(P) | 2nd-excl(P) | 2nd-any(P) | 2nd-excl(S) | redundant |
|---|---|---|---|---|---|
| path | 0.45 | 4.60 | 6.40 | 6.80 | 12.43 |
| star | 0.40 | 0.67 | 4.50 | 2.43 | 13.60 |
| ER .25 | 0.46 | 4.30 | 7.13 | 6.43 | 13.47 |
| ER .50 | 0.52 | 4.20 | 9.83 | 6.27 | 15.83 |
| ring | 0.55 | 4.17 | 6.30 | 6.93 | 16.00 |
| ER .75 | 0.63 | 4.83 | 14.00 | 6.83 | 17.63 |
| complete | 0.99 | 0.00 | 31.20 | 0.00 | 25.73 |

## LLM-judge prompt sensitivity: original vs re-judged relay figures

| cell | leaked_perm (orig→new, Δ) | 2nd-order-any perm (orig→new, Δ) |
|---|---|---|
| path | 38.1→41.0 (Δ+2.9) | 2.0→6.4 (Δ+4.4) |
| star | 36.6→36.7 (Δ+0.1) | 1.4→4.5 (Δ+3.1) |
| ER .25 | 39.6→42.0 (Δ+2.4) | 2.7→7.1 (Δ+4.5) |
| ER .50 | 45.0→47.5 (Δ+2.6) | 4.2→9.8 (Δ+5.6) |
| ring | 47.7→49.7 (Δ+2.0) | 3.0→6.3 (Δ+3.3) |
| ER .75 | 55.6→57.1 (Δ+1.6) | 8.4→14.0 (Δ+5.6) |
| complete | 90.7→90.2 (Δ-0.5) | 19.6→31.2 (Δ+11.6) |

## Pre-registered prediction outcomes

## Pre-registered prediction outcomes

- **P1** (permissive): realization 0.99–1.12 (span 0.13).
- **P1** (strict): realization 0.99–1.15 (span 0.16).
  → **SUPPORTED** (flat ⇒ topology-invariant).
- **P2**: corr(leaked_strict, reachable_pairs) = 0.994 → **SUPPORTED** (mechanical).
- **P3**: corr(fraction_informative, density) = 0.678; 0.75 (sparsest) → 0.76 (densest). Predicted NEGATIVE; got POSITIVE/flat → **NOT supported** (fraction is topology-invariant).
- **P4**: 2nd-order-excl(perm) — path 4.60, star 0.67, complete 0.00. Effect REAL but **MECHANISM CORRECTED**: star (sparse) ≈ 0 disproves the density framing → structural (distinct-intermediary count).
- **P5**: corr(utility, density) = 0.121; utility 0.71→0.71 → **SUPPORTED** (no density benefit).
