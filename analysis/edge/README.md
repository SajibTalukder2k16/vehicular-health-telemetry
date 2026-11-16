# `analysis/edge/` — the M4 edge-cost sensitivity corpus, as a verified extract

**960 runs, 2026-11-11.** Produced by `tools/edge_sensitivity.sh`; result
written up in `docs/EDGE_COST_RESULT.md`.

The raw corpus (`simulations/pilot/results_edge/`, **1.5 GB**) is *not* tracked —
see the note in `.gitignore`. These three files are, and they are sufficient to
reproduce every number in the write-up.

| file | size | contents |
|---|---|---|
| `pilot_all.csv.gz` | 24 MB | every scalar, every statistic field, every histogram bin: 5,356,040 values |
| `escalation_latencies.csv.gz` | 1.2 MB | the per-escalation alert/evidence samples: 171,853 rows |
| `config_manifest.csv` | 1.9 MB | the `par` and `config` lines, i.e. what each run was actually told to do |

## Faithfulness is proven, not asserted

`tools/verify_extract.py` streams the corpus and the extract in the same order,
compares **every value as text**, and independently checks that each histogram's
bins sum to its recorded count:

```
OK: 5356040 values match exactly; 77760 histograms sum to their recorded count
```

And the committed extract reproduces the headline table **identically** to the
1.5 GB corpus — verified by diffing the two outputs:

```sh
python3 -I tools/dispatch_times.py analysis/edge/escalation_latencies.csv.gz \
        --report-pairing --tol 1.0
python3 -I tools/edge_contrasts.py
```

## `--tol 1.0` is required, not optional

The default 10 ms window is **wrong for this corpus**. The alert/evidence
creation offset *is* the edge latency, so here it reaches **0.451 s** rather than
1.28 ms. Too small a window leaves escalations unpaired, and an unpaired
escalation silently collapses dispatch onto the alert — which erases the whole
effect and has produced a wrong table once before. Too large a window crosses
the **1.1692 s** minimum inter-escalation spacing. 1.0 s sits between them.
Read `--report-pairing` before the table, every time.

## The eight arms

`label:evidenceBytes:processingTime:cameraInterval`

| arm | rung | edge | fps | note |
|---|---|---|---|---|
| `e2bB30` | 14.4 kB | `uniform(0.5ms,2ms)` | 30 | matched baseline for `e2bPC30` |
| `e2bPC30` | 14.4 kB | 22.73 ms | 30 | **the reportable configuration** — inference fits |
| `e2bPC` | 14.4 kB | 22.73 ms | 60 | edge saturated, ρ = 1.40 |
| `e2bEMB` | 14.4 kB | 94.27 ms | 60 | edge saturated, ρ = 5.80 |
| `e4B30` | 138 kB | `uniform(0.5ms,2ms)` | 30 | matched baseline for `e4PC30` |
| `e4PC30` | 138 kB | 22.73 ms | 30 | |
| `e4PC` | 138 kB | 22.73 ms | 60 | |
| `e4EMB` | 138 kB | 94.27 ms | 60 | |

The 60 fps arms' free-edge baselines are **not in this directory**: they are
`e2b` in `analysis/phase2/` and `e4` in `analysis/escalation_vec/`, at the same
seeds. `tools/edge_contrasts.py` wires all three together, because comparing a
60 fps arm against a 30 fps one reads *backwards* — see `EDGE_COST_RESULT.md`
§5.1.
