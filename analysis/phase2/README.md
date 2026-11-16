# `phase2` — the E2' rung and the two deferral reversals

480 runs, 2026-11-10/11, by `tools/escalation_phase2.sh`. Four arms x four
conditions x 30 seeds, seeds matched to `escalation_vec` so every arm pairs
directly against that corpus at the same rung.

Result: `docs/PHASE2_RESULT.md`.

| arm | evidenceBytes | admissionPolicy | what it tests |
|---|---|---|---|
| `e2b` | 14,400 B | none | the waveform rung at W >= 120 s, which LF/HF needs |
| `e3` | 57,344 B | pace | that the inherited gate is a structural no-op below E4 |
| `e4` | 138,000 B | pace | C4.1: does temporal spreading now hurt? |
| `e4dp` | 138,000 B | dropPace | C4.2: is staleness discard still free? |

The gate keeps the mechanism layer's EXISTING settings (`cameraRate` 1 Mbps,
`cameraBurst` 65536 B, `cameraMaxAge` 2 s) rather than being retuned, because
RQ4 asks whether those rules transfer. The bucket arithmetic is why `e3/pace`
is in the arm set at all: 57,344 B < 65,536 B, so pacing cannot engage, and the
run exists to demonstrate that rather than assert it.

## What is committed

| file | size | contents |
|---|---|---|
| `escalation_latencies.csv.gz` | **0.55 MB** | 77,435 rows: every alarm and evidence delay sample |
| `pilot_all.csv.gz` | **12.6 MB** | 2,704,204 values: every scalar, statistic field, histogram bin |
| `config_manifest.csv` | | resolved `par`/`config` per condition and arm |
| raw corpus | 765 MB | gitignored |

## Verified, not asserted

```sh
python3 tools/verify_extract.py simulations/pilot/results_phase2 \
                                analysis/phase2/pilot_all.csv.gz
# OK: 2704204 values match exactly; 38880 histograms sum to their recorded count

python3 tools/dispatch_times.py analysis/phase2/escalation_latencies.csv.gz
# identical to the same tool run against the 480-run corpus
```

Pairing: 100% of escalations paired in all 16 cells, median creation offset
1.22-1.28 ms (the edge processing time -- see `tools/dispatch_times.py`).

## A measurement trap found here

`evidenceChunksDropped` reads **0** in every `dropPace` run even though the
server received only 45-47% of the evidence: that counter records buffer
refusals, not staleness discards. Score evidence policies on
`received_evidence / evidenceChunksEmitted`, not on the drop counter and not on
dispatch latency.
