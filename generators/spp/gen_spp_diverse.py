#!/usr/bin/env python3
"""Regenerate the curated "interesting" SPP instances selected from the
parameter-grid search (see gen_spp_search.py / /tmp/spp_search_report.json)
directly into the repo's mips/ directory.

Each instance below was found by the grid search to reach proven
optimality in roughly 15-90s wall-clock time while requiring genuine
branch-and-bound (not solved trivially at the root), using the
"random" set-membership pattern -- the only one that resists
mipster's clique-cut machinery at this scale.
"""

import gzip
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_spp_fixtures import generate_spp_instance, write_spp_mps

# (suffix, n_elements, ratio, k, seed) -- n_sets = n_elements * ratio
INSTANCES = [
    ("n400_r5_k80_s2", 400, 5, 80, 2),
    ("n300_r4_k50_s2", 300, 4, 50, 2),
    ("n300_r6_k70_s3", 300, 6, 70, 3),
    ("n350_r4_k50_s1", 350, 4, 50, 1),
    ("n400_r6_k60_s1", 400, 6, 60, 1),
    ("n350_r6_k80_s3", 350, 6, 80, 3),
    ("n450_r6_k60_s1", 450, 6, 60, 1),
    ("n400_r4_k50_s3", 400, 4, 50, 3),
    ("n350_r4_k80_s3", 350, 4, 80, 3),
    ("n450_r4_k80_s3", 450, 4, 80, 3),
    ("n450_r5_k70_s3", 450, 5, 70, 3),
    ("n450_r6_k70_s1", 450, 6, 70, 1),
    ("n400_r6_k70_s3", 400, 6, 70, 3),
    ("n450_r5_k50_s1", 450, 5, 50, 1),
    ("n450_r5_k50_s3", 450, 5, 50, 3),
]


def main():
    repo_root = Path(__file__).resolve().parents[2]
    fixture_dir = repo_root / "mips"
    fixture_dir.mkdir(exist_ok=True)

    print(f"=== Generating {len(INSTANCES)} curated SPP instances ===\n")

    for suffix, n_elem, ratio, k, seed in INSTANCES:
        n_sets = n_elem * ratio
        name = f"spp_search_{suffix}"
        values, members = generate_spp_instance(n_elem, n_sets, seed, "random", k, "integer")

        with tempfile.NamedTemporaryFile(suffix=".mps", delete=False) as tmp:
            mps_path = tmp.name
        write_spp_mps(mps_path, n_elem, n_sets, values, members)

        gz_path = fixture_dir / f"{name}.mps.gz"
        with open(mps_path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                f_out.writelines(f_in)
        Path(mps_path).unlink(missing_ok=True)

        print(f"  {name}: written to {gz_path}")

    print(f"\n=== Generated {len(INSTANCES)} instances ===")


if __name__ == "__main__":
    main()
