#!/usr/bin/env python3
"""Search a QAP parameter grid for "interesting" instances.

QAP's linearized MPS formulation grows as O(n^4), so problem size is
the dominant difficulty knob -- n=8 with dense (uniform) flow is
already too hard to prove optimal within a couple of minutes, while
n=6-7 solve in well under a second for easy patterns. This script
explores n in {6,7,8} together with flow/distance patterns and seeds
to find combinations that land in the 15-90s "interesting" window
(non-trivial branching/cuts, not just root-node solves).

An instance is considered interesting when solving it with mipster:
  - reaches proven optimality within a target wall-clock window
    (default 15s - 90s), and
  - does not solve trivially at the root node (it should require
    branching and/or generate cutting planes).

Usage:
    python3 gen_qap_search.py [--min-time 15] [--max-time 90] \\
        [--min-nodes 20] [--jobs 7] [--time-limit 100]

Writes candidate .mps files to a scratch directory and prints a report.
It does NOT write into mips/ automatically -- promote the ones you
like with gen_qap_diverse.py.
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
from gen_qap_fixtures import generate_qap_instance, write_qap_mps

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
    cut_rounds = len(re.findall(r"^\s*\d+\s+\d+\s+\d+\s+\S", out, re.MULTILINE))

    return {
        "status": status,
        "obj": float(obj_m.group(1)) if obj_m else None,
        "nodes": int(nodes_m.group(1)) if nodes_m else None,
        "wall": float(wall_m.group(1)) if wall_m else None,
        "cut_rounds": cut_rounds,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-time", type=float, default=15.0)
    ap.add_argument("--max-time", type=float, default=90.0)
    ap.add_argument("--min-nodes", type=int, default=20)
    ap.add_argument("--time-limit", type=float, default=100.0)
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--out", default="/tmp/qap_search_report.json")
    args = ap.parse_args()

    grid = list(itertools.product(
        [6, 7, 8],                                  # n
        ["uniform", "sparse", "hub"],                # flow_type
        ["euclidean", "manhattan", "grid"],           # dist_type
        [1, 2, 3, 4],                                 # seed
    ))

    print(f"=== Searching {len(grid)} QAP parameter combinations "
          f"(jobs={args.jobs}, time_limit={args.time_limit}s) ===\n")

    tmpdir = tempfile.mkdtemp()
    tasks = []
    for (n, flow_type, dist_type, seed) in grid:
        name = f"qap_n{n}_{flow_type}_{dist_type}_s{seed}"
        f, d = generate_qap_instance(n, seed, flow_type, dist_type)
        mps_path = Path(tmpdir) / f"{name}.mps"
        write_qap_mps(str(mps_path), n, f, d)
        tasks.append((name, mps_path, n, flow_type, dist_type, seed))

    def worker(task):
        name, mps_path, n, flow_type, dist_type, seed = task
        stats = solve_with_mipster(mps_path, args.time_limit)
        stats.update(name=name, n=n, flow_type=flow_type,
                      dist_type=dist_type, seed=seed)
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
