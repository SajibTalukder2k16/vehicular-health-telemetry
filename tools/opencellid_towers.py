#!/usr/bin/env python3
"""Convert OpenCellID cell-tower data into eNodeB positions for a SUMO-based
OMNeT++ scenario.

Input: a CSV in OpenCellID export format (radio,mcc,net,area,cell,unit,lon,lat,
range,samples,changeable,created,updated,averageSignal). Download for your
region from https://opencellid.org (free API key required) or use a full-
country extract filtered by the bbox.

The script:
  1. keeps cells of --radio inside the SUMO network's original geo bbox,
  2. filters to ONE operator (--mcc/--mnc); pooling operators models a network
     no single subscriber can use, so it must be requested explicitly,
  3. clusters cells within --site-radius meters into physical tower sites
     (one eNodeB per site, since one site hosts many cells/sectors),
  4. optionally keeps only sites within --near-dist of the drive --trace
     (sites far from the route cannot serve the UE),
  5. converts lat/lon to SUMO local x,y via the network's projection,
  6. emits an omnetpp.ini fragment with eNodeB positions, the initial-attach
     site, and an AUDIT block giving the route's distance-to-nearest-site
     profile.

IMPORTANT -- site selection bias. Earlier versions kept the --max-sites
*densest* clusters. On a rural route that silently discards the 1-2-cell
clusters, which is what a rural site looks like in OpenCellID, and so
manufactures coverage gaps that are not in the data. The bias is asymmetric:
it barely touches a dense urban extract but costs a rural route kilometres of
margin. --max-sites now selects the sites NEAREST THE ROUTE and refuses to run
without --trace, and the AUDIT block reports what the truncation did to the
coverage profile so the effect can never be invisible again. Prefer leaving
--max-sites at 0 (keep every site).

Note on what OpenCellID can support: its records are *estimated* cell
positions contributed by crowd-sourced measurements, and an absent record is
not evidence that an area lacks service. Coverage inferred from it should be
described as inferred, not measured.

Usage:
  opencellid_towers.py --cells va_cells.csv --net va_rural.net.xml \
      --trace va_ego.bonnmotion --mcc 310 --mnc 410 \
      --out towers_va_att.ini --site-radius 200 --x2-mesh

If --cells is omitted, emits a REPRESENTATIVE layout instead (sites along the
trace, or along the network diagonal) so scenarios stay runnable before real
data is available; the output file is clearly marked as synthetic in that case.
"""
import argparse
import csv
import math
import os
import sys

import sumolib


def cluster_sites(points, radius):
    """Greedy clustering: points within radius of a site centroid join it."""
    sites = []  # [x_sum, y_sum, n]
    for x, y in points:
        for s in sites:
            cx, cy = s[0] / s[2], s[1] / s[2]
            if math.hypot(x - cx, y - cy) <= radius:
                s[0] += x
                s[1] += y
                s[2] += 1
                break
        else:
            sites.append([x, y, 1])
    return [(s[0] / s[2], s[1] / s[2], s[2]) for s in sites]


def read_trace(path):
    """First line of a BonnMotion trace -> [(t, x, y), ...]."""
    vals = open(path).readline().split()
    return [(float(vals[i]), float(vals[i + 1]), float(vals[i + 2]))
            for i in range(0, len(vals) - 2, 3)]


def nearest_site_dist(route, sites):
    """For each route sample, distance to the nearest site."""
    return [min(math.hypot(x - sx, y - sy) for sx, sy, _ in sites)
            for _t, x, y in route]


def site_route_dist(site, route):
    sx, sy = site[0], site[1]
    return min(math.hypot(x - sx, y - sy) for _t, x, y in route)


