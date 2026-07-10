#!/usr/bin/env python3
"""Generate a curated set of 'interesting' Steiner tree instances.

These (n_nodes, n_terminals, seed) tuples were selected from a 125-combo
parameter-grid search (see gen_steiner_search.py) as instances that:
  - are proven optimal by mipster within roughly 15-90 seconds
  - require genuine branch-and-bound (hundreds to tens of thousands of nodes)

All instances use complete graphs with random integer edge costs, which
was found to reliably produce this difficulty profile (see gen_steiner_search.py
exploration notes).
"""

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_steiner_fixtures as G  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent.parent
MIPS_DIR = REPO_ROOT / "mips"
MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")

# (n_nodes, n_terminals, seed) tuples selected for diversity across
# n_nodes, n_terminals, and wall-clock time (~15-90s in original search).
DIVERSE_INSTANCES = [
    (20, 8, 7),
    (16, 10, 21),
    (22, 9, 137),
    (24, 6, 42),
    (18, 8, 21),
    (20, 7, 99),
    (18, 10, 99),
    (20, 10, 21),
    (22, 6, 42),
    (24, 7, 42),
    (22, 8, 21),
    (24, 8, 137),
    (20, 9, 7),
    (22, 9, 21),
    (24, 9, 137),
]


def main():
    MIPS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for n_nodes, n_terminals, seed in DIVERSE_INSTANCES:
        name = f"steiner_search_n{n_nodes}_t{n_terminals}_sd{seed}"
        print(f"Generating {name}...")
        nodes, edges, edge_costs = G.generate_complete_graph(n_nodes, "random", seed)
        root = 0
        terminals = G.select_terminals(nodes, n_terminals, root, seed)

        mps_path = str(MIPS_DIR / f"{name}.mps.gz")
        G.generate_steiner_mps(name, nodes, edges, edge_costs, root, terminals, mps_path)

        proc = subprocess.run(
            [MIPSTER, mps_path, "-sec", "120", "-solve"],
            capture_output=True, text=True, timeout=150,
        )
        out = proc.stdout + proc.stderr
        obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
        optimal = "Optimal solution found" in out
        obj = float(obj_m.group(1)) if obj_m else None
        print(f"  -> obj={obj} optimal={optimal}")
        results.append((name, obj, optimal))

    print("\nSummary:")
    for name, obj, optimal in results:
        print(f"  {name}: obj={obj} optimal={optimal}")


if __name__ == "__main__":
    main()
