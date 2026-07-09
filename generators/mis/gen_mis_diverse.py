#!/usr/bin/env python3
"""Regenerate the curated set of "interesting" MIS instances.

These 15 instances were selected from a 225-combination parameter grid
search (see gen_mis_search.py) as ones that mipster proves optimal
within roughly 15-80s while still requiring real branch-and-bound
(tens to thousands of nodes). Only "random" (Erdos-Renyi) graphs
resist mipster's clique-cut machinery enough to be interesting at a
practical vertex count -- geometric, k-partite, grid, tree, cycle and
planar patterns all solve at the root node even with hundreds of
vertices. These instances span n in {90,100,110,120,130}, edge
probability in {0.2-0.4}, and all three weight distributions (uniform,
unit, diverse) for good code-path diversity.

Writes directly into mips/ as mis_search_<name>.mps.gz.
"""

import gzip
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_mis_fixtures import generate_mis_instance, write_mis_mps

# (name, n, edge_prob, weight_type, seed)
INSTANCES = [
    ("n90_ep0.25_unit_s3", 90, 0.25, "unit", 3),
    ("n100_ep0.4_diverse_s1", 100, 0.4, "diverse", 1),
    ("n110_ep0.25_uniform_s1", 110, 0.25, "uniform", 1),
    ("n90_ep0.35_unit_s2", 90, 0.35, "unit", 2),
    ("n100_ep0.35_uniform_s1", 100, 0.35, "uniform", 1),
    ("n120_ep0.25_diverse_s1", 120, 0.25, "diverse", 1),
    ("n130_ep0.2_diverse_s3", 130, 0.2, "diverse", 3),
    ("n110_ep0.2_uniform_s2", 110, 0.2, "uniform", 2),
    ("n100_ep0.25_unit_s2", 100, 0.25, "unit", 2),
    ("n130_ep0.2_uniform_s1", 130, 0.2, "uniform", 1),
    ("n100_ep0.4_unit_s3", 100, 0.4, "unit", 3),
    ("n120_ep0.3_uniform_s2", 120, 0.3, "uniform", 2),
    ("n110_ep0.2_unit_s2", 110, 0.2, "unit", 2),
    ("n130_ep0.3_uniform_s3", 130, 0.3, "uniform", 3),
    ("n120_ep0.4_unit_s2", 120, 0.4, "unit", 2),
]


def main():
    repo_root = Path(__file__).resolve().parents[2]
    mips_dir = repo_root / "mips"
    mips_dir.mkdir(exist_ok=True)

    print(f"=== Generating {len(INSTANCES)} curated MIS instances ===\n")
    for (suffix, n, edge_prob, weight_type, seed) in INSTANCES:
        name = f"mis_search_{suffix}"
        weights, edges = generate_mis_instance(n, seed, "random", edge_prob, weight_type)

        mps_path = mips_dir / f"{name}.mps"
        write_mis_mps(str(mps_path), n, weights, edges)

        gz_path = mips_dir / f"{name}.mps.gz"
        with open(mps_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            f_out.writelines(f_in)
        mps_path.unlink()

        print(f"  {name}: written to {gz_path}")

    print(f"\n=== Generated {len(INSTANCES)} instances ===")


if __name__ == "__main__":
    main()
