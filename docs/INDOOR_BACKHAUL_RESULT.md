# The indoor backhaul: WiFi and cellular, and what actually caused the failure

**450 runs, 2026-11-18.** Two new campaigns, both at the same five-rung
evidence ladder × 30 seeds as the vehicular pilot:

| campaign | driver | corpus | runs |
|---|---|---|---|
| camera on the WLAN | `tools/room_wifi_ladder.sh` | `simulations/room/results_room_wifi/` | 300 |
| edge on a cellular backhaul | `tools/indoor_lte_ladder.sh` | `simulations/pilot/results_indoor_lte/` | 150 |

Analysis for both, and for the earlier wired indoor control, is
`tools/analyze_room_ladder.py`; the significance tests are
`tools/compare_backhaul.py`.

---

## 1. Why these runs exist

`docs/ROOM_LADDER_RESULT.md` ran the indoor control with the camera on a
**wired** sensor link and a **WLAN** backhaul. It established that requiring
complete evidence is not intrinsically expensive, and then had to concede two
things:

1. **Three things differed at once** against the cellular campaign — access
   technology, competing traffic, and the observation window — so it localised
   the 16–49 % delivery failure to "the mobile cellular setting as a whole"
   and could not say which part caused it.
2. **The camera was on a cable**, which is the right *control* but not the
   realistic indoor installation.

These two campaigns address exactly those two gaps. The first puts the camera
on the wireless LAN. The second gives a stationary, unloaded indoor edge a
**cellular** backhaul, which closes the comparison grid:

| | WLAN backhaul | LTE backhaul |
|---|---|---|
| **stationary, no competing load** | `RoomMatched5GHz` | `CondIndoorLte` ← new |
| **mobile, with competing load** | — | `CondHealthy` … `CondOutage` |

`CondIndoorLte` vs `RoomMatched5GHz` differs **only in the backhaul**.
`CondIndoorLte` vs `CondHealthy` differs **only in mobility, load and
window**. Between them they separate what the indoor control could not.

---

## 2. The camera on the WLAN: C1's WLAN wall, measured

C1 derives an 802.11a/g DCF ceiling of **30.9 Mb/s** on a quiet medium and
**6.18 Mb/s** with the medium 80 % held by other stations, against a
PRV-grade camera at **25.5 Mb/s** (53,167 B at 60 fps). Those two ceilings
were derived from `src/links/WifiLink.ned`'s framing and timing parameters and
had **never been measured against a stream of that rate**. Now they have.

| | frames offered | dropped | drop rate | fluid prediction |
|---|---|---|---|---|
| quiet medium | 17,969 | **0** | 0.00 % | ~0 % (25.5 of 30.9 Mb/s) |
| medium 80 % busy | 17,969 | 13,647 | **75.95 %** | 75.8 % = 1 − 6.18/25.5 |

> **The derivation is right.** The quiet medium carries a PRV-grade stream
> with 21 % to spare and drops nothing at all. The busy medium drops three
> frames in four, within **0.2 percentage points** of the fluid estimate. The
> time-average queue sits at 46,772 B of a 65,536 B capacity — persistently
> backed up, not marginally so.

This is the C1 WLAN row promoted from derived to measured. It is also the
answer to "can the camera just use the WLAN indoors?": on a quiet medium yes,
on a contended one no, and the margin between those two cases is the whole
difference.

## 2b-pre. The camera on BLE

A third sensor link was run on 2026-11-18: the camera on Bluetooth, which is
C1's largest margin and the natural question given that the wearable is BLE in
every configuration. At PRV grade it drops **97.07 %** of frames; at 4 KiB and
10 fps it drops **none**. The shared-radio case has a cliff at one protocol
data unit, below which the wearable delivers nothing at all. Full results,
including the two predictions that were wrong, are in
**`docs/BLE_CAMERA_RESULT.md`**.

## 2a. The partition's isolation holds

`src/apps/EdgeApp.cc:657` implements the derived architecture by counting and
**deleting** each camera frame at the edge with no service cost, so raw frames
never reach the backhaul. If that is the truth of the model, saturating the
camera's own link must leave the escalation path untouched. It does:

