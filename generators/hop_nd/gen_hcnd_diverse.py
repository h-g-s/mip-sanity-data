#!/usr/bin/env python3
"""Curated set of "interesting" Hop-Constrained Network Design (HCND)
instances, selected from the gen_hcnd_search.py parameter-grid results
(/tmp/hcnd_search_report.json): all proven optimal in 15-66s wall time
with genuine branch-and-bound (196-9776 nodes), spanning n=14-16,
edge_prob=0.3-0.4, num_commodities=8-10, hop_limit=4.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hcnd_lib import build_layered_mps, write_mps_gz, solve_with_mipster, generate_instance

ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = ROOT / "mips"
TIME_LIMIT = 100

SPECS = [
    dict(n=16, edge_prob=0.30, num_commodities=8, hop_limit=4, seed=7),
    dict(n=14, edge_prob=0.40, num_commodities=10, hop_limit=4, seed=8),
    dict(n=15, edge_prob=0.35, num_commodities=8, hop_limit=4, seed=1),
    dict(n=16, edge_prob=0.40, num_commodities=10, hop_limit=4, seed=5),
    dict(n=14, edge_prob=0.40, num_commodities=8, hop_limit=4, seed=5),
    dict(n=16, edge_prob=0.40, num_commodities=8, hop_limit=4, seed=8),
    dict(n=16, edge_prob=0.35, num_commodities=10, hop_limit=4, seed=6),
    dict(n=15, edge_prob=0.40, num_commodities=10, hop_limit=4, seed=4),
    dict(n=15, edge_prob=0.35, num_commodities=10, hop_limit=4, seed=1),
    dict(n=16, edge_prob=0.35, num_commodities=10, hop_limit=4, seed=7),
    dict(n=15, edge_prob=0.40, num_commodities=8, hop_limit=4, seed=3),
    dict(n=16, edge_prob=0.30, num_commodities=10, hop_limit=4, seed=6),
    dict(n=16, edge_prob=0.40, num_commodities=10, hop_limit=4, seed=6),
    dict(n=16, edge_prob=0.35, num_commodities=8, hop_limit=4, seed=1),
    dict(n=15, edge_prob=0.40, num_commodities=10, hop_limit=4, seed=7),
]


def main():
    ok = 0
    for spec in SPECS:
        name = (f"hcnd_n{spec['n']}_ep{spec['edge_prob']}_k{spec['num_commodities']}"
                 f"_H{spec['hop_limit']}_sd{spec['seed']}")
        instance = generate_instance(spec["n"], spec["edge_prob"], spec["num_commodities"],
                                      spec["hop_limit"], spec["seed"])
        mps_text = build_layered_mps(name, instance)
        path = MIPS_DIR / f"{name}.mps.gz"
        write_mps_gz(mps_text, path)
        r = solve_with_mipster(path, TIME_LIMIT)
        ok += r["optimal"]
        print(f"{name:40s} optimal={r['optimal']!s:5} obj={r['obj']!s:>10} "
              f"nodes={r['nodes']!s:>6} wall={r['wall']:>6.2f}s")
    print(f"\n{ok}/{len(SPECS)} solved to optimality within {TIME_LIMIT}s")


if __name__ == "__main__":
    main()
