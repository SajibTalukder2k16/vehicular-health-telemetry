#!/usr/bin/env python3
"""Emit an OMNeT++ scenario for one sampled corridor: real tower positions and
a straight-line drive, with no SUMO network needed.

The corridors sampled by tools/sample_corridors.py are straight lines through
the real tower field, so the mobility trace can be written directly rather
than routed through SUMO. Tower positions are real; road topology is
idealised, which is the documented trade for this study (see
docs/CORRIDOR_POPULATION.md).

Two constraints shape the site selection:

  * Simu5G's RMa LOS path loss ASSERTS beyond 10 km, and Simu5G evaluates
    interference from every eNB regardless of the delivery horizon. Sites
    further than --max-site-dist from the route are therefore dropped. They
    sit well beyond the ~7 km usable horizon anyway, so this does not change
    the coverage profile -- the emitted AUDIT block reports the profile with
    and without them so that claim is checkable rather than asserted.

  * X2 is a full mesh in CorridorNet, which is O(n^2). Keeping only sites that
    are among the --serving-rank nearest at some point on the route preserves
    the coverage profile exactly while bounding the mesh.

Usage:
  make_corridor_scenario.py --cells <dir> --mcc 310 --mnc 260 \
      --lon -98.4 --lat 39.1 --bearing 73.2 --name c012 --outdir <dir>
"""
import argparse
import csv
import math
import os
import sys

import numpy as np
from pyproj import Proj
from scipy.spatial import cKDTree


def load_cells(path, mcc, mnc, radio='LTE'):
    files = []
    if os.path.isdir(path):
        for root, _d, names in os.walk(path):
            files += [os.path.join(root, n) for n in names if n.endswith('.csv')]
    else:
        files = [path]
    lon, lat = [], []
    for f in files:
        with open(f, errors='replace') as fh:
            for r in csv.reader(fh):
                if len(r) < 8 or r[0] != radio or r[1] != mcc or r[2] != mnc:
                    continue
                try:
                    lon.append(float(r[6])); lat.append(float(r[7]))
                except ValueError:
                    continue
    return np.array(lon), np.array(lat)


