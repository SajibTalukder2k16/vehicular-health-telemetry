package paperrebuild.nodes;

import paperrebuild.links.ILink;
import paperrebuild.links.BleLink;

// Tier-1 sensor suite + Tier-2 edge compute stage of one vehicle or room.
// The wearable always uses BLE; camera and OBD link types are experiment
// factors. The alarm stream is generated at the edge itself (modeling the
// edge's own analysis of the fused Tier-1 streams flagging an anomaly),
// so it never traverses a Tier-1 link -- it enters the edge queue directly.
// The edge forwards processed packets to the backhaul app named by
// targetModule (an EdgeApp inside the UE/WiFi host).
module SensorRig
{
    parameters:
        string targetModule = default("");
        string cameraLinkType = default("WiredLink");
        string obdLinkType = default("WiredLink");
        bool hasObd = default(true);
        @display("i=misc/sensorgateway;bgb=420,300");
    submodules:
        wearable: SensorSource {
            sourceType = 0;
            messageLength = default(512B);
            sendInterval = default(exponential(1s));
            @display("p=60,60");
        }
        alarm: SensorSource {
            // edge-generated (Tier 2), not a Tier-1 device -- see note above
            sourceType = 3;
            messageLength = default(128B);
            sendInterval = default(exponential(300s));
            @display("p=250,110");
        }
        obd: SensorSource if hasObd {
            sourceType = 1;
            messageLength = default(256B);
            sendInterval = default(exponential(2s));
            @display("p=60,220");
        }
        camera: SensorSource {
            sourceType = 2;
            messageLength = default(4KiB);
            sendInterval = default(0.5s);
            @display("p=60,290");
        }
        bleWearable: BleLink {
            @display("p=180,100");
        }
        obdLink: <obdLinkType> like ILink if hasObd {
            @display("p=180,220");
        }
        camLink: <cameraLinkType> like ILink {
            @display("p=180,290");
        }
        edge: EdgeAggregator {
            targetModule = parent.targetModule;
            @display("p=320,170");
        }
    connections allowunconnected:
        wearable.out --> bleWearable.in++;
        obd.out --> obdLink.in++ if hasObd;
        camera.out --> camLink.in++;
        bleWearable.out --> edge.in++;
        obdLink.out --> edge.in++ if hasObd;
        camLink.out --> edge.in++;
        alarm.out --> edge.in++;         // edge-generated: no Tier-1 link hop
}
