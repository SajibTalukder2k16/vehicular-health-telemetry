# Local patches to Simu5G 1.4.4

Three defects were found and patched in our local Simu5G checkout
(`Thesis/Simu5G`, tag v1.4.4) while building the Family A corridor scenarios.
All three are candidates for an upstream issue/PR to Unipisa/Simu5G.
Keep this file in sync with the checkout; re-apply if Simu5G is re-cloned.

## P1 — RMa/SMa LOS path loss uses Hz instead of GHz (results-affecting bug)

**File:** `src/simu5g/stack/phy/channelmodel/LteRealisticChannelModel.cc`,
`computeRuralMacro()` and `computeSubUrbanMacro()`, LOS branches (4 sites).

The 3GPP TR 36.814 LOS formula `PL = 20·log10(40π·d·fc/3) + …` expects the
carrier frequency **in GHz**. The code multiplied by `carrierFrequencyHz_`
(Hz), overstating path loss by 20·log10(1e9) = **180 dB**, which silently
kills every RURAL_MACROCELL / SUBURBAN_MACROCELL LOS link (zero CQI, zero
delivery, no error message). The NLOS branches correctly use
`log10CarrierFrequencyGHz_` — only LOS was wrong.

**Fix:** replaced `carrierFrequencyHz_` with `(carrierFrequencyHz_ / 1e9)` in
the four `40 * M_PI * {d,dbp} * …` expressions.

**Sanity check after fix:** RMa LOS at 500 m / 2 GHz ≈ 100 dB (plausible);
before the fix ≈ 280 dB.

## P2 — eNB MAC crash on packet for departed UE (handover race)

**File:** `src/simu5g/stack/mac/LteMacEnb.cc`, `bufferizePacket()`.

`connDescOut_.at(cid)` was guarded only by an `ASSERT`, which compiles out in
release mode → `std::out_of_range` crash when a packet arrives for a
connection already torn down by handover. (The base-class version even has a
TODO acknowledging this unhandled path.)

**Fix:** if the CID is unknown, log a warning, drop the packet, return false —
data arriving for a departed UE is lost, which is the physically correct
semantic.

## P3 — RAC scheduler crash on stale request during handover

**Files:** `src/simu5g/stack/mac/scheduler/LteSchedulerEnbUl.cc`
(`racschedule()`), `src/simu5g/stack/mac/amc/LteAmc.cc` (`existTxParams()`).

A random-access request from a UE that is mid-handover can be processed by an
eNB whose AMC has no entry for that UE: `nodeIndex.at(id)` throws
`std::out_of_range` deep inside `computeTxParams()`, crashing the run
(reproducibly at the 2nd handover of the rural corridor, RuralSmoke t=700s).

**Fix:** (a) `existTxParams()` returns false instead of throwing when the
node is unknown; (b) `racschedule()` wraps per-node RAC handling in a
try/catch that skips the stale request with a warning — the UE retries RAC
normally.

## Verification after patching

- `simulations/corridorA` UrbanSmoke: 4-eNB chain, 3 handovers (t≈69/142/212 s
  at the geometric midpoints), 96% delivery, mean E2E 281 ms under 8 bgUEs/cell.
- `simulations/corridorA` RuralSmoke: 3-eNB chain at 10 km ISD, RMa LOS,
  95.7% delivery, mean E2E 374 ms, max 4.2 s at cell edge, no crash over 750 s.
