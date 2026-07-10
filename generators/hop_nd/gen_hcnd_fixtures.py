#!/usr/bin/env python3
"""Generate baseline Hop-Constrained Network Design (HCND) fixtures with
certified optima: a handful of tiny hand-verified instances (used to
validate the layered-graph formulation itself) plus small/medium random
instances across topologies.

See hcnd_lib.py for the formulation. All fixtures here are expected to be
solved at or near the root node (baseline/regression coverage, not the
"interesting" harder set built later by gen_hcnd_search.py /
gen_hcnd_diverse.py).
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hcnd_lib import build_layered_mps, write_mps_gz, solve_with_mipster, generate_instance

ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = ROOT / "mips"
TIME_LIMIT = 60


def make_and_solve(name, instance):
    mps_text = build_layered_mps(name, instance)
    path = MIPS_DIR / f"{name}.mps.gz"
    write_mps_gz(mps_text, path)
    r = solve_with_mipster(path, TIME_LIMIT)
    print(f"{name:35s} optimal={r['optimal']!s:5} obj={r['obj']!s:>10} "
          f"nodes={r['nodes']!s:>6} wall={r['wall']:>6.2f}s")
    return r


# ---------------------------------------------------------------------
# Hand-verified tiny instances (formulation sanity checks; also serve as
# minimal regression fixtures).
# ---------------------------------------------------------------------
HAND_VERIFIED = [
    ("hcnd_tiny_hopchoice", dict(
        n=4, edges=[(0, 1, 5, 10), (1, 2, 5, 10), (2, 3, 5, 10),
                    (0, 3, 100, 10), (0, 2, 8, 10), (1, 3, 8, 10)],
        commodities=[(0, 3, 5)], hop_limit=2, seed=0)),
    ("hcnd_tiny_capforce", dict(
        n=3, edges=[(0, 1, 5, 3), (1, 2, 5, 3), (0, 2, 20, 10)],
        commodities=[(0, 2, 5)], hop_limit=2, seed=0)),
    ("hcnd_tiny_hop1", dict(
        n=4, edges=[(0, 1, 5, 10), (1, 2, 5, 10), (2, 3, 5, 10),
                    (0, 3, 100, 10), (0, 2, 8, 10), (1, 3, 8, 10)],
        commodities=[(0, 3, 5)], hop_limit=1, seed=0)),
    ("hcnd_tiny_shared", dict(
        n=3, edges=[(0, 1, 1, 5), (1, 2, 1, 5), (0, 2, 100, 100)],
        commodities=[(0, 2, 3), (1, 2, 3)], hop_limit=2, seed=0)),
]

# ---------------------------------------------------------------------
# Small/medium random instances (baseline coverage across sizes).
# ---------------------------------------------------------------------
RANDOM_SPECS = [
    dict(name="hcnd_small_sparse", n=6, edge_prob=0.5, num_commodities=2, hop_limit=3, seed=1),
    dict(name="hcnd_small_dense", n=6, edge_prob=0.8, num_commodities=3, hop_limit=3, seed=2),
    dict(name="hcnd_medium_sparse", n=9, edge_prob=0.4, num_commodities=3, hop_limit=3, seed=3),
    dict(name="hcnd_medium_dense", n=9, edge_prob=0.6, num_commodities=4, hop_limit=4, seed=4),
    dict(name="hcnd_medium_manycomm", n=8, edge_prob=0.5, num_commodities=6, hop_limit=3, seed=5),
]


def main():
    report = []

    for name, instance in HAND_VERIFIED:
        r = make_and_solve(name, instance)
        report.append((name, r))

    for spec in RANDOM_SPECS:
        name = spec.pop("name")
        instance = generate_instance(**spec)
        r = make_and_solve(name, instance)
        report.append((name, r))

    n_ok = sum(1 for _, r in report if r["optimal"])
    print(f"\n{n_ok}/{len(report)} solved to optimality within {TIME_LIMIT}s")

    out = {name: dict(obj=r["obj"], optimal=r["optimal"], nodes=r["nodes"], wall=r["wall"])
           for name, r in report}
    Path("/tmp/hcnd_fixtures_report.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
