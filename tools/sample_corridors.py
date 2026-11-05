#!/usr/bin/env python3
"""Sample candidate drive corridors from the national OpenCellID extract and
characterise each one's tower geometry.

WHY: the regime finding -- whether a corridor is contention-limited or
coverage-limited -- currently rests on two routes, both of which turned out to
be coverage-limited. That leaves the question the controller work depends on
unanswered: how common is the regime where admission control actually matters?

WHAT THIS DOES AND DOES NOT MODEL. The corridor is a straight line of
--length-km through the real, measured tower field of one operator. Tower
positions and therefore the distance-to-nearest-site profile are real; road
topology is idealised. That is the right trade for this question, because the
regime is set by site spacing rather than by road curvature, and the existing
corridorA scenarios already drive straight chains. It should be stated
plainly in any write-up rather than glossed.

OpenCellID caveat carried from docs/TOWER_DATA.md: positions are *estimated*
cell locations from crowd-sourced measurements, and a missing record is not
evidence of absent service. Coverage inferred here is inferred, not measured.

Usage:
  sample_corridors.py --cells <dir> --mcc 310 --mnc 260 --n 300 \
      --length-km 20 --out corridors.csv
"""
import argparse
import csv
import math
import os
import sys

import numpy as np
from pyproj import Proj
from scipy.spatial import cKDTree

EARTH_R = 6371000.0


def load_cells(path, mcc, mnc, radio='LTE'):
    """(lon, lat) of every matching cell. Accepts a file or a directory."""
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
                if len(r) < 8 or r[0] != radio:
                    continue
                if r[1] != mcc or r[2] != mnc:
                    continue
                try:
                    lon.append(float(r[6]))
                    lat.append(float(r[7]))
                except ValueError:
                    continue
    return np.array(lon), np.array(lat)


def count_sites(xy, radius=200.0):
    """Approximate physical-site count by snapping cells to a radius-sized grid.

    The greedy clustering in opencellid_towers.py is O(n * sites), which is
    fine for one corridor's few hundred cells but intractable here: a dense
    metro puts thousands of cells in the sampling box and this runs over
    hundreds of corridors. Grid snapping is O(n) and accurate enough for a
    site COUNT, which is all this value is used for.
    """
    if len(xy) == 0:
        return 0
    return int(len(np.unique(np.round(xy / radius).astype(np.int64), axis=0)))


def profile(route_xy, cell_xy):
    """Distance from each route sample to the nearest CELL.

    Clustering is unnecessary for this: co-located cells sit at the same
    position, so nearest-cell distance equals nearest-site distance. A KD-tree
    makes it O(n log n) rather than an O(n*m) pairwise matrix, which is what
    made the first version of this script intractable.
    """
    if len(cell_xy) == 0:
        return np.full(len(route_xy), np.inf)
    return cKDTree(cell_xy).query(route_xy, k=1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cells', required=True, help='OpenCellID csv file or directory')
    ap.add_argument('--mcc', default='310')
    ap.add_argument('--mnc', default='260')
    ap.add_argument('--n', type=int, default=300, help='candidate corridors to sample')
    ap.add_argument('--length-km', type=float, default=20.0)
    ap.add_argument('--samples', type=int, default=200, help='route sample points')
    ap.add_argument('--site-radius', type=float, default=200.0)
    ap.add_argument('--horizon', type=float, default=7000.0,
                    help='usable range (m); -104 dBm gives about 7 km')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    lon, lat = load_cells(args.cells, args.mcc, args.mnc)
    print(f'{len(lon):,} LTE cells for mcc{args.mcc}-mnc{args.mnc}', file=sys.stderr)
    if len(lon) == 0:
        sys.exit('no cells matched')

    # Keep CONUS so the projection stays sane and the sample is one country.
    keep = (lon > -125) & (lon < -66) & (lat > 24) & (lat < 50)
    lon, lat = lon[keep], lat[keep]
    print(f'{len(lon):,} within CONUS', file=sys.stderr)

    rng = np.random.default_rng(args.seed)
    # Anchor corridors on actual cells so every corridor has some service
    # somewhere; sampling blank map would mostly return empty ocean/desert.
    idx = rng.choice(len(lon), size=min(args.n, len(lon)), replace=False)

    rows = []
    half = args.length_km * 1000.0 / 2.0
    for k, i in enumerate(idx):
        clon, clat = lon[i], lat[i]
        proj = Proj(proj='aeqd', lat_0=clat, lon_0=clon, datum='WGS84')
        # cells within a generous box around the corridor
        box = 0.45  # degrees, ~50 km
        near = ((lon > clon - box) & (lon < clon + box) &
                (lat > clat - box) & (lat < clat + box))
        if near.sum() < 2:
            continue
        cx, cy = proj(lon[near], lat[near])
        cells = np.column_stack([cx, cy])
        n_sites = count_sites(cells, args.site_radius)

        bearing = rng.uniform(0, 2 * math.pi)
        t = np.linspace(-half, half, args.samples)
        route = np.column_stack([t * math.cos(bearing), t * math.sin(bearing)])

        d = profile(route, cells)
        rows.append({
            'lon': round(float(clon), 5), 'lat': round(float(clat), 5),
            'bearing_deg': round(math.degrees(bearing), 1),
            'n_sites_50km': n_sites,
            'median_m': round(float(np.median(d)), 1),
            'p95_m': round(float(np.percentile(d, 95)), 1),
            'max_m': round(float(d.max()), 1),
            'frac_beyond_horizon': round(float((d > args.horizon).mean()), 4),
        })
        if (k + 1) % 50 == 0:
            print(f'  {k+1}/{len(idx)} corridors', file=sys.stderr)

    with open(args.out, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f'wrote {len(rows)} corridors -> {args.out}', file=sys.stderr)


if __name__ == '__main__':
    main()