def cluster(xy, radius=200.0):
    """Grid-snap cells into sites and return each site's centroid."""
    if len(xy) == 0:
        return np.empty((0, 2))
    key = np.round(xy / radius).astype(np.int64)
    _u, inv = np.unique(key, axis=0, return_inverse=True)
    out = np.zeros((inv.max() + 1, 2))
    cnt = np.zeros(inv.max() + 1)
    np.add.at(out, inv, xy)
    np.add.at(cnt, inv, 1)
    return out / cnt[:, None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cells', required=True)
    ap.add_argument('--mcc', default='310')
    ap.add_argument('--mnc', default='260')
    ap.add_argument('--lon', type=float, required=True)
    ap.add_argument('--lat', type=float, required=True)
    ap.add_argument('--bearing', type=float, required=True)
    ap.add_argument('--name', required=True)
    ap.add_argument('--outdir', required=True)
    ap.add_argument('--length-km', type=float, default=20.0)
    ap.add_argument('--speed-mps', type=float, default=15.28)
    ap.add_argument('--site-radius', type=float, default=200.0)
    ap.add_argument('--serving-rank', type=int, default=2)
    ap.add_argument('--max-sites', type=int, default=20,
                    help='cap on sites, keeping those nearest the route. X2 '
                         'must be a full mesh (see below) and that is O(n^2), '
                         'so dense corridors have to be thinned. The AUDIT '
                         'block reports the profile before and after so the '
                         'effect on coverage is checkable.')
    ap.add_argument('--max-site-dist', type=float, default=9000.0)
    ap.add_argument('--horizon', type=float, default=7000.0)
    ap.add_argument('--margin', type=float, default=2000.0)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    lon, lat = load_cells(args.cells, args.mcc, args.mnc)
    proj = Proj(proj='aeqd', lat_0=args.lat, lon_0=args.lon, datum='WGS84')
    box = 0.45
    near = ((lon > args.lon - box) & (lon < args.lon + box) &
            (lat > args.lat - box) & (lat < args.lat + box))
    cx, cy = proj(lon[near], lat[near])
    sites_all = cluster(np.column_stack([cx, cy]), args.site_radius)

    half = args.length_km * 1000.0 / 2.0
    th = math.radians(args.bearing)
    n_s = 400
    t = np.linspace(-half, half, n_s)
    route = np.column_stack([t * math.cos(th), t * math.sin(th)])

    def prof(sites):
        if len(sites) == 0:
            return np.full(n_s, np.inf)
        return cKDTree(sites).query(route, k=1)[0]

    full = prof(sites_all)
    # drop sites Simu5G cannot legally evaluate (and which are out of range anyway)
    if len(sites_all):
        d_site = cKDTree(route).query(sites_all, k=1)[0]
        sites_valid = sites_all[d_site <= args.max_site_dist]
    else:
        sites_valid = sites_all
    valid = prof(sites_valid)

    # keep only sites that are ever among the serving-rank nearest
    if len(sites_valid) > args.serving_rank:
        # k=1 returns a 1-D index array, k>1 a 2-D one; np.unique flattens
        # either, which is all that is needed here.
        nn = cKDTree(sites_valid).query(route, k=args.serving_rank)[1]
        sites = sites_valid[np.unique(nn)]
    else:
        sites = sites_valid
    # Cap the site count. X2 has to be a FULL MESH: the chain wiring assumes
    # handover only ever happens between consecutive sites, but with real
    # tower geometry the best server jumps non-consecutively, and the handover
    # manager then sends X2 to a peer the chain never wired -- which surfaces
    # as "Address contains no value" late in a run. A mesh is O(n^2), so
    # dense corridors must be thinned instead.
    if len(sites) > args.max_sites:
        # Thin by ROUTE POSITION, not by distance to the route. Keeping the
        # globally nearest sites drops whichever ones cover the far end and
        # opens artificial gaps there -- measured on c09 it pushed max
        # distance 4693 -> 8046 m and invented 5.2% of the drive "beyond
        # horizon", which would have misclassified the very regime this study
        # is trying to measure. Taking the nearest site to each of max_sites
        # evenly spaced waypoints keeps coverage spread along the whole drive.
        way = route[np.linspace(0, len(route) - 1, args.max_sites).round().astype(int)]
        keep = np.unique(cKDTree(sites).query(way, k=1)[1])
        sites = sites[keep]
    sel = prof(sites)

    if len(sites) == 0:
        sys.exit(f'{args.name}: no usable sites')

    # Order sites along the direction of travel. CorridorNet's chain X2 wiring
    # connects consecutive indices, so this makes the chain geographically
    # consecutive -- which is what handover actually needs, since a vehicle
    # hands over between adjacent sites, not arbitrary pairs. A full mesh is
    # O(n^2) and intractable here: a dense corridor keeps 80+ sites, and 41
    # sites already took ~24 minutes per 60 s of simulated time.
    along = sites[:, 0] * math.cos(th) + sites[:, 1] * math.sin(th)
    sites = sites[np.argsort(along)]

    # shift into a positive coordinate frame for OMNeT++
    allx = np.concatenate([route[:, 0], sites[:, 0]])
    ally = np.concatenate([route[:, 1], sites[:, 1]])
    ox, oy = allx.min() - args.margin, ally.min() - args.margin
    route_s = route - [ox, oy]
    sites_s = sites - [ox, oy]
    maxx, maxy = allx.max() - ox + args.margin, ally.max() - oy + args.margin

    sim_time = (2 * half) / args.speed_mps
    # straight-line BonnMotion trace: "t x y t x y ..."
    steps = int(sim_time) + 1
    tr = []
    for i in range(steps):
        tt = i
        p = route_s[0] + (route_s[-1] - route_s[0]) * (tt * args.speed_mps / (2 * half))
        p = np.clip(p, [0, 0], [maxx, maxy])
        tr += [f'{tt}', f'{p[0]:.2f}', f'{p[1]:.2f}']
    trace_path = os.path.join(args.outdir, f'{args.name}.bonnmotion')
    open(trace_path, 'w').write(' '.join(tr) + '\n')

    start = route_s[0]
    attach = int(np.argmin(np.hypot(sites_s[:, 0] - start[0], sites_s[:, 1] - start[1])))

    n = len(sites)
    lines = [
        f'# corridor {args.name}: lon {args.lon}, lat {args.lat}, bearing {args.bearing} deg',
        f'# operator mcc{args.mcc}-mnc{args.mnc}; {int(near.sum())} LTE cells in box',
        '#',
        '# AUDIT -- distance to nearest site along the drive (m)',
        f'#   all {len(sites_all)} sites:        median {np.median(full):7.0f}  p95 {np.percentile(full,95):7.0f}  max {full.max():7.0f}  beyond {args.horizon:.0f} m: {(full>args.horizon).mean()*100:5.2f}%',
        f'#   within {args.max_site_dist:.0f} m ({len(sites_valid)}): median {np.median(valid):7.0f}  p95 {np.percentile(valid,95):7.0f}  max {valid.max():7.0f}  beyond: {(valid>args.horizon).mean()*100:5.2f}%',
        f'#   selected ({n}):         median {np.median(sel):7.0f}  p95 {np.percentile(sel,95):7.0f}  max {sel.max():7.0f}  beyond: {(sel>args.horizon).mean()*100:5.2f}%',
        '# Dropping distant sites must not change the profile -- they lie beyond',
        '# the usable horizon. Compare the three rows above to check that.',
        '# OpenCellID positions are ESTIMATED cell locations; a missing record is',
        '# not evidence of absent service. Coverage here is INFERRED.',
        '#',
        f'*.numEnb = {n}',
    ]
    for i, (x, y) in enumerate(sites_s):
        lines.append(f'*.eNodeB[{i}].mobility.initialX = {x:.1f}m')
        lines.append(f'*.eNodeB[{i}].mobility.initialY = {y:.1f}m')
    lines += [
        '',
        f'*.ue.servingNodeId = {attach + 1}',
        f'*.ue.mobility.traceFile = "{args.name}.bonnmotion"',
        f'sim-time-limit = {sim_time:.0f}s',
        f'**.mobility.constraintAreaMinX = 0m',
        f'**.mobility.constraintAreaMinY = 0m',
        f'**.mobility.constraintAreaMaxX = {maxx:.0f}m',
        f'**.mobility.constraintAreaMaxY = {maxy:.0f}m',
        '',
        '# X2 FULL MESH. Real tower layouts are not chains: the best server',
        '# can jump between non-adjacent sites, and a chain leaves those',
        '# handovers unwired, which fails late in a run as an empty X2',
        '# address. The mesh is O(n^2), which is why --max-sites caps n.',
        '*.x2Mesh = true',
        f'*.eNodeB[*].numX2Apps = {n - 1}',
        '*.eNodeB[*].x2App[*].server.localPort = 5000 + ancestorIndex(1)',
    ]
    for i in range(n):
        for k, j in enumerate(x for x in range(n) if x != i):
            lines.append(f'*.eNodeB[{i}].x2App[{k}].client.connectAddress = "eNodeB[{j}]%x2ppp0"')

    ini_path = os.path.join(args.outdir, f'{args.name}.ini')
    open(ini_path, 'w').write('\n'.join(lines) + '\n')
    print(f'{args.name}: {n} sites (of {len(sites_all)}), '
          f'profile median {np.median(sel):.0f} max {sel.max():.0f} m, '
          f'beyond horizon {(sel>args.horizon).mean()*100:.1f}%, sim {sim_time:.0f}s')


if __name__ == '__main__':
    main()
