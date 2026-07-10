#!/usr/bin/env python3
"""
Generate curated "interesting" BPC (Bin Packing with Conflicts) instances.

These 14 instances were selected from a 540-combination parameter-grid
search (see gen_bpc_search.py / /tmp/bpc_search_report.json) to require
genuine branch-and-bound: proven optimal within 15-90 seconds wall time
with thousands to tens of thousands of B&B nodes (not solved trivially
at the root).
"""

import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gen_bpc_fixtures import generate_bpc_instance, write_bpc_mps  # noqa: E402

# (n_items, capacity, seed, conflict_pattern, conflict_density, weight_pattern)
INSTANCES = [
    (13, 120, 137, "random",    0.30, "uniform"),
    (13, 150, 137, "random",    0.20, "uniform"),
    (15, 100, 137, "random",    0.25, "uniform"),
    (13, 100, 42,  "bipartite", 0.20, "uniform"),
    (13, 100, 42,  "bipartite", 0.25, "uniform"),
    (13, 100, 42,  "bipartite", 0.30, "uniform"),
    (16, 150, 42,  "random",    0.25, "uniform"),
    (16, 100, 7,   "random",    0.30, "uniform"),
    (14, 150, 7,   "bipartite", 0.30, "uniform"),
    (15, 100, 137, "random",    0.20, "uniform"),
    (14, 100, 7,   "bipartite", 0.30, "uniform"),
    (16, 100, 7,   "random",    0.25, "uniform"),
    (14, 120, 7,   "bipartite", 0.30, "uniform"),
    (14, 120, 42,  "random",    0.20, "uniform"),
]


def main():
    repo_root = Path(__file__).resolve().parents[2]
    mips_dir = repo_root / "mips"
    mips_dir.mkdir(exist_ok=True)
    scratch = Path("/tmp/bpc_diverse_scratch")
    scratch.mkdir(exist_ok=True)

    for n_items, capacity, seed, conf_pat, conf_dens, weight_pat in INSTANCES:
        name = (f"bpc_search_n{n_items}_c{capacity}_sd{seed}_{conf_pat}"
                 f"_d{conf_dens}_{weight_pat}")
        weights, conflicts = generate_bpc_instance(
            n_items, capacity, seed, conf_pat, conf_dens, weight_pat
        )
        mps_path = str(scratch / f"{name}.mps")
        write_bpc_mps(mps_path, n_items, capacity, weights, conflicts)

        gz_path = mips_dir / f"{name}.mps.gz"
        with open(mps_path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                f_out.writelines(f_in)
        print(f"Written {gz_path} (conflicts={len(conflicts)})")


if __name__ == "__main__":
    main()
