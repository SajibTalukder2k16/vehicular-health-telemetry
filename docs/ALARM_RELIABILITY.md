# Alarm reliability, and what the controller costs it

Added 2026-10-27. Data: `simulations/pilot/results_alarm/`.

## Why a separate study was needed

Alarms are the safety-critical class, but at the design rate —
`exponential(300 s)` — a drive yields about three, so the whole corpus gave
50–98 per configuration and Wilson intervals 12–20 pp wide. No alarm claim was
supportable from the primary runs.

This uses the high-rate protocol: alarm interval raised tenfold purely for
statistical exposure, with generation stopped one 5 s budget before the cutoff
so no alarm is censored by the end of the run. The raised rate is a sampling
device, not a claim about how often patients raise alarms.

## Results — 10 seeds pooled per cell

| Condition | Policy | generated | received | late | timely | 95% CI | width |
|---|---|---|---|---|---|---|---|
| Congested | dropPace | 475 | 457 | 29 | **90.1%** | [87.1, 92.5] | 5.4 |
| Congested | aimd | 475 | 455 | 48 | **85.7%** | [82.2, 88.5] | 6.3 |
| Transient | dropPace | 475 | 447 | 50 | 83.6% | [80.0, 86.6] | 6.7 |
| Transient | aimd | 475 | 465 | 69 | 83.4% | [79.8, 86.4] | 6.7 |
| Outage | dropPace | 243 | 195 | 54 | 58.0% | [51.7, 64.1] | 12.3 |
| Outage | aimd | 243 | 209 | 78 | 53.9% | [47.6, 60.1] | 12.4 |

Intervals are 5.4–6.7 pp where the drive is long, against 12–20 pp at the
design rate. The outage condition stays wide at 12.3 pp because its drive is
680 s rather than 1369 s, so it carries half the alarms.

## Two findings, both uncomfortable

**1. The controller costs alarm timeliness.** AIMD is worse than the static
cap in all three conditions: −4.4 pp (Congested), −0.2 pp (Transient),
−4.1 pp (Outage). Only the Congested gap approaches significance — the
intervals overlap only over [87.1, 88.5] — and the other two are well within
noise. But the sign is consistent across all three.

The mechanism is straightforward and was predictable: alarms are never gated
by any policy, but AIMD admits far more camera traffic (74% against 35% timely
camera in Congested), and that traffic still occupies the radio. Alarms queue
behind it. **The controller's camera gains are paid for partly in alarm
latency**, which for a mixed-criticality system is exactly the trade a reviewer
should be told about rather than left to infer.

**2. Alarms are not well served by any policy here.** Even the conservative
static cap reaches only 90.1% in Congested, 83.6% in Transient and 58.0% in
Outage. Roughly one alarm in ten misses its 5 s budget in the mildest of these
conditions, and more than four in ten during an outage.

That is a limitation of the architecture under these conditions, not of either
policy, and it bears on the clinical framing: a system that loses 10–40% of
safety-critical alerts is not one to describe as meeting an alarm deadline.
The honest statement is that alarm delivery degrades with the same coverage
and contention pressure as everything else, and that no admission policy
rescues it — an alarm cannot be delivered over a link that is not there.

## What would change this

Alarms are tiny (128 B) and rare. Nothing in the current design gives them
priority *within* the radio, only at the gateway, where they already bypass
every queue. Carrying them on a separate bearer with its own QoS class, or
retransmitting until acknowledged, are the obvious directions — and both are
outside what the gateway alone can do, which is itself worth saying.

## Limitations

The raised alarm rate changes the offered load slightly, so these numbers are
not directly comparable with the primary runs' alarm figures; they are for
comparing policies against each other under identical conditions. Three
conditions only, and the outage interval remains wide.
