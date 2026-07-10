#!/usr/bin/env python3
"""
Generate curated "interesting" FCNF (Fixed-Charge Network Flow) instances.

These 15 instances were selected from a 432-combination parameter-grid
search (see gen_fcnf_search.py / /tmp/fcnf_search_report.json) over the
"random heterogeneous" topology (mixed fixed-cost-dominated and
variable-cost-dominated arcs). They require genuine branch-and-bound:
proven optimal within 15-90 seconds wall time with hundreds to thousands
of B&B nodes (not solved trivially at the root, unlike the baseline
fixtures).
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_fcnf_fixtures as G  # noqa: E402

# (n_nodes, deg, n_sources, n_sinks, slack, seed)
INSTANCES = [
    (50, 8, 2, 3, 0.95, 7),
    (50, 8, 4, 5, 0.95, 137),
    (50, 8, 2, 3, 0.9, 42),
    (50, 9, 4, 5, 0.95, 7),
    (55, 9, 4, 5, 0.99, 7),
    (55, 10, 4, 5, 0.99, 42),
    (55, 10, 2, 3, 0.99, 7),
    (55, 9, 4, 5, 0.9, 137),
    (50, 10, 2, 3, 0.99, 137),
    (50, 10, 4, 5, 0.99, 137),
    (55, 10, 4, 5, 0.9, 7),
    (55, 8, 4, 5, 0.99, 42),
    (55, 8, 4, 5, 0.95, 42),
    (55, 10, 3, 4, 0.95, 7),
    (55, 10, 3, 4, 0.99, 7),
]


def main():
    repo_root = Path(__file__).resolve().parents[2]
    mips_dir = repo_root / "mips"
    mips_dir.mkdir(exist_ok=True)

    for n_nodes, deg, n_sources, n_sinks, slack, seed in INSTANCES:
        name = f"fcnf_search_n{n_nodes}_d{deg}_s{n_sources}_{n_sinks}_sl{slack}_sd{seed}"
        rng = random.Random(seed)
        n, arcs, sup = G.build_random_heterogeneous(n_nodes, deg, rng,
                                                      n_sources=n_sources, n_sinks=n_sinks)
        scaled = G._scale_supplies_to_capacity(arcs, sup, slack=slack)
        if scaled is None:
            print(f"WARNING: {name} rescale failed, skipping", file=sys.stderr)
            continue

        gz_path = mips_dir / f"{name}.mps.gz"
        G.write_mps(name, n, arcs, scaled, str(gz_path))
        print(f"Written {gz_path} (arcs={len(arcs)})")


if __name__ == "__main__":
    main()
