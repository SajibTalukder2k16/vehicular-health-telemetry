package paperrebuild.simulations.validation_ble;

import paperrebuild.links.BleLink;
import paperrebuild.nodes.DelaySink;
import paperrebuild.nodes.SensorSource;

// Unit-validation harness: one sensor stream over one BLE link.
network BleValidationNet
{
    submodules:
        src: SensorSource {
            @display("p=60,60");
        }
        link: BleLink {
            @display("p=180,60");
        }
        sink: DelaySink {
            @display("p=300,60");
        }
    connections:
        src.out --> link.in++;
        link.out --> sink.in;
}
