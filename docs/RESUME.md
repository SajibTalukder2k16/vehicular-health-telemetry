# Where this is, and how to pick it up

Rewritten 2026-11-03. Branch `corrections-2026-10`. Everything described as
settled below is committed, so a reboot is safe.

## Nothing is in flight. Next step is the manuscript.

No campaign is running. The working tree is clean and every result below is
committed, so the machine can be powered off freely.

The next piece of work is the manuscript rewrite — framing is settled, the
headline is settled, and the load scoping that was blocking it is now done.
See "Open, in priority order" below.

## The loaded campaign is COMPLETE — and the headline survived

**490/490 runs, validated, zero failures**, in
`simulations/corridorpop/results_loaded/`. Every one verified genuinely loaded.
Finished 2026-11-03T17:27.

**Result: the margin over the per-seed oracle is +23.1 ± 18.7 pp unloaded
against +22.4 ± 11.2 pp loaded.** Matched-seed paired change: **−2.2 ± 16.0 pp,
interval spanning zero.** So the headline is not an artifact of an idle cell,
and no load-dependence direction can be claimed. Only c11 changes
significantly, and it narrows (−21.7 ± 14.0). Absolute timeliness falls on
every corridor and both streams, so the load is real and biting. Full writeup
in `docs/CORRIDOR_REGIME.md`; reproduce with `tools/analyze_load_effect.py`.

**Two traps recorded there, do not step in them:** c08 appears to swing +32.6 pp
but that compares 7 scorable seeds against 9 — matched, it is +22.3 ± 35.0,
not significant, so "the c08 caveat dissolves under load" is NOT a finding.
And c14 loses 9 of 10 seeds to unreachability, so nothing quantitative about
c14 under load is available.

## How this campaign was run, for next time

**Use `setsid`, not bare `nohup`.** The first launch died at 41/490 when the
session was torn down: `nohup` ignores SIGHUP but does not leave the process
group, so a group-wide signal still reaches it. `setsid` makes the runner a
session leader and it survived a second teardown cleanly. Verify with
`ps -o pid=,pgid=,sid= -p <pid>` — all three numbers should match.

Cost was ~10–14 h of compute at 20 slots, ~1.05 GB per run. My first estimate
of 4–5 h was wrong because it compared a solo loaded run against a solo
unloaded one; under 20-way concurrency the loaded runs contend for memory
bandwidth. Cost scales roughly with eNodeB count, so c08/c09/c10 dominate.

**Why this exists.** Until 2026-11-02 this project had no background traffic in
any run, at any setting. `startTimeUl` sat at its Simu5G default of `-1s` and
`TrafficGeneratorBase.cc:73` schedules a first transmission only
`if (startTime_[UL] >= 0.0)`, so every background UE ever instantiated —
across `corridorpop`, `pilot`, `dc_case` and `va_case` — sent exactly nothing.
`numBgUes` bound correctly and built 2 vs 20 modules, which is why it went
unnoticed: the modules existed and did nothing. Full diagnosis in
`docs/CORRECTIONS_2026-10.md` **C13**.

It was caught because the `bgues=2` campaign reproduced the `bgues=20` analysis
on *every line but the directory name*. Read on its own, that output looked
like a clean result.

**Three settings were missing, not one** (all now in
`simulations/corridorpop/omnetpp.ini`, committed):

| Setting | Why it matters |
|---|---|
| `generator.startTimeUl` | without it nothing is ever scheduled |
| `generator.typename` | default is the abstract `TrafficGeneratorBase` |
| `bgUE[*].mobility.initialX/Y` | a `BackgroundUe` has no position tied to its cell; unplaced it lands off-geometry and the RMa model aborts at `t=0` |

Placement is generated per corridor from each one's own tower coordinates by
`tools/gen_bgue_placement.py`, into an idempotent delimited block so it
survives regeneration by `opencellid_towers.py`. The radius is fixed at
±1000 m for every corridor on purpose — a density-derived radius would make a
background UE's path loss, and so the resource blocks it consumes, a function
of corridor geometry, confounding corridor with load in exactly the comparison
this study makes.

**Verified working end to end** on c08/aimd/seed 7: 1080 nonzero background
statistics where every archive previously read `count 0`, and the rig moves the
right way — timely vitals 96.73 → 95.39, timely camera 72.32 → 68.58, mean
admitted rate 838 → 796 kbps, backoffs 560 → 450.

**Pre-registration, scored honestly.** The expectation in the runner's header
was that the margin would "narrow but survive". Survive, yes. Narrow — not
established: −2.2 ± 16.0 pp. Half the prediction held and the interesting half
is unsupported.

Memory note if these are ever re-run: ~1.05 GB per run, 20.9 GB over 20 slots,
leaving only ~4 GB headroom. `validate_runs.py` warns that an OOM-killed run
leaves a file that still greps as complete, so lower
`tools/lib_campaign.sh:slots_for` rather than risk it on a busier machine.

## What the result directories mean

Easy to misread later, so stated plainly:

| Directory | Background load |
|---|---|
| `results_seeds10/` | **none** — carries the published headline |
| `results_lowload/` | **none** — ran before the fix, identical to the above |
| `results_targets/` | **none** |
| `results_loaded/` | **~2.5 Mbps/cell** — the only loaded data in the project |

## Settled, and safe to build on

- **Headline, 10 seeds, 490 validated runs** (`results_seeds10/`):
  **+34.8 ± 13.9 pp** timely camera at matched vitals against a per-corridor
  oracle static policy. Adversarial per-seed oracle: **+24.0 ± 16.0 pp**. Quote
  the first, cite the second.
