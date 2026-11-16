# `analysis/gate/` — the C4 confirmation sweep, as a verified extract

**2,160 runs, 2026-11-12/13.** Produced by `tools/gate_sweep.sh`, with the 600
`dropPace` arms re-run by `tools/gate_dp_rerun.sh` after the staleness fix.
Result: `docs/GATE_SWEEP_RESULT.md`. Derivation under test:
`docs/GATE_DERIVATION.md`.

The raw corpus (`simulations/pilot/results_gate/`, **3.4 GB**) is not tracked.
These three files are, and reproduce every number in the write-up.

| file | size | contents |
|---|---|---|
| `pilot_all.csv.gz` | 55 MB | every scalar, statistic field and histogram bin: 12,192,061 values |
| `escalation_latencies.csv.gz` | 4.4 MB | per-escalation alert/evidence samples: 684,035 rows |
| `config_manifest.csv` | 4.2 MB | the `par` and `config` lines — what each run was actually told to do |

Verified value-by-value by `tools/verify_extract.py`:

```
OK: 12192061 values match exactly; 174960 histograms sum to their recorded count
```

## The 18 arms

Twelve `pace` arms sweep the bucket against the fill rate; five `dropPace` arms
sweep the staleness horizon; one `none` arm is the **internal baseline**, so
every contrast is within this corpus at matched seeds. All at E4 = 138,000 B,
which Proposition 1 derives to be the only rung that engages the gate.

| arm | `cameraBurst` | `cameraRate` | note |
|---|---|---|---|
| `p16k1` … `p16k16` | 16 KiB | 1 / 4 / 16 Mbps | |
| `p64k1` … `p64k16` | 64 KiB | 1 / 4 / 16 Mbps | **the inherited gate** |
| `p128k1` … `p128k16` | 128 KiB | 1 / 4 / 16 Mbps | barely engages (6,928 B) |
| `p256k1` … `p256k16` | 256 KiB | 1 / 4 / 16 Mbps | **positive control**: `b > B`, must be a no-op |
| `dp05` … `dp8` | 64 KiB | 1 Mbps | `cameraMaxAge` 0.5 / 1 / 2 / 4 / 8 s |
| `none` | — | — | gate bypassed; baseline for all of the above |

## Two traps this corpus was built to avoid

1. **The camera rate must be set explicitly.** The ini default is 2 Hz, the
   original rate from before C1 revised it to 60 fps. The first run of this
   sweep omitted `sendInterval` and produced 3.53 pkt/s through the edge where
   every other corpus has 61.53 — not comparable, and invisible in the dispatch
   table because the camera terminates at the edge. Those 2,040 runs were
   discarded. Check `packetsForwarded` against another corpus.
2. **The baseline must be internal.** It was the cross-corpus dependency on
   Gate A's `e4` arm that let trap 1 go unnoticed. Hence the `none` arm here.