| camera sensor link | completion, all rungs | E4 gap | E4 dispatch |
|---|---|---|---|
| wired | 100.0 % | 0.0350 | 0.0362 |
| WLAN, quiet | 100.0 % | 0.0350 | 0.0364 |
| WLAN, 80 % busy | 100.0 % | 0.0350 | 0.0364 |
| BLE, 97 % dropped | 100.0 % | 0.0350 | 0.0363 |

**Identical to four decimals**, while the camera link itself goes from zero
drops to losing 76 % of frames. The camera's cost is confined to its own
sensor link, which is the architectural claim, tested and not merely asserted.

## 2b. One apparent effect that was an artefact

The alert initially read **0.0013 s on the quiet medium and 0.0015 s on the
busy one**, consistently across all five rungs. A busy WLAN cannot physically
slow a BLE wearable, so this was chased down rather than reported.

`simulations/room/omnetpp.ini:27` puts `camLink` on **shared RNG stream 4,
together with the BLE wearable link and the edge service** — the ini's own
comment labels that group "rig links and edge service". At 80 % busy the
camera link makes vastly more backoff and retry draws, which advances the
shared stream and changes what the edge service draws.

Re-running both configurations with `camLink` on its own stream
(`--num-rngs=6 --**.rig.camLink.rng-0=5`) **reverses the sign**: 0.0015 s
quiet against 0.0012 s busy. Across four independent readings the alert
wanders over 0.0012–0.0015 s with no consistent direction, while the E4 gap
reads 0.0350 s every single time.

> **The alert difference is a common-random-number artefact and is not
> reported as a result.** The gap is unaffected by the perturbation, which is
> what makes §2a's null result safe to state.

⚠ **No published result is affected.** The hazard only activates when
`camLink` is a `WifiLink`, which is new in this campaign: `WiredLink` makes no
random draws at all (verified — zero RNG calls in `src/links/WiredLink.cc`),
and every previously published campaign runs the camera on a cable. The
shared-stream grouping in `simulations/pilot/omnetpp.ini:44-47` is latent
there, not active.

---

## 3. The cellular indoor backhaul: the decomposition

At E4 (138 kB of evidence). Gap medians in seconds, conditional on completion.
Both summaries are given because on cellular they diverge — see §3a.

| configuration | gap, pooled | gap, per-seed | completion |
|---|---|---|---|
| WLAN 5 GHz, stationary, no load | 0.0350 | 0.0349 | 100.0 % |
| **LTE, stationary, no load** | **0.0680** | **0.1320** | **91.4 %** |
| LTE, mobile, light load (`CondHealthy`) | 0.1920 | 0.2035 | 83.8 % |
| LTE, mobile, coverage outage (`CondOutage`) | 0.4020 | 0.4455 | 51.4 % |

Stepwise contrasts. Gap: Mann–Whitney U on per-seed medians, two-sided,
unpaired. Completion: Fisher's exact, two-sided.

| step | what it isolates | gap | p | completion | p |
|---|---|---|---|---|---|
| WLAN → LTE, both stationary & unloaded | the backhaul | ×3.78 | **1.5 × 10⁻⁷** | 100.0 → 91.4 % | 0.239 |
| LTE stationary → LTE mobile + loaded | mobility + contention | ×1.54 | 0.156 | 91.4 → 83.8 % | 0.480 |
| light load → coverage outage | losing coverage | ×2.19 | **0.045** | 83.8 → 51.4 % | **0.0009** |

> **This does not say what the paper's current framing implies.** The largest
> and by far the most significant step in the **gap** is moving from 802.11 to
> LTE *at all* — stationary, unloaded, in coverage. Mobility and moderate
> background load together are **not distinguishable** on either metric. The
> **completion** collapse is driven specifically by **losing coverage**, which
> is the only step that moves completion significantly.

So "the mobile uplink" was too coarse a diagnosis. The sharper one:

- the **evidence transfer cost** is dominated by the access technology;
- the **failure to deliver at all** is dominated by coverage holes;
- **mobility and moderate load**, on this corpus, add nothing resolvable.

The alert tells the same story in one number. It is **0.0013 s indoors on
WLAN against 0.0157 s indoors on LTE** — a 12× step for the backhaul alone —
and then **0.0161 s** on mobile loaded LTE, i.e. mobility and light load cost
the alert essentially nothing.

### 3a. Why two gap summaries, and which to trust

On the WLAN the pooled median (0.0350) and the median of per-seed medians
(0.0349) agree. On indoor LTE they differ by 2× (0.0680 against 0.1320). The
cause is a within-run selection effect, isolated:

| | 1 complete burst in the run | >1 complete burst | ratio |
|---|---|---|---|
| WLAN 5 GHz | 0.0350 s | 0.0350 s | 1.00× |
| indoor LTE | 0.1320 s | 0.0630 s | **2.10×** |

A run's **first** escalation is slower than the ones after it, on LTE only
(2.10×; the WLAN control is exactly flat). The natural reading is cold versus
warm uplink grant state — the first burst pays for acquiring a grant, later
ones reuse an active one. Pooling over-weights warm bursts; the per-seed
median over-weights cold ones.

> ⚠ **This mechanism is NOT established.** Mann–Whitney on first versus later
> gives **p = 0.262** (n = 18 against 14). The ratio is suggestive and the
> WLAN control is clean, but 30 seeds yielding ~1.2 escalations per run cannot
> resolve it. It is recorded as an open question, not a finding.

Both summaries are reported throughout. The headline WLAN→LTE contrast is
significant under either (×1.94 pooled, ×3.78 per-seed); the direction and
the significance do not depend on the choice.

---

## 4. Predictions, scored

### 4a. The WLAN camera (`tools/room_wifi_ladder.sh`)

| | prediction | outcome |
|---|---|---|
| **P1** | quiet medium fits, ~0 drops, ~13.8 ms/frame | ✔ **0 drops of 17,969** |
| **P2** | ≥ 70 % of frames dropped at 80 % busy | ✔ **75.95 %**, against a 75.8 % estimate |
| **P3** | completion unchanged at 100 % every rung | ✔ both configurations, every rung |
| **P4** | the E4 gap is unchanged | ✔ **0.0350 s** in all three sensor-link cases |

Four for four. P4 was written as the one most likely to embarrass the
architecture; it did not, and §2b explains why the one apparent exception was
not real.

### 4b. The cellular indoor backhaul (`tools/indoor_lte_ladder.sh`)

| | prediction | outcome |
|---|---|---|
| **P1** | E4 completion above 95 % | ✘ **91.4 %** — right in direction, below the bar I set |
| **P2** | E4 gap between 0.0350 s and 0.1920 s, nearer the WLAN end | ✔ on the pooled reading (**0.0680**); ✘ on the per-seed reading (0.1320 is nearer the cellular end) |
| **P3** | E1–E3 completion at or near 100 % | ✘ **100 / 97.1 / 94.3 %** — E3 misses |
| **P4** | the alert is flat, not falling | ✔ **0.0157 s flat** across all five rungs |

**Two wrong, one half-right, one right.** Taking them in turn:

- **P1.** 91.4 % is not above 95 %, so the prediction fails as written. But the
  shortfall against the WLAN's 100 % is **not significant** (p = 0.239), so
  the opposite claim — that an LTE backhaul costs completion — is *also* not
  supportable. The honest statement is that this corpus cannot tell 91.4 %
  from 100 %.
- **P3.** Same arithmetic: 94.3 % at E3 is 2 lost bursts out of 35.
- **P4 is the informative one**, and it forces a correction to a published
  document. See §5.

---

## 5. A correction to `docs/ROOM_LADDER_RESULT.md`

That document's §4 states, of the wired indoor control:

> *"the alert is perfectly flat at 1.3 ms across the whole ladder, where on
> cellular it falls as evidence grows. The 'alert gets faster' effect is
> therefore specific to cellular grant acquisition."*