- **The headline is load-robust** (`results_loaded/`, 490 validated runs):
  +22.4 ± 11.2 pp loaded against +23.1 ± 18.7 pp unloaded on the matched
  six-corridor set, matched-seed paired change −2.2 ± 16.0 pp. It is not an
  artifact of an idle cell. No load-dependence direction is claimable.
- The old "+24 to +48 pp" figure is **not comparable** and must not be quoted.
- **c10 is not a counterexample** — a 3-seed artifact, struck at 10 seeds. No
  corridor is dominated by any fixed rate.
- **c08 is the real caveat**: +0.2 ± 9.2 pp under the per-seed oracle.
- **The cross-stream signal confers no advantage.** Settled by the 560-run
  frontier sweep: with each arm tuned to its own best target, best achievable
  camera differs by **+0.7 ± 1.1 pp** and the sign reverses across corridors.
  The −7.2 pp gap at a shared target was a tuning artifact. What the signal
  choice changes is the *reachable* vitals range. See
  `docs/ABLATION_CROSS_STREAM.md`.
- **Framing is therefore settled**: (1) adaptive admission control beats tuned
  static configuration, (2) the queue-discipline mechanism finding — a freshness
  signal is usable only if the queue discards stale work, (3) signal source is a
  free design choice, with `aimdSelf` reported as the A³L-FEC baseline.
- Literature positioning is essentially cleared (`docs/RELATED_WORK.md`).

## Withdrawn — do not quote

- **"Background load is immaterial on real corridors"** (`CORRIDOR_REGIME.md`)
  and **Family A's 0.00 pp load effect**. Both true, both vacuous: no
  experiment could have returned anything else. A null forced by configuration
  is not evidence.
- **C12's "`numBgUes` does work"** (980/889/951 packets at 0/20/60 UEs). No
  background packet was sent at any of the three settings. The series is also
  non-monotonic, which is the shape of noise. The sentence built on it — "load
  matters once a cell is already near its limit" — has no support.
- **"The c08 caveat dissolves under load."** Tempting and unsupported: the
  apparent +32.6 pp swing compares 7 scorable seeds against 9. Matched to the
  6 common seeds it is +22.3 ± 35.0 pp. See `CORRIDOR_REGIME.md`.
- **Anything quantitative about c14 under load.** Nine of ten seeds have the
  controller's vitals above every static point, so the oracle has nothing to
  compare against and the corridor drops out of the test.
- The corridor-to-corridor spread *is* real (c08 97.5/35.0 vs c14 42.0/15.0 at
  a 400 kbps cap). It comes from site density, distance and handover, so the
  regime framing survives with contention removed from its explanation.

## Open, in priority order

1. **Manuscript rewrite.** Now unblocked: framing settled, headline settled,
   load scoping done. This is the next piece of work.
2. ~~No adversarial pass on the de-confounded Family A factorial or the
   population study.~~ **Both done 2026-11-04.** Neither conclusion was
   overturned; both had real errors in the reported numbers.
   - *Population study:* geospatial work is sound (correct per-anchor
     azimuthal-equidistant projection, adequate cell box) and every number
     reproduces. But each corridor is **centred** on its anchor tower, which
     *censors* both difficulty statistics — `max_m` cannot exceed 10 km,
     `frac_beyond_horizon` cannot exceed 0.30 — and c14 sits at both ceilings.
     Percentile labels were corrected (c14 is the 97th, not the 100th), the
     ">25% of drive" row was struck as a measurement of the ceiling, Wilson
     intervals added, and the population restated as corridors weighted by one
     operator's cell density rather than "US corridors". All biases run toward
     optimism, so the conclusions survive as conservative.
   - *De-confounding factorial:* campaign sound, but **none of the nine
     published point estimates reproduced** and all three processing-time
     effects had the wrong sign. The original pooled runs instead of blocking
     on seed, so the 28 pp camera-link split inflated the other factors'
     intervals ~2×. Conclusion unchanged and now better supported.
     `tools/analyze_deconf.py` regenerates the table.
3. ~~**FAIFO full text**~~ — **closed 2026-11-05, dropped not cited.** The
   manuscript never cited it and does not need to; the queue-discipline
   position is held by the LGFS paragraph, which cites a survey we read. See
   `RELATED_WORK.md`.
4. Optional: the `bgues=2` level could now be run *with* traffic for a genuine
   three-point load axis. Not needed for the current claims — the two-point
   comparison already shows load-robustness — so this is a strengthening move,
   not a gap.

## The repo cannot currently be pushed

`git push` to `origin` is **rejected by GitHub**, and not for the reason it
looks like. `analysis/vectors/*.csv` holds files of 111–127 MB committed as
plain git blobs: `.gitattributes` routes `*.sca`, `*.vec` and `*.vci` through
LFS but never `*.csv`, and GitHub hard-rejects any non-LFS file above 100 MB.
`--no-verify` does not help, because the problem is not LFS.

Separately, the branch has never been pushed at all (origin has only `main`)
and the local LFS store is ~95 GB against GitHub's 1 GB free allowance, so a
full push would exceed quota regardless.

Fixing it means rewriting history with `git filter-repo` to move those CSVs
into LFS or drop them, then force-pushing — invasive, and it should be a
deliberate decision, not something done in passing. Until then the branch lives
on this disk only. **It is committed and clean, so a reboot is safe; a disk
failure is not.**
