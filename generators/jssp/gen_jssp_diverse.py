#!/usr/bin/env python3
"""Regenerate the curated set of "interesting" JSSP instances.

These 15 instances were selected from a 324-combination parameter grid
search (see gen_jssp_search.py) as ones that mipster proves optimal
within roughly 15-60s while still requiring substantial branch-and-bound
(thousands to hundreds of thousands of nodes), so LP relaxation, cut
generation and branching are all genuinely exercised. They span a range
of job/machine counts (7-9 jobs, 5-7 machines) and processing-time
distributions (uniform, skewed, bimodal) for good code-path diversity.

Writes directly into mips/ as jssp_search_<name>.mps.gz.
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_jssp_fixtures import generate_jssp_mps
from gen_jssp_search import build_instance

# (name, n_jobs, n_machines, pt_low, pt_high, pt_pattern, seed)
INSTANCES = [
    ("n7_m7_bimodal_pt1-20_s1", 7, 7, 1, 20, "bimodal", 1),
    ("n8_m5_uniform_pt1-20_s3", 8, 5, 1, 20, "uniform", 3),
    ("n9_m7_skewed_pt1-50_s3", 9, 7, 1, 50, "skewed", 3),
    ("n7_m7_uniform_pt1-99_s3", 7, 7, 1, 99, "uniform", 3),
    ("n8_m6_bimodal_pt1-99_s1", 8, 6, 1, 99, "bimodal", 1),
    ("n9_m5_bimodal_pt1-50_s2", 9, 5, 1, 50, "bimodal", 2),
    ("n8_m6_skewed_pt1-20_s2", 8, 6, 1, 20, "skewed", 2),
    ("n7_m5_uniform_pt1-20_s2", 7, 5, 1, 20, "uniform", 2),
    ("n7_m7_uniform_pt1-20_s2", 7, 7, 1, 20, "uniform", 2),
    ("n9_m6_skewed_pt1-20_s3", 9, 6, 1, 20, "skewed", 3),
    ("n7_m6_uniform_pt1-20_s1", 7, 6, 1, 20, "uniform", 1),
    ("n9_m5_skewed_pt1-50_s1", 9, 5, 1, 50, "skewed", 1),
    ("n8_m7_skewed_pt1-50_s2", 8, 7, 1, 50, "skewed", 2),
    ("n9_m7_skewed_pt1-20_s3", 9, 7, 1, 20, "skewed", 3),
    ("n9_m7_bimodal_pt1-99_s2", 9, 7, 1, 99, "bimodal", 2),
]


def main():
    repo_root = Path(__file__).resolve().parents[2]
    mips_dir = repo_root / "mips"
    mips_dir.mkdir(exist_ok=True)

    print(f"=== Generating {len(INSTANCES)} curated JSSP instances ===\n")
    for (suffix, n_jobs, n_machines, pt_low, pt_high, pt_pattern, seed) in INSTANCES:
        name = f"jssp_search_{suffix}"
        jobs = build_instance(n_jobs, n_machines, pt_low, pt_high, pt_pattern, seed)
        mps_path = mips_dir / f"{name}.mps.gz"
        generate_jssp_mps(name, n_jobs, n_machines, jobs, mps_path)
        print(f"  {name}: written to {mps_path}")

    print(f"\n=== Generated {len(INSTANCES)} instances ===")


if __name__ == "__main__":
    main()
