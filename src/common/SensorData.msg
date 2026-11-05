// Intra-vehicle/room sensor message (rig side, plain OMNeT++ packet).
// Byte length is set by the source; creation time carries the sensing instant.

namespace paperrebuild;

packet SensorData
{
    int sourceType;       // 0=wearable vitals, 1=OBD, 2=camera, 3=alarm
    long sequenceNumber;
}