P4 predicted the alert would be flat on indoor LTE, which would make that
attribution wrong. It is flat (0.0157 s at every rung). Checking the alert
across all four cellular conditions shows the attribution was never
supportable:

| condition | ref | E1 | E2 | E3 | E4 |
|---|---|---|---|---|---|
| CondHealthy | 0.0161 | 0.0159 | 0.0160 | 0.0161 | 0.0161 |
| CondCongested | 0.0242 | 0.0175 | 0.0176 | 0.0201 | 0.0207 |
| CondTransient | 0.0319 | 0.0215 | 0.0220 | 0.0220 | 0.0203 |
| CondOutage | 1.0071 | 0.8285 | 0.4039 | 0.1376 | 0.3704 |

> **"On cellular the alert falls as evidence grows" is an overstatement.**
> Across E1→E4 the alert is flat in `CondHealthy`, and varies by a few
> milliseconds without a clear trend in `CondCongested` and `CondTransient`.
> The large fall is **`CondOutage` only** — and it is not even monotone there
> (0.1376 s at E3, back up to 0.3704 s at E4). The remaining systematic piece
> is a **ref→E1 step** in three conditions, which is a different effect from
> "falls as evidence grows".

The effect is therefore a **coverage-outage phenomenon**, not a general
property of cellular grant acquisition. `ROOM_LADDER_RESULT.md` §4 has been
amended accordingly, and nothing in the paper claimed the broader version.

---

## 6. What these runs resolve, and what they do not

**Resolved** — the two caveats `ROOM_LADDER_RESULT.md` §5 had to carry:

