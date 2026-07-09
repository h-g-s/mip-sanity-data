#!/usr/bin/env python3
"""Regenerate the curated "interesting" GAP instances selected from the
parameter-grid search (see gen_gap_search.py / /tmp/gap_search_report.json)
directly into the repo's mips/ directory.

Each instance below was found by the grid search to reach proven
optimality in roughly 15-90s wall-clock time while requiring genuine
branch-and-bound (11000-55000+ nodes), using the "anticorr" cost_type
-- the only one that resists mipster's cuts/preprocessing at this
scale (uniform/structured/correlated/skewed cost types solve near the
root node, see baseline fixtures).
"""

import gzip
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_gap_fixtures import generate_gap_instance, write_gap_mps

# (suffix, n_agents, n_tasks, alpha, weight_type, seed)
INSTANCES = [
    ("7a30t_sd3_a1.15_variable",  7, 30, 1.15, "variable", 3),
    ("6a35t_sd3_a1.1_heavy",      6, 35, 1.10, "heavy",    3),
    ("6a38t_sd1_a1.12_heavy",     6, 38, 1.12, "heavy",    1),
    ("6a30t_sd1_a1.12_heavy",     6, 30, 1.12, "heavy",    1),
    ("7a38t_sd2_a1.1_variable",   7, 38, 1.10, "variable", 2),
    ("7a32t_sd4_a1.1_variable",   7, 32, 1.10, "variable", 4),
    ("6a30t_sd2_a1.1_heavy",      6, 30, 1.10, "heavy",    2),
    ("7a35t_sd4_a1.1_heavy",      7, 35, 1.10, "heavy",    4),
    ("6a32t_sd1_a1.1_heavy",      6, 32, 1.10, "heavy",    1),
    ("7a38t_sd3_a1.12_variable",  7, 38, 1.12, "variable", 3),
    ("7a30t_sd1_a1.1_variable",   7, 30, 1.10, "variable", 1),
    ("6a35t_sd2_a1.1_heavy",      6, 35, 1.10, "heavy",    2),
    ("7a35t_sd2_a1.12_variable",  7, 35, 1.12, "variable", 2),
    ("6a35t_sd3_a1.12_variable",  6, 35, 1.12, "variable", 3),
    ("7a30t_sd3_a1.12_heavy",     7, 30, 1.12, "heavy",    3),
]


def main():
    repo_root = Path(__file__).resolve().parents[2]
    fixture_dir = repo_root / "mips"
    fixture_dir.mkdir(exist_ok=True)

    print(f"=== Generating {len(INSTANCES)} curated GAP instances ===\n")

    for suffix, n_ag, n_tk, alpha, wtype, seed in INSTANCES:
        name = f"gap_search_{suffix}"
        costs, weights, capacity = generate_gap_instance(n_ag, n_tk, seed, alpha, "anticorr", wtype)

        with tempfile.NamedTemporaryFile(suffix=".mps", delete=False) as tmp:
            mps_path = tmp.name
        write_gap_mps(mps_path, n_ag, n_tk, costs, weights, capacity)

        gz_path = fixture_dir / f"{name}.mps.gz"
        with open(mps_path, 'rb') as f_in:
            with gzip.open(gz_path, 'wb') as f_out:
                f_out.writelines(f_in)
        Path(mps_path).unlink(missing_ok=True)

        print(f"  {name}: written to {gz_path}")

    print(f"\n=== Generated {len(INSTANCES)} instances ===")


if __name__ == "__main__":
    main()
