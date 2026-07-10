#!/usr/bin/env python3
"""
Parameter-grid search harness for Fixed-Charge Network Flow (FCNF) instances.

Explores the "random heterogeneous" topology (build_random_heterogeneous),
which mixes fixed-cost-dominated and variable-cost-dominated arcs and is
the only topology among the FCNF generators that reliably produces
genuine branch-and-bound at moderate scale (n=40-55 nodes, avg out-degree
7-10, tight capacity slack).

Solves each candidate with mipster under a time limit and classifies
instances as "interesting" if:
  - solver proves optimality
  - wall time falls in [MIN_TIME, MAX_TIME] seconds
  - node count indicates genuine branch-and-bound (not a root-node solve)

Writes a JSON report to /tmp/fcnf_search_report.json for later curation via
gen_fcnf_diverse.py.
"""

import json
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_fcnf_fixtures as G  # noqa: E402

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")
TIME_LIMIT = 100
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 20

SCRATCH = Path("/tmp/fcnf_search_scratch")
SCRATCH.mkdir(exist_ok=True)


def solve_one(n_nodes, deg, n_sources, n_sinks, slack, seed):
    rng = random.Random(seed)
    n, arcs, sup = G.build_random_heterogeneous(n_nodes, deg, rng,
                                                 n_sources=n_sources, n_sinks=n_sinks)
    scaled = G._scale_supplies_to_capacity(arcs, sup, slack=slack)
    if scaled is None:
        return None

    name = f"fcnf_n{n_nodes}_d{deg}_s{n_sources}_{n_sinks}_sl{slack}_sd{seed}"
    mps_path = str(SCRATCH / f"{name}.mps.gz")
    G.write_mps(name, n, arcs, scaled, mps_path)

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
    nodes = int(nodes_m.group(1)) if nodes_m else None

    interesting = bool(
        optimal and obj is not None and nodes is not None
        and MIN_TIME <= wall <= MAX_TIME and nodes >= MIN_NODES
    )

    Path(mps_path).unlink(missing_ok=True)

    return {
        "n_nodes": n_nodes, "deg": deg, "n_sources": n_sources, "n_sinks": n_sinks,
        "slack": slack, "seed": seed, "n_arcs": len(arcs),
        "obj": obj, "nodes": nodes, "optimal": optimal, "wall": round(wall, 2),
        "interesting": interesting,
    }


def main():
    combos = []
    for n_nodes in [40, 45, 50, 55]:
        for deg in [7, 8, 9, 10]:
            for n_sources, n_sinks in [(2, 3), (3, 4), (4, 5)]:
                for slack in [0.9, 0.95, 0.99]:
                    for seed in [42, 137, 7]:
                        combos.append((n_nodes, deg, n_sources, n_sinks, slack, seed))

    print(f"Total combinations: {len(combos)}", flush=True)

    results = []
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = {ex.submit(solve_one, *c): c for c in combos}
        done = 0
        for fut in as_completed(futs):
            r = fut.result()
            done += 1
            if r is None:
                continue
            results.append(r)
            tag = " *** INTERESTING ***" if r["interesting"] else ""
            print(f"[{done}/{len(combos)}] n={r['n_nodes']} deg={r['deg']} "
                  f"s={r['n_sources']}/{r['n_sinks']} slack={r['slack']} sd={r['seed']} "
                  f"arcs={r['n_arcs']} -> obj={r['obj']} nodes={r['nodes']} "
                  f"optimal={r['optimal']} wall={r['wall']}s{tag}", flush=True)

    interesting = [r for r in results if r["interesting"]]
    print(f"\nFound {len(interesting)} interesting out of {len(combos)}")

    with open("/tmp/fcnf_search_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Report written to /tmp/fcnf_search_report.json")


if __name__ == "__main__":
    main()