- **§5 caveat 4** ("the camera is on a wired sensor link here;
  `RoomWifiCam*` was not run with the ladder") — now run; §2.
- **§5 caveat 1** ("WLAN against LTE confounds access technology with mobility
  and coverage") — now decomposed; §3. Mobility, load and window are matched
  across the WLAN→LTE step.

**Not resolved.**

1. **The WLAN→LTE step is not a pure access-technology contrast.** It still
   compares two *networks*: `RoomNet` (802.11 DCF, AP, Eth1G to the server)
   against `CorridorNet` (URBAN_MACROCELL, eNB, PPP backbone). Mobility, load
   and window are matched; the channel model and the wired path behind the
   access link are not. It is a much tighter contrast than before, not a
   clean one.
2. **Step 2's non-significance is a failure to detect, not evidence of no
   effect.** With 18 and 20 seed medians a 1.54× difference is simply not
   resolvable. Nothing here licenses "mobility and load do not matter".
3. **Thin cells.** 35 bursts per indoor cell; 37 and 72 for the cellular
   cells. Enough for the 100 %/51 % contrast, not for fine comparison — which
   is exactly what §4b's P1 and P3 ran into.
4. **The cold/warm grant mechanism of §3a is unestablished** (p = 0.262).
5. **One room geometry and one parked position.** The indoor LTE edge sits
   100 m from eNodeB[0]; see §7.
6. **`mediumBusyFraction` is a parametric stand-in** for competing stations,
   not a simulated contending population.

---

## 7. Provenance, and two silent failures worth recording

```sh
sh tools/room_wifi_ladder.sh                  # 300 runs, ~17 s on 12 jobs
sh tools/indoor_lte_ladder.sh                 # 150 runs, ~43 s on 12 jobs
python3 -I tools/analyze_room_ladder.py simulations/room/results_room_wifi
python3 -I tools/analyze_room_ladder.py simulations/pilot/results_indoor_lte
python3 -I tools/compare_backhaul.py \
    simulations/room/results_room_ladder RoomMatched5GHz \
    simulations/pilot/results_indoor_lte CondIndoorLte --arm e4
```

`tools/analyze_room_ladder.py` is new and exists because
`ROOM_LADDER_RESULT.md` was produced by an inline analysis whose provenance
section could name only the driver. It was **validated by reproducing that
document's published tables exactly** — 100 % completion in both bands and E4
gaps of 0.0464 and 0.0350 s — before being used on anything new.

Two failures that completed successfully and produced nothing:

1. **`StationaryMobility` delivers zero packets.** It leaves the UE's position
   unknown to Simu5G's channel model, so the UE never gets a CQI, never gets
   an uplink grant, and `server.udp packetReceived` is **0** — while the run
   reports success. The indoor LTE arm therefore keeps `BonnMotionMobility`
   and reads a trace that does not move, so the mobility module and the entire
   attach path stay identical to the cellular campaign's.
2. **Where the UE is parked is a real choice.** Parking it at the mobile
   trace's own t = 0 point, (5.1, −1.6), *also* delivered zero: that point is
   495 m from eNodeB[0] at the corridor's edge and out of coverage. The mobile
   UE delivers because it **drives into** coverage. A distance sweep settles
   it (packets received at the server, `CondHealthy`, 300 s, seed 0):

   | distance from eNodeB[0] | 0 m | 50 m | 100 m | 200 m | 300 m |
   |---|---|---|---|---|---|
   | packets received | 1067 | 1067 | 1037 | 1045 | 1068 |

   Coverage is solid across the range, and every one of them beats the mobile
   arm's 653. **100 m** was chosen: realistic for an indoor device on an
   outdoor macro, and not an unrealistically perfect 0 m.

Both are recorded because each one produced a complete, clean, empty run — the
same failure mode as the room network's `cloud`/`server` naming mismatch, and
the third instance of it in this project.

---

## 8. Corrections from external review, 2026-11-18 (second round)

A review of this work reproduced the E4 gap medians (35 ms WLAN, 68 ms
stationary LTE) and the 3.78 per-seed ratio, and raised six points. **All six
were verified and all six were right.** What changed:

### 8a. The attribution to coverage loss is withdrawn

§3 read "the completion collapse is driven specifically by losing coverage
(p = 0.0009)". The difference is real and significant, but `CondHealthy` and
`CondOutage` differ in **five** respects at once:

| | Healthy | Outage |
|---|---|---|
| sites, spacing | 6 at 1 km | 2 at 16 km |
| propagation setting | urban | rural |
| background UEs | 4 | 8 |
| camera payload | 4 KiB | 60 KiB |
| observation window | 320 s | 680 s |

No experiment in this project varies coverage alone. **The difference is
reported; the attribution is not.** Only the WLAN→LTE step isolates a single
factor.

### 8b. ~~The camera payload was NOT matched~~ — **THIS CORRECTION WAS WRONG**

> ⚠ **RETRACTED 2026-11-18, same day.** This section accepted the reviewer's
> point that the indoor campaigns ran a 53,167 B camera against 4 KiB/60 KiB
> in the cellular corpus. **That is false, and so was the §8b correction.**
> The 120-seed validator caught it: a `CondHealthy` arm run at the ini's
> 4 KiB gave 25/12 complete/lost where the published cell is 31/6.
>
> The error came from trusting `analysis/escalation_vec/config_manifest.csv`,
> which records `4KiB`. **A `.sca` carries two `config` lines for an
> overridden parameter** — the command-line value and the ini value — and the
> manifest extraction kept the ini one. The authoritative record is the `par`
> line, which gives the effective value:
>
> ```
> par CorridorNet.rig.camera messageLength 53167B
> ```
>
> verified for **all four conditions in both the ladder and the gate
> corpora**. Every campaign driver overrides `messageLength`, so the
> per-condition 4 KiB/60 KiB sizes in the ini are never in force.
>
> **The payload was always matched at 53,167 B and 60 fps.** The reviewer's
> point 2 is withdrawn, the 4 KiB arm is a payload *sensitivity* check rather
> than a confound correction, and two passages in the paper that described
> per-condition camera loads of 1.97 and 29.5 Mb/s were wrong and are fixed —
> as was the same claim about the edge-cost campaign, which also runs
> 53,167 B.
>
> **The lesson is about evidence, not arithmetic.** I confirmed a reviewer's
> claim from a derived summary rather than from the corpus, having already
> written down in this project that a secondary summary is not a source. The
> `par` line was one grep away.
>
> What remains true from the original §8b: the measurement it prompted. Run
> at 4 KiB, the indoor cellular arm gives an identical alert and E4 gap and
> completion within one burst, so payload does not reach the verification
> path. That was worth measuring and stands on its own.

### 8c. `compare_backhaul.py` applied one horizon to both inputs

A real bug, and a silent one. The censoring test is
`creation + t_obs > horizon`; forcing the indoor 300 s onto `CondOutage`,
which ran to 680 s, reclassified genuine losses as censored and dropped them
from the denominator — **37/72 became 37/43 and Fisher's p went from 0.000882
to 1.000.** It would have erased the one completion effect in the table.

The published p = 0.0009 was *not* affected: it came from an inline analysis
that left the cellular conditions' own horizons in place, and the reviewer
independently reproduced 0.000882. But the shipped tool would not have
reproduced it. It now takes the condition's own `completion.HORIZON` entry
when it has one and 300 s otherwise, with `--horizon-a`/`--horizon-b`
overriding per input rather than jointly.

### 8d. Completion tests now also cluster by run

Fisher's exact on pooled escalations assumes each is independent. They are
not: escalations from one run share a mobility trace, a radio realisation and
a background-load draw, so pooling overstates the effective sample size and
the p-value is anti-conservative. Every completion contrast is now also tested
on per-run completion fractions:

| step | pooled p | clustered p |
|---|---|---|
| WLAN → LTE | 0.239 | 0.081 |
| LTE still → LTE mobile+loaded | 0.480 | 0.548 |
| light load → outage | 0.0009 | **0.0008** |

**No conclusion changes.** The outage difference survives clustering.

### 8e. "Delivered" was an estimate; it is now measured

`indoor_sensor_links.py` computed delivered rate as
`offered × (1 − dropped/sent)`, which counts a frame undropped but still
queued at termination as delivered. `linkDelay` fires only on transmission
completion, so its count is the true delivered figure. Both are now reported:

| arm | accepted (estimate) | delivered (measured) |
|---|---|---|
| WLAN quiet | 25.520 | **25.475** |
| WLAN 80 % busy | 6.138 | **6.125** |
| BLE, PRV grade | 0.747 | **0.744** |
| BLE, 4 KiB @ 30 fps | 0.765 | **0.762** |

The estimate was high by ≤ 0.06 % — the distinction is methodologically right
and numerically small here. It also recovers the per-frame link delay, which
the earlier table reported as `nan`: **13.86 ms** on the quiet WLAN, against
13.8 ms derived.

### 8f. Numbers and labels fixed in the paper

- the gate sweep's **128 KiB row collapsed three refill rates into "any"**,
  and they differ: at 1 Mb/s completion is 89.2/71.0/69.0/56.2, at 16 Mb/s it
  equals the baseline exactly. Two of that row's completion figures matched no
  arm at all. Split into three rows; the 256 KiB control likewise.
- **Congested E2 deadline success 90.2 % → 89.5 %** (128/143). Independently
  recomputed from the definition in the table's own caption; every other cell
  in that table was correct.
- completion percentages in the sweep table now carry **one decimal**, the
  paper's convention elsewhere: `(60)` was 59.5, and `87 % against 84 %` was
  86.5 % against 83.8 %.
- **6.6 GB → 7.6 GB** of raw output; "three indoor campaigns" → five.
- the indoor table now shows **counts and names its denominator** (observed
  bursts, not emitted — the ladder extract has no emission counter).
- the 8.23 % BLE threshold is now **scoped** to this model's 30 ms interval,
  1 Mb/s PHY and 251 B data units. What generalises is that the floor is one
  PDU, not a share of bandwidth.

---

## 9. 120 seeds: both undetected steps resolve, and one conjecture dies

**3,000 runs, 2026-11-18.** Driver `tools/indoor_power120.sh`, validator
`tools/verify_power120.py`, corpora `results_{indoor_lte,indoor_lte_4k,healthy,
outage}_120/` and `results_room5g_120/`. Five arms × five rungs × 120 seeds.

§3 reported two contrasts as failures to detect, on 18–20 per-seed medians per
cell. Quadrupling the seeds settles both — and overturns a third result that
*had* looked solid.

### 9a. Validation first

Seeds 0–29 are the same seed-sets the published corpora used, so they must
reproduce the published cells exactly. All five arms do, to the precision
published:

| arm | seeds 0–29 | published |
|---|---|---|
| `indoor_lte` | 32/3, .0680, .1320 | 32/3, .0680, .1320 |
| `indoor_lte_4k` | 31/4, .0680, .1320 | 31/4, .0680 |
| `healthy` | 31/6, .1920, .2035 | 31/6, .1920, .2035 |
| `room5g` | 35/0, .0350, .0349 | 35/0, .0350, .0349 |
| `outage` | 37/35, .4020, .4455 | 37/35, .4020, .4455 |

**The validator earned itself immediately.** `healthy` failed on the first
attempt — 25/12 against a published 31/6 — because the driver left
`CondHealthy` at the ini's 4 KiB camera. That is how §8b's error was found;
see the retraction there.

### 9b. The result: three comparable steps, all significant

| configuration | gap (per-seed) | ×  | gap $p$ | completion | compl. $p$ |
|---|---|---|---|---|---|
| WLAN 5 GHz, still, no load | .0349 | — | — | 111/111 (100 %) | — |
| LTE, still, no load | .0910 | 2.61 | 2e-16 | 99/111 (89.2 %) | .0006 |
| LTE, mobile, light load | .1895 | 2.08 | .0013 | 88/117 (75.2 %) | .015 |
| LTE, mobile, outage | .4850 | 2.56 | 7e-06 | 123/242 (50.8 %) | 2e-05 |

Completion $p$ is clustered by run. The three factors compound to
**13.9×**, which is what the end points give directly (0.4850/0.0349).

> **At 30 seeds the story was "the backhaul dominates" (3.78× against a
> non-significant 1.54×). That was wrong.** The factors are alike, and the
> earlier reading was an artefact of an unstable per-seed median — 0.1320 s
> for the stationary cellular arm at 30 seeds against 0.0910 s at 120.

### 9c. The cold/warm grant conjecture is withdrawn

§3a offered cold-versus-warm uplink grant state to explain a twofold
pooled/per-seed divergence, at 2.10× and p = 0.262, explicitly unclaimed.

| | 30 seeds | 120 seeds |
|---|---|---|
| pooled vs per-seed divergence | 1.94× | **1.10×** |
| first vs later escalation | 2.10× | **1.33×** |
| $p$ | 0.262 | **0.311** |

**The effect weakened as the data grew** and the divergence that motivated it
largely vanished. That is the signature of a small-sample artefact, not a
mechanism. Withdrawn. `tools/grant_warmup.py` is the test, and it reproduces
the published 30-seed figures before being run at 120.

### 9d. Predictions, scored

| | prediction | outcome |
|---|---|---|
| **P1** | seeds 0–29 reproduce the published cells | ✔ all five, after the driver bug was fixed |
| **P2** | Q1 (mobility+load gap) becomes significant, p ≈ .005 | ✔ **p = .0013**, ×2.08 |
| **P3** | Q2 (cold/warm) becomes marginally significant | ✘ **weakened**: ×1.33, p = .311 |
| **P4** | Q3 (backhaul completion) becomes significant | ✔ **clustered p = .0006** |
| **P5** | point estimates barely move (1.3–1.8× and 1.8–2.4×) | ✘ **moved materially**: step 1 3.78→2.61, step 2 1.54→2.08 |

**Three of five.** P5 is the one that mattered: it was written as the
prediction most likely to embarrass the published tables, and it did.

### 9e. What 120 seeds does not fix

Power is not validity. Step 2 still changes mobility, load and window
together; step 3 changes site count and spacing, propagation, load and window
together. **The withdrawn attribution of §8a stays withdrawn** — nothing here
varies coverage alone, and a significant difference is still not an attributed
cause.
