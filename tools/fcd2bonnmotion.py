#!/usr/bin/env python3
"""Convert SUMO FCD output to BonnMotion trace format for INET's BonnMotionMobility.

BonnMotion format: one line per node, whitespace-separated "t x y" triplets.
Usage: fcd2bonnmotion.py fcd.xml out.bonnmotion [--3d]
"""
import sys
import xml.etree.ElementTree as ET
from collections import OrderedDict


def convert(fcd_path, out_path, use3d=False):
    traces = OrderedDict()  # vehicle id -> list of (t, x, y)
    for _, elem in ET.iterparse(fcd_path, events=("end",)):
        if elem.tag == "timestep":
            t = float(elem.get("time"))
            for veh in elem.iter("vehicle"):
                traces.setdefault(veh.get("id"), []).append(
                    (t, float(veh.get("x")), float(veh.get("y"))))
            elem.clear()
    with open(out_path, "w") as f:
        for veh_id, points in traces.items():
            if use3d:
                line = " ".join(f"{t} {x} {y} 0" for t, x, y in points)
            else:
                line = " ".join(f"{t} {x} {y}" for t, x, y in points)
            f.write(line + "\n")
    print(f"{len(traces)} node trace(s) written to {out_path}: "
          + ", ".join(f"{v}({len(p)} pts)" for v, p in traces.items()))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    convert(sys.argv[1], sys.argv[2], use3d="--3d" in sys.argv[3:])
