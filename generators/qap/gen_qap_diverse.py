#!/usr/bin/env python3
"""Regenerate the curated set of "interesting" QAP instances.

These 12 instances were selected from a 108-combination parameter grid
search (see gen_qap_search.py) as ones that mipster proves optimal
within roughly 15-90s while still requiring substantial branch-and-
bound (hundreds to tens of thousands of nodes), so LP relaxation, cut
generation and branching are all genuinely exercised. QAP's linearized
MPS formulation grows as O(n^4), so n=8 with dense/uniform flow is
already too hard within this window -- these instances span n in
{7,8} together with all three flow patterns (uniform, sparse, hub) and
all three distance patterns (euclidean, manhattan, grid) for good
code-path diversity.

Writes directly into mips/ as qap_search_<name>.mps.gz.
"""

import gzip
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_qap_fixtures import generate_qap_instance, write_qap_mps

# (name, n, flow_type, dist_type, seed)
INSTANCES = [
    ("n7_hub_grid_s1", 7, "hub", "grid", 1),
    ("n7_hub_manhattan_s3", 7, "hub", "manhattan", 3),
    ("n8_sparse_manhattan_s1", 8, "sparse", "manhattan", 1),
    ("n7_hub_euclidean_s4", 7, "hub", "euclidean", 4),
    ("n8_sparse_grid_s4", 8, "sparse", "grid", 4),
    ("n7_hub_euclidean_s3", 7, "hub", "euclidean", 3),
    ("n7_uniform_manhattan_s3", 7, "uniform", "manhattan", 3),
    ("n7_uniform_grid_s2", 7, "uniform", "grid", 2),
    ("n7_uniform_manhattan_s1", 7, "uniform", "manhattan", 1),
    ("n7_hub_grid_s2", 7, "hub", "grid", 2),
    ("n8_hub_grid_s3", 8, "hub", "grid", 3),
    ("n8_hub_euclidean_s1", 8, "hub", "euclidean", 1),
]


def main():
    repo_root = Path(__file__).resolve().parents[2]
    mips_dir = repo_root / "mips"
    mips_dir.mkdir(exist_ok=True)

    print(f"=== Generating {len(INSTANCES)} curated QAP instances ===\n")
    for (suffix, n, flow_type, dist_type, seed) in INSTANCES:
        name = f"qap_search_{suffix}"
        f, d = generate_qap_instance(n, seed, flow_type, dist_type)

        mps_path = mips_dir / f"{name}.mps"
        write_qap_mps(str(mps_path), n, f, d)

        gz_path = mips_dir / f"{name}.mps.gz"
        with open(mps_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
            f_out.writelines(f_in)
        mps_path.unlink()

        print(f"  {name}: written to {gz_path}")

    print(f"\n=== Generated {len(INSTANCES)} instances ===")


if __name__ == "__main__":
    main()
