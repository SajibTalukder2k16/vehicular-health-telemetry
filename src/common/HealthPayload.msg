// Application payload carried over UDP from the edge to the cloud server.
// sensorCreationTime preserves the original sensing instant across the
// edge queue and the cellular/WiFi backhaul, so the server can compute
// true end-to-end delay and Age of Information.

import inet.common.INETDefs;
import inet.common.packet.chunk.Chunk;

namespace paperrebuild;

class HealthPayload extends inet::FieldsChunk
{
    simtime_t sensorCreationTime;
    int sourceType;       // 0=wearable vitals, 1=OBD, 2=camera, 3=alarm
    long sequenceNumber;
    simtime_t edgeDelay;  // time spent in the edge queue+processing
}

// Compact feedback from the cloud server back to the vehicle gateway.
//
// A real gateway cannot see the radio's queue depth or the server's true Age
// of Information; it only learns what the far end tells it, late. This chunk
// is what the gateway is allowed to use: cumulative bytes the server has
// received, and the freshest sensing timestamp it holds per stream. Its
// delay, loss and byte overhead are all simulated, since it travels as an
// ordinary UDP packet over the same network.
class GatewayFeedback extends inet::FieldsChunk
{
    uint64_t bytesReceived;            // cumulative application bytes at the server
    uint64_t packetsReceived;          // cumulative packets at the server
    simtime_t freshestVitals;          // newest vitals sensing time held
    simtime_t freshestCamera;          // newest camera sensing time held
    simtime_t generatedAt;             // when the server built this report
}
