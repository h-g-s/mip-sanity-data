#!/usr/bin/env python3
"""Generate a curated set of "interesting" CVRP instances.

Unlike the baseline fixtures in gen_vrp_fixtures.py / gen_diverse_vrp.py /
gen_cvrp_working.py, the instances below were not picked arbitrarily: they
were selected from a ~300-combination parameter-grid search (see
gen_cvrp_search.py) specifically because mipster:

  - proves optimality within a 10s-45s wall-clock window (not trivial,
    not too slow for quick regression/debugging use), and
  - requires substantial branch-and-bound work to get there (thousands to
    tens of thousands of nodes), so the LP relaxation, cut separation
    (2-MIR, Gomory, probing, path, clique, ...) and branching code paths
    are all genuinely exercised rather than solved at the root node.

Regenerate with:
    python3 gen_cvrp_diverse.py
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_cvrp_search import build_instance
from gen_vrp_fixtures import MIPS_DIR, write_cvrp_mps

# (name, n_customers, k_vehicles, cap_factor, demand_pattern, pos_pattern, seed)
# Selected from the search report: proven-optimal wall time 10s-45s with
# >=1800 B&B nodes on the reference machine (mipster, single thread).
INSTANCES = [
    ("cvrp_search_n10_k2_varied_uniform",     10, 2, 1.3,  "varied",  "uniform",   42),
    ("cvrp_search_n12_k2_skewed_clustered",   12, 2, 1.15, "skewed",  "clustered", 42),
    ("cvrp_search_n14_k2_uniform_clustered",  14, 2, 1.3,  "uniform", "clustered", 42),
    ("cvrp_search_n10_k3_skewed_uniform",     10, 3, 1.15, "skewed",  "uniform",   42),
    ("cvrp_search_n10_k2_skewed_uniform_b",   10, 2, 1.15, "skewed",  "uniform",   137),
    ("cvrp_search_n12_k2_varied_uniform",     12, 2, 1.3,  "varied",  "uniform",   42),
    ("cvrp_search_n10_k2_uniform_clustered",  10, 2, 1.0,  "uniform", "clustered", 42),
    ("cvrp_search_n14_k2_varied_clustered",   14, 2, 1.15, "varied",  "clustered", 42),
    ("cvrp_search_n12_k3_uniform_clustered",  12, 3, 1.15, "uniform", "clustered", 42),
    ("cvrp_search_n10_k2_uniform_clustered_b",10, 2, 1.15, "uniform", "clustered", 137),
    ("cvrp_search_n12_k2_varied_uniform_b",   12, 2, 1.15, "varied",  "uniform",   42),
    ("cvrp_search_n10_k3_uniform_uniform",    10, 3, 1.15, "uniform", "uniform",   42),
]


def main():
    MIPS_DIR.mkdir(exist_ok=True)
    for name, n, k, capf, dpat, ppat, seed in INSTANCES:
        customers, Q, demands, costs = build_instance(
            n, k, capf, dpat, ppat, "euclidean", seed)
        desc = (f"Search-selected CVRP: n={n} k={k} cap_factor={capf} "
                f"demand={dpat} pos={ppat} seed={seed}")
        write_cvrp_mps(name, k, customers, Q, demands, costs, desc)

    print(f"\n=== Generated {len(INSTANCES)} curated CVRP instances ===")


if __name__ == "__main__":
    main()