def coverage_profile(route, sites, gap_thresh):
    """Time-weighted distance-to-nearest-site profile along the drive."""
    d = nearest_site_dist(route, sites)
    ts = [t for t, _x, _y in route]
    dt = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)] + [0.0]
    total = sum(dt) or 1.0
    gap = sum(w for w, di in zip(dt, d) if di > gap_thresh) / total * 100.0
    sd = sorted(d)
    p95 = sd[min(len(sd) - 1, int(0.95 * len(sd)))]
    return {'median': sd[len(sd) // 2], 'p95': p95, 'max': sd[-1], 'gap': gap}


def fmt_profile(p, gap_thresh):
    return (f"median {p['median']:.0f} m, p95 {p['p95']:.0f} m, "
            f"max {p['max']:.0f} m, {p['gap']:.2f}% of drive time beyond "
            f"{gap_thresh:.0f} m")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cells', help='OpenCellID CSV export')
    ap.add_argument('--net', required=True, help='SUMO .net.xml (for projection + bbox)')
    ap.add_argument('--out', required=True, help='omnetpp.ini fragment to write')
    ap.add_argument('--radio', default='LTE')
    ap.add_argument('--mcc', help='keep only this mobile country code (e.g. 310)')
    ap.add_argument('--mnc', help='keep only this network code (e.g. 410); '
                                  'omitting it pools operators -- see --allow-pooled')
    ap.add_argument('--allow-pooled', action='store_true',
                    help='permit pooling several operators into one network '
                         '(models coverage no single subscriber has)')
    ap.add_argument('--site-radius', type=float, default=150.0)
    ap.add_argument('--max-sites', type=int, default=0,
                    help='0 = keep every site (recommended). If >0, keeps the '
                         'sites nearest the --trace, never the densest.')
    ap.add_argument('--near-dist', type=float, default=0.0,
                    help='drop sites farther than this from the --trace '
                         '(0 = keep all)')
    ap.add_argument('--serving-rank', type=int, default=0, metavar='K',
                    help='keep only sites that are among the K nearest at some '
                         'point on the --trace (0 = keep all). K=2 keeps the '
                         'serving site and its handover candidate everywhere, '
                         'and preserves the coverage profile exactly while '
                         'cutting the O(n^2) X2 mesh. The AUDIT block proves '
                         'the profile is unchanged.')
    ap.add_argument('--gap-thresh', type=float, default=4500.0,
                    help='audit threshold for the coverage-gap fraction (m)')
    ap.add_argument('--fallback-isd', type=float, default=1000.0)
    ap.add_argument('--trace', help='BonnMotion trace: coverage audit, '
                                    'route-proximity selection, initial attach; '
                                    'also used to place synthetic fallback sites')
    ap.add_argument('--x2-mesh', action='store_true',
                    help='also emit full-mesh X2 app config (needed for real, '
                         'non-linear tower layouts; requires CorridorNet x2Mesh=true)')
    args = ap.parse_args()

    net = sumolib.net.readNet(args.net)
    xmin, ymin, xmax, ymax = net.getBoundary()
    route = read_trace(args.trace) if args.trace else None
    audit = []

    synthetic = False
    if args.cells and os.path.exists(args.cells):
        if not args.mnc and not args.allow_pooled:
            ap.error('real cell data without --mnc pools operators into one '
                     'network; pass --mnc <code> for a per-operator scenario, '
                     'or --allow-pooled if that is genuinely intended')
        pts = []
        seen_ops = set()
        with open(args.cells) as f:
            for row in csv.reader(f):
                if not row or row[0].lower() == 'radio':
                    continue
                radio, mcc, mnc = row[0], row[1], row[2]
                if radio.upper() != args.radio.upper():
                    continue
                if args.mcc and mcc != args.mcc:
                    continue
                if args.mnc and mnc != args.mnc:
                    continue
                seen_ops.add((mcc, mnc))
                x, y = net.convertLonLat2XY(float(row[6]), float(row[7]))
                if xmin <= x <= xmax and ymin <= y <= ymax:
                    pts.append((x, y))
        if not pts:
            ap.error(f'no {args.radio} cells matched mcc={args.mcc} mnc={args.mnc}')
        op = (f"mcc{args.mcc or '*'}-mnc{args.mnc or '*'}"
              + ('' if len(seen_ops) == 1 else f' POOLED{sorted(seen_ops)}'))
        sites = cluster_sites(pts, args.site_radius)
        audit.append(f"{len(pts)} {args.radio} cells ({op}) -> {len(sites)} "
                     f"clusters at {args.site_radius:.0f} m site radius")
        if route:
            full = coverage_profile(route, sites, args.gap_thresh)
            audit.append(f"all {len(sites)} sites: {fmt_profile(full, args.gap_thresh)}")
        if args.near_dist > 0:
            if not route:
                ap.error('--near-dist requires --trace')
            keep = [s for s in sites if site_route_dist(s, route) <= args.near_dist]
            if len(keep) != len(sites):
                audit.append(f"dropped {len(sites) - len(keep)} site(s) farther "
                             f"than {args.near_dist:.0f} m from the route")
            sites = keep
        if args.serving_rank > 0:
            if not route:
                ap.error('--serving-rank requires --trace')
            K = args.serving_rank
            used = set()
            for _t, x, y in route:
                order = sorted(range(len(sites)),
                               key=lambda i: math.hypot(x - sites[i][0], y - sites[i][1]))
                used.update(order[:K])
            kept = [sites[i] for i in sorted(used)]
            prof = coverage_profile(route, kept, args.gap_thresh)
            audit.append(f"kept the {len(kept)} site(s) that are among the {K} "
                         f"nearest at some point on the route (of {len(sites)}): "
                         f"{fmt_profile(prof, args.gap_thresh)}")
            if abs(prof['max'] - full['max']) > 1.0 or prof['gap'] > full['gap'] + 0.01:
                audit.append("WARNING: this selection changed the coverage "
                             "profile; raise --serving-rank.")
            else:
                audit.append("distance-to-nearest-site profile is IDENTICAL to "
                             "the full site set. NOTE: this establishes only "
                             "that coverage geometry is preserved. Interference, "
                             "handover behaviour and delivery performance are "
                             "NOT verified by this check and may differ from the "
                             "full site set.")
            sites = kept
        if args.max_sites and len(sites) > args.max_sites:
            if not route:
                ap.error('--max-sites requires --trace (selection is by route '
                         'proximity; density selection manufactures gaps)')
            sites = sorted(sites, key=lambda s: site_route_dist(s, route))[:args.max_sites]
            trunc = coverage_profile(route, sites, args.gap_thresh)
            audit.append(f"TRUNCATED to the {args.max_sites} sites nearest the "
                         f"route: {fmt_profile(trunc, args.gap_thresh)}")
            if route and trunc['gap'] > full['gap'] + 0.01:
                audit.append(f"WARNING: truncation raised the gap fraction from "
                             f"{full['gap']:.2f}% to {trunc['gap']:.2f}% -- the "
                             f"gap is an artifact of site selection, not of the "
                             f"cell data. Raise --max-sites.")
        src = (f"{len(pts)} {args.radio} cells ({op}) -> {len(sites)} sites "
               f"from {os.path.basename(args.cells)}")
    else:
        synthetic = True
        sites = []
        n_cap = args.max_sites or 12
        if args.trace:
            pts = [(x, y) for _t, x, y in route]
            # walk the trace, dropping a site every fallback-isd meters,
            # offset 120 m perpendicular so towers are roadside, not on-road
            acc = args.fallback_isd / 2
            for k in range(1, len(pts)):
                (x0, y0), (x1, y1) = pts[k - 1], pts[k]
                seg = math.hypot(x1 - x0, y1 - y0)
                acc += seg
                if acc >= args.fallback_isd and seg > 0:
                    ux, uy = (x1 - x0) / seg, (y1 - y0) / seg
                    sites.append((x1 - uy * 120, y1 + ux * 120, 0))
                    acc = 0
                if len(sites) >= n_cap:
                    break
            src = (f"SYNTHETIC layout: {len(sites)} sites every ~{args.fallback_isd:.0f} m "
                   f"along {os.path.basename(args.trace)} (no OpenCellID data given)")
        else:
            for i in range(n_cap):
                t = (i + 0.5) / n_cap
                sites.append((xmin + t * (xmax - xmin), ymin + t * (ymax - ymin), 0))
            src = (f"SYNTHETIC layout: {n_cap} sites along network diagonal at "
                   f"~{args.fallback_isd:.0f} m equivalent ISD (no OpenCellID data given)")

    attach = None
    if route:
        final = coverage_profile(route, sites, args.gap_thresh)
        audit.append(f"SELECTED {len(sites)} sites: {fmt_profile(final, args.gap_thresh)}")
        x0, y0 = route[0][1], route[0][2]
        attach = min(range(len(sites)),
                     key=lambda i: math.hypot(sites[i][0] - x0, sites[i][1] - y0))
        d0 = math.hypot(sites[attach][0] - x0, sites[attach][1] - y0)
        audit.append(f"initial attach: eNodeB[{attach}] is nearest the trace "
                     f"start ({d0:.0f} m)")

    with open(args.out, 'w') as f:
        f.write(f"# generated by opencellid_towers.py -- {src}\n")
        if synthetic:
            f.write("# WARNING: synthetic placeholder positions; replace with real\n"
                    "# OpenCellID data before producing paper results\n")
        if audit:
            f.write("#\n# AUDIT (site selection and route coverage profile)\n")
            for line in audit:
                f.write(f"#   {line}\n")
            f.write("# OpenCellID positions are ESTIMATED cell locations from\n"
                    "# crowd-sourced measurements; a missing record is not evidence\n"
                    "# of absent service. Coverage derived here is INFERRED.\n#\n")
        f.write(f"*.numEnb = {len(sites)}\n")
        for i, (x, y, ncells) in enumerate(sites):
            note = f"  # {ncells} cells" if ncells else ""
            f.write(f"*.eNodeB[{i}].mobility.initialX = {x:.1f}m{note}\n")
            f.write(f"*.eNodeB[{i}].mobility.initialY = {y:.1f}m\n")
        if attach is not None:
            f.write(f"\n# nearest site to the trace start\n"
                    f"*.ue.servingNodeId = {attach + 1}\n")
        if args.x2_mesh:
            n = len(sites)
            f.write("\n# X2 full mesh (real layouts are not linear chains)\n")
            f.write("*.x2Mesh = true\n")
            f.write(f"*.eNodeB[*].numX2Apps = {n - 1}\n")
            f.write("*.eNodeB[*].x2App[*].server.localPort = 5000 + ancestorIndex(1)\n")
            for i in range(n):
                for k, j in enumerate(x for x in range(n) if x != i):
                    f.write(f"*.eNodeB[{i}].x2App[{k}].client.connectAddress = \"eNodeB[{j}]%x2ppp0\"\n")
    print(f"{src}")
    for line in audit:
        print(f"  {line}")
    print(f"-> {args.out} ({len(sites)} eNodeBs)")


if __name__ == '__main__':
    sys.exit(main())
