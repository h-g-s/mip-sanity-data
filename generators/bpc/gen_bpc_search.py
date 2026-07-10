#!/usr/bin/env python3
"""
Parameter-grid search harness for Bin Packing with Conflicts (BPC) instances.

Explores (n_items, capacity, conflict_pattern, conflict_density, weight_pattern, seed)
combinations, solving each with mipster under a time limit, and classifies
instances as "interesting" if:
  - solver proves optimality
  - wall time falls in [MIN_TIME, MAX_TIME] seconds
  - node count indicates genuine branch-and-bound (not a root-node solve)

Writes a JSON report to /tmp/bpc_search_report.json for later curation via
gen_bpc_diverse.py.
"""

import json
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from gen_bpc_fixtures import generate_bpc_instance, write_bpc_mps  # noqa: E402

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")
TIME_LIMIT = 100
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 20

SCRATCH = Path("/tmp/bpc_search_scratch")
SCRATCH.mkdir(exist_ok=True)


def solve_one(n_items, capacity, seed, conf_pat, conf_dens, weight_pat):
    weights, conflicts = generate_bpc_instance(
        n_items, capacity, seed, conf_pat, conf_dens, weight_pat
    )
    name = f"bpc_n{n_items}_c{capacity}_sd{seed}_{conf_pat}_{conf_dens}_{weight_pat}"
    mps_path = str(SCRATCH / f"{name}.mps")
    write_bpc_mps(mps_path, n_items, capacity, weights, conflicts)

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
        "n_items": n_items, "capacity": capacity, "seed": seed,
        "conflict_pattern": conf_pat, "conflict_density": conf_dens,
        "weight_pattern": weight_pat,
        "obj": obj, "nodes": nodes, "optimal": optimal, "wall": round(wall, 2),
        "num_conflicts": len(conflicts),
        "interesting": interesting,
    }


def main():
    combos = []
    for n_items in [12, 13, 14, 15, 16]:
        for capacity in [100, 120, 150]:
            for conf_pat in ["random", "geometric", "bipartite"]:
                for conf_dens in [0.15, 0.2, 0.25, 0.3]:
                    for seed in [42, 137, 7]:
                        combos.append((n_items, capacity, seed, conf_pat, conf_dens, "uniform"))

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
            print(f"[{done}/{len(combos)}] n={r['n_items']} c={r['capacity']} sd={r['seed']} "
                  f"pat={r['conflict_pattern']} dens={r['conflict_density']} "
                  f"conflicts={r['num_conflicts']} -> obj={r['obj']} nodes={r['nodes']} "
                  f"optimal={r['optimal']} wall={r['wall']}s{tag}", flush=True)

    interesting = [r for r in results if r["interesting"]]
    print(f"\nFound {len(interesting)} interesting out of {len(combos)}")

    with open("/tmp/bpc_search_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Report written to /tmp/bpc_search_report.json")


if __name__ == "__main__":
    main()
