package paperrebuild.simulations.room;

import inet.networklayer.configurator.ipv4.Ipv4NetworkConfigurator;
import inet.node.ethernet.Eth1G;
import inet.node.inet.StandardHost;
import inet.node.inet.WirelessHost;
import inet.node.wireless.AccessPoint;
import inet.physicallayer.wireless.ieee80211.packetlevel.Ieee80211ScalarRadioMedium;
import paperrebuild.nodes.SensorRig;

// In-room baseline: sensor rig -> edge host (embedded PC) -> real 802.11n/ac
// WiFi -> access point -> wired cloud server. The WiFi band/mode is a real
// PHY configuration, so 2.4 vs 5 GHz differ for physical reasons.
network RoomNet
{
    parameters:
        @display("bgb=400,300");
    submodules:
        configurator: Ipv4NetworkConfigurator {
            @display("p=50,50");
        }
        radioMedium: Ieee80211ScalarRadioMedium {
            @display("p=50,120");
        }
        rig: SensorRig {
            @display("p=120,220");
        }
        edgeHost: WirelessHost {
            @display("p=200,150");
        }
        ap: AccessPoint {
            @display("p=280,100");
        }
        cloud: StandardHost {
            @display("p=350,50;i=device/server");
        }
    connections:
        ap.ethg++ <--> Eth1G <--> cloud.ethg++;
}
