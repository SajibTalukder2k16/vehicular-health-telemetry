# WifiLink Unit Validation

**Model:** `paperrebuild.links.WifiLink` — parametric 802.11 DCF link for an
intra-rig sensor connection. Per MSDU it fragments to `maxMsduPayload` and
spends one DCF cycle per fragment — `DIFS + backoff + T_data + SIFS + T_ack` —
with binary exponential backoff and retries. There is no delay knob and no
throughput knob; both emerge from the framing and timing parameters, which is
the bar `BleLink` was held to in [BLE_VALIDATION.md](BLE_VALIDATION.md).

**Harness:** `simulations/validation_wifi/` — one SensorSource → WifiLink →
DelaySink, 300 s × 10 seeds per config. Run date: 2026-11-05.
**Analyzer:** `tools/validate_wifi.py`, which recomputes the analytic target
from the same constants rather than comparing against a hard-coded number.

## Why this module exists

An indoor installation can attach its sensors over the wireless LAN instead of
over BLE or a cable. On capacity alone that is uninteresting: the whole rig
offers about 70 kb/s with the 4 KiB camera against tens of Mb/s available, so
a WLAN sensor link behaves like `WiredLink` and the wired arm already stands
in for it. The property that is *not* the wired arm renamed is that indoor
sensor traffic and indoor backhaul traffic share one medium and contend for
it. `mediumBusyFraction` is that term.

## Results

802.11a/g timings throughout: slot 9 µs, SIFS 16 µs, DIFS 34 µs, PHY header
20 µs, CWmin 15 (mean backoff 7.5 slots), MAC header + FCS 28 B, ACK 14 B.

| Config | Simulated (10 seeds) | Target | Error |
|---|---|---|---|
| `LatencyUnloaded` — 20 B, exclusive medium | 0.1676 ms | 0.1693 ms, one DCF cycle | −1.0% |
| `Throughput54_1500` — 1500 B, ACK 24 Mb/s | 30.882 Mb/s | 30.885 Mb/s analytic | −0.0% |
| `ThroughputNetSimRef` — 1450 B, ACK 6 Mb/s | 29.354 Mb/s | 29.358 analytic; **28.9 published** | −0.0% vs analytic, **+1.6% vs published** |
| `MediumBusy50` | 15.442 Mb/s | 15.443 Mb/s | −0.0% |
| `MediumBusy80` | 6.177 Mb/s | 6.177 Mb/s | −0.0% |
| `FER10` — 10% frame error rate | 27.155 Mb/s | below 0.88× error-free | 0.879× |

## What these numbers do and do not establish

**Read the 0.0% errors correctly.** The simulator implements the same cycle
arithmetic the "analytic target" column computes, so agreement there is a
*self-consistency* check, not an external validation. It is still worth
running — it is what would catch a fragmentation bug, a backoff off-by-one, or
a unit error — but it cannot confirm the model is a good description of
802.11.

**The one genuinely external anchor is `ThroughputNetSimRef`.** A published
worked example (one AP, one station, full queue, CWmin 15, 9 µs slot, 1518 B
frame, ACK at 6 Mb/s) reports ≈28.9 Mb/s UDP throughput for a 1450 B payload.
This model gives 29.35 Mb/s for the same configuration, +1.6%. That is one
reference, and it is a vendor tutorial rather than a peer-reviewed
measurement.

**Open item before this is cited in the paper.** The canonical analytic
reference is the IEEE 802.11 working-group contribution 802.11-01/055,
"802.11a and 11b max throughput for simulation model conformance" (Jan 2001),
which computes maximum DCF throughput from per-frame timing. It should be
retrieved and the table above checked against it before any claim rests on
this module in print. Until then, treat the external calibration as a single
weak anchor.

**`FER10` behaves as predicted and not merely as `0.9×`.** Naive reasoning
gives 0.9 × error-free = 27.80 Mb/s; the model gives 27.155, i.e. 0.879×,
because the contention window doubles on each failure and the extra backoff
costs air time on top of the retransmission itself. The gap in the right
direction is evidence the backoff state machine is live rather than decorative.

## The result that matters for the paper

| Config | mean sensor-link delay |
|---|---|
| `CameraOverWifi` — 4 KiB @ 2 Hz, exclusive medium | 1.10 ms |
| `CameraOverWifiBusy80` — same, medium 80% occupied | 5.52 ms |

The camera stream occupies about 0.2% of the link. Even with the backhaul
holding the medium 80% of the time, the sensor hop costs 5.5 ms against a 10 s
freshness budget. So at these payloads a WLAN sensor link is both
capacity-equivalent to the wired link **and** contention-tolerant, and the
indoor conclusion does not depend on which of the two is used.

This is a null result and is reported as one.

## QC

- Non-degenerate across seeds: every config's interval is non-zero.
- No delay exceeds simulation time.
- `mediumBusyFraction` halves throughput at 0.5 and gives one fifth at 0.8,
  which is the defining behaviour of the contention term; had it not, the
  parameter would be decorative.

Reproduce:
```sh
cd simulations/validation_wifi
opp_runall -j20 ../../src/out/clang-release/paperrebuild -u Cmdenv \
  -n ../../src:..:../../../inet4.7/src -c <Config>
python3 ../../tools/validate_wifi.py
```
