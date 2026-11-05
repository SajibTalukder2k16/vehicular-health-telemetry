package paperrebuild.simulations.validation_wifi;

import paperrebuild.links.WifiLink;
import paperrebuild.nodes.DelaySink;
import paperrebuild.nodes.SensorSource;

// Unit-validation harness: one sensor stream over one 802.11 DCF link.
// Mirrors validation_ble so the two link models are held to the same bar.
network WifiValidationNet
{
    submodules:
        src: SensorSource {
            @display("p=60,60");
        }
        link: WifiLink {
            @display("p=180,60");
        }
        sink: DelaySink {
            @display("p=300,60");
        }
    connections:
        src.out --> link.in++;
        link.out --> sink.in;
}
