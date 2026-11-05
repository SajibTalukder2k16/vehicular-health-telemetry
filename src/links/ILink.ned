package paperrebuild.links;

// Common interface for intra-rig sensor-to-edge links (BLE, wired).
moduleinterface ILink
{
    gates:
        input in[];
        output out;
}
