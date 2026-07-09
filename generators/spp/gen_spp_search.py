#!/usr/bin/env python3
"""Search a Set Packing Problem (SPP) parameter grid for "interesting"
instances.

Like MIS (a special case of SPP where each set is an edge), mipster's
conflict-graph clique-cut machinery is extremely effective on
set-packing instances built from structured patterns: k_partite,
geometric, and scheduling all solve at the root node even with
thousands of elements/sets, because their clique structure is
captured almost entirely by cuts. Only "random" set-membership
patterns (each set a random subset of elements) resist this at large
enough scale (~300-450 elements, ~1500-2250 sets) -- this script
focuses the search there.

An instance is considered interesting when solving it with mipster:
  - reaches proven optimality within a target wall-clock window
    (default 15s - 90s), and
  - does not solve trivially at the root node (it should require
    branching), so LP relaxation, cut separation and branch-and-bound
    are all genuinely exercised.

Usage:
    python3 gen_spp_search.py [--min-time 15] [--max-time 90] \\
        [--min-nodes 20] [--jobs 7] [--time-limit 100]

Writes candidate .mps files to a scratch directory and prints a
report. It does NOT write into mips/ automatically -- promote the
ones you like with gen_spp_diverse.py.
"""

import argparse
import itertools
import json
import os
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_spp_fixtures import generate_spp_instance, write_spp_mps

MIPSTER_BIN = os.environ.get("MIPSTER_BIN") or (
    str(Path(os.environ["MIPSTER_PREFIX"]) / "bin" / "mipster")
    if "MIPSTER_PREFIX" in os.environ else "mipster"
)


def solve_with_mipster(mps_path, time_limit):
    """Run mipster on the instance and parse key solve statistics."""
    cmd = [MIPSTER_BIN, str(mps_path), "-sec", str(time_limit), "-solve"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                 timeout=time_limit + 30)
    except subprocess.TimeoutExpired:
        return {"status": "timeout_hard", "nodes": None, "obj": None, "wall": None}

    out = result.stdout

    status = "unknown"
    if "Optimal solution found" in out or "Optimal - objective value" in out:
        status = "optimal"
    elif "Stopped on time limit" in out:
        status = "time_limit"
    elif "infeasible" in out.lower():
        status = "infeasible"

    obj_m = re.search(r"Objective value:\s*([\-0-9.e]+)", out)
    nodes_m = re.search(r"Enumerated nodes:\s*([0-9]+)", out)
    wall_m = re.search(r"Total time \(Wallclock seconds\):\s*([0-9.]+)", out)

    return {
        "status": status,
        "obj": float(obj_m.group(1)) if obj_m else None,
        "nodes": int(nodes_m.group(1)) if nodes_m else None,
        "wall": float(wall_m.group(1)) if wall_m else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-time", type=float, default=15.0)
    ap.add_argument("--max-time", type=float, default=90.0)
    ap.add_argument("--min-nodes", type=int, default=20)
    ap.add_argument("--time-limit", type=float, default=100.0)
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--out", default="/tmp/spp_search_report.json")
    args = ap.parse_args()

    grid = list(itertools.product(
        [300, 350, 400, 450],          # n_elements
        [4, 5, 6],                     # sets_ratio (n_sets = n_elements * ratio)
        [50, 60, 70, 80],              # k (max set size)
        [1, 2, 3],                     # seed
    ))

    print(f"=== Searching {len(grid)} SPP parameter combinations "
          f"(jobs={args.jobs}, time_limit={args.time_limit}s) ===\n")

    tmpdir = tempfile.mkdtemp()
    tasks = []
    for (n_elem, ratio, k, seed) in grid:
        n_sets = n_elem * ratio
        name = f"spp_n{n_elem}_r{ratio}_k{k}_s{seed}"
        values, members = generate_spp_instance(n_elem, n_sets, seed, "random", k, "integer")
        mps_path = Path(tmpdir) / f"{name}.mps"
        write_spp_mps(str(mps_path), n_elem, n_sets, values, members)
        tasks.append((name, mps_path, n_elem, n_sets, k, seed))

    def worker(task):
        name, mps_path, n_elem, n_sets, k, seed = task
        stats = solve_with_mipster(mps_path, args.time_limit)
        stats.update(name=name, n_elements=n_elem, n_sets=n_sets, k=k, seed=seed)
        return stats

    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        for i, stats in enumerate(pool.map(worker, tasks)):
            results.append(stats)
            interesting = (
                stats["status"] == "optimal"
                and stats["wall"] is not None
                and args.min_time <= stats["wall"] <= args.max_time
                and stats["nodes"] is not None
                and stats["nodes"] >= args.min_nodes
            )
            flag = "*** INTERESTING ***" if interesting else ""
            print(f"[{i+1}/{len(tasks)}] {stats['name']}: status={stats['status']} "
                  f"nodes={stats['nodes']} wall={stats['wall']} obj={stats['obj']} {flag}")

    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)

    interesting = [r for r in results
                   if r["status"] == "optimal" and r["wall"] is not None
                   and args.min_time <= r["wall"] <= args.max_time
                   and r["nodes"] is not None and r["nodes"] >= args.min_nodes]

    print(f"\n=== {len(interesting)} interesting instances found out of {len(results)} ===")
    for r in sorted(interesting, key=lambda x: x["wall"]):
        print(f"  {r['name']}: nodes={r['nodes']} wall={r['wall']:.1f}s obj={r['obj']}")

    print(f"\nFull report written to {args.out}")
    print(f"Scratch .mps files kept in {tmpdir}")


if __name__ == "__main__":
    main()
