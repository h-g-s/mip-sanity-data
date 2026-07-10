#!/usr/bin/env python3
"""
Parameter-grid search harness for Steiner Tree instances.

Explores complete graphs with random edge costs (generate_complete_graph
with cost_type="random"), which is the only topology among the Steiner
generators that reliably produces genuine branch-and-bound at moderate
scale. Sparse random and geometric graphs tend to be either trivial
(root-node solve) or intractable (disconnected/very hard), so the search
here focuses on complete graphs varying node count and terminal count.

Solves each candidate with mipster under a time limit and classifies
instances as "interesting" if:
  - solver proves optimality
  - wall time falls in [MIN_TIME, MAX_TIME] seconds
  - node count indicates genuine branch-and-bound (not a root-node solve)

Writes a JSON report to /tmp/steiner_search_report.json for later curation
via gen_steiner_diverse.py.
"""

import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_steiner_fixtures as G  # noqa: E402

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")
TIME_LIMIT = 100
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 20

SCRATCH = Path("/tmp/steiner_search_scratch")
SCRATCH.mkdir(exist_ok=True)


def solve_one(n_nodes, n_terminals, seed):
    nodes, edges, edge_costs = G.generate_complete_graph(n_nodes, "random", seed)
    root = 0
    terminals = G.select_terminals(nodes, n_terminals, root, seed)

    name = f"steiner_complete{n_nodes}_t{n_terminals}_sd{seed}"
    mps_path = str(SCRATCH / f"{name}.mps.gz")
    G.generate_steiner_mps(name, nodes, edges, edge_costs, root, terminals, mps_path)

    t0 = time.time()
    try:
        proc = subprocess.run(
            [MIPSTER, mps_path, "-sec", str(TIME_LIMIT), "-solve"],
            capture_output=True, text=True, timeout=TIME_LIMIT + 30,
        )
        out = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        out = ""
    wall = time.time() - t0

    obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
    nodes_m = re.search(r"Enumerated nodes:\s*(\d+)", out)
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    b_nodes = int(nodes_m.group(1)) if nodes_m else None

    interesting = bool(
        optimal and obj is not None and b_nodes is not None
        and MIN_TIME <= wall <= MAX_TIME and b_nodes >= MIN_NODES
    )

    Path(mps_path).unlink(missing_ok=True)

    return {
        "n_nodes": n_nodes, "n_terminals": n_terminals, "seed": seed,
        "n_edges": len(edges),
        "obj": obj, "nodes": b_nodes, "optimal": optimal, "wall": round(wall, 2),
        "interesting": interesting,
    }


def main():
    combos = []
    for n_nodes in [16, 18, 20, 22, 24]:
        for n_terminals in [6, 7, 8, 9, 10]:
            for seed in [42, 137, 7, 99, 21]:
                combos.append((n_nodes, n_terminals, seed))

    print(f"Total combinations: {len(combos)}", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = {ex.submit(solve_one, *c): c for c in combos}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            done += 1
            tag = " *** INTERESTING ***" if r["interesting"] else ""
            print(f"[{done}/{len(combos)}] n={r['n_nodes']} t={r['n_terminals']} sd={r['seed']} "
                  f"edges={r['n_edges']} -> obj={r['obj']} nodes={r['nodes']} "
                  f"optimal={r['optimal']} wall={r['wall']}s{tag}", flush=True)

    interesting = [r for r in results if r["interesting"]]
    print(f"\nFound {len(interesting)} interesting out of {len(combos)}")

    with open("/tmp/steiner_search_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Report written to /tmp/steiner_search_report.json")


if __name__ == "__main__":
    main()
