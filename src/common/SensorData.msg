// Intra-vehicle/room sensor message (rig side, plain OMNeT++ packet).
// Byte length is set by the source; creation time carries the sensing instant.

namespace paperrebuild;

// sourceType 4 (evidence) is not produced by a SensorSource. The edge
// synthesizes it when an alarm passes through, because the edge is what ran
// the inference: an escalation is an ALERT the server acts on plus the
// EVIDENCE the server verifies it with, emitted at the same instant over the
// same link. See EdgeApp's escalation section and docs/PLAN_2026-11.md §6.
packet SensorData
{
    int sourceType;       // 0=wearable vitals, 1=OBD, 2=camera, 3=alarm, 4=evidence
    long sequenceNumber;
}
