#!/usr/bin/env python3
"""Search a GAP parameter grid for "interesting" instances.

Unlike MIS/SPP (where mipster's clique cuts make almost every
structured pattern trivial), GAP's anti-correlated cost/weight
pattern already requires genuine branch-and-bound at the baseline
fixture sizes (n_agents=4-6, n_tasks=30-35): thousands to tens of
thousands of nodes. This script explores a size/tightness grid around
that region to find combinations landing in the 15-90s "interesting"
window. Only the "anticorr" cost_type is searched -- uniform/
structured/correlated/skewed cost types solve at or near the root
node even at these sizes (see baseline fixture results).

An instance is considered interesting when solving it with mipster:
  - reaches proven optimality within a target wall-clock window
    (default 15s - 90s), and
  - does not solve trivially at the root node (it should require
    branching), so LP relaxation, cut separation and branch-and-bound
    are all genuinely exercised.

Usage:
    python3 gen_gap_search.py [--min-time 15] [--max-time 90] \\
        [--min-nodes 20] [--jobs 7] [--time-limit 100]

Writes candidate .mps files to a scratch directory and prints a
report. It does NOT write into mips/ automatically -- promote the
ones you like with gen_gap_diverse.py.
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
from gen_gap_fixtures import generate_gap_instance, write_gap_mps, tightness_label

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
    ap.add_argument("--out", default="/tmp/gap_search_report.json")
    args = ap.parse_args()

    grid = list(itertools.product(
        [6, 7],                        # n_agents
        [30, 32, 35, 38],              # n_tasks
        [1.10, 1.12, 1.15],            # alpha (capacity tightness)
        ["variable", "heavy"],         # weight_type
        [1, 2, 3, 4],                  # seed
    ))

    print(f"=== Searching {len(grid)} GAP parameter combinations "
          f"(jobs={args.jobs}, time_limit={args.time_limit}s) ===\n")

    tmpdir = tempfile.mkdtemp()
    tasks = []
    for (n_ag, n_tk, alpha, wtype, seed) in grid:
        tag = tightness_label(alpha)
        name = f"gap_{n_ag}a{n_tk}t_sd{seed}_a{alpha}_anticorr_{wtype}"
        costs, weights, capacity = generate_gap_instance(n_ag, n_tk, seed, alpha, "anticorr", wtype)
        mps_path = Path(tmpdir) / f"{name}.mps"
        write_gap_mps(str(mps_path), n_ag, n_tk, costs, weights, capacity)
        tasks.append((name, mps_path, n_ag, n_tk, alpha, wtype, seed))

    def worker(task):
        name, mps_path, n_ag, n_tk, alpha, wtype, seed = task
        stats = solve_with_mipster(mps_path, args.time_limit)
        stats.update(name=name, n_agents=n_ag, n_tasks=n_tk, alpha=alpha,
                     weight_type=wtype, seed=seed)
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
