# `escalation_vec` — the pilot with per-escalation recording

The same 600 runs as `escalation_sr` (4 conditions x {no evidence, E1..E4} x 30
seeds, SR-corrected model), re-run 2026-11-10 with the two escalation latency
vectors recorded. This is the corpus the per-escalation frontier is computed
from: `docs/VERIFICATION_FRONTIER.md` §2.

## Why it exists

`escalation_sr` has `**.vector-recording = false`, so its `.vec` files hold
vector declarations and zero samples, and time-to-dispatch was only available as
`e2eDelayEvidence:max` -- a maximum over all escalations in a run. That
overstated typical dispatch delay by up to 40x. See the ordering warning at
the `vector-recording` block in `simulations/pilot/omnetpp.ini`: the specific
`vector-recording = true` keys
must precede the `**` catch-all or they are dead lines.

Scalars are unaffected: a run of this configuration against the `escalation_sr`
corpus differs only by the two new `config` lines, every measured value
identical.

## What is committed

| file | size | contents |
|---|---|---|
| `escalation_latencies.csv.gz` | **0.41 MB** | 57,140 rows: every `e2eDelayAlarm` and `e2eDelayEvidence` sample |
| `pilot_all.csv.gz` | **15 MB** | 3,364,877 values: every scalar, statistic field and histogram bin |
| `config_manifest.csv` | 1.2 MB | resolved `par`/`config` per condition and arm |
| raw corpus (NOT committed) | 956 MB | gitignored; regenerate per below |

`escalation_latencies.csv.gz` columns:

    condition,arm,seed,kind,recv_time,delay,creation

`kind` is `alarm` or `evidence`; `creation = recv_time - delay`. **An alarm's
creation stamp is its sensor creation time at the rig; an evidence chunk's is at
the edge, after `uniform(0.5ms, 2ms)` of processing.** The two therefore differ
by a median of 1.28 ms, which is why pairing needs a tolerance above 2 ms --
`tools/dispatch_times.py` carries the full warning.

## Both extracts are verified, not asserted

```sh
python3 tools/verify_extract.py simulations/pilot/results_escalation_vec \
                                analysis/escalation_vec/pilot_all.csv.gz
# OK: 3364877 values match exactly; 48600 histograms sum to their recorded count

python3 tools/dispatch_times.py analysis/escalation_vec/escalation_latencies.csv.gz
python3 tools/dispatch_times.py simulations/pilot/results_escalation_vec
# the two tables are identical
```

## Regenerating

```sh
cd ../../Simu5G && git apply ../PaperRebuild/patches/simu5g-scheduling-request.patch
cd src && make -j8                      # after `source $OMNETPP_ROOT/setenv`
cd ../../PaperRebuild
OUT_DIR=$PWD/simulations/pilot/results_escalation_vec tools/escalation_pilot.sh 8
python3 tools/extract_sca.py simulations/pilot/results_escalation_vec out.csv.gz
python3 tools/extract_vec.py simulations/pilot/results_escalation_vec lat.csv.gz
```

~11 s per run; 600 runs in about 15 minutes at 8 jobs on 24 cores.
Pinned: OMNeT++ 6.4.0, INET 4.7.0, Simu5G 1.4.4 + the patch. Seeds 0-29.
