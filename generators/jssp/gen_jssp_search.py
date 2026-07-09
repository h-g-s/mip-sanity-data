#!/usr/bin/env python3
"""Search a JSSP parameter grid for "interesting" instances.

An instance is considered interesting when solving it with mipster:
  - reaches proven optimality within a target wall-clock window
    (default 15s - 120s), and
  - does not solve trivially at the root node (it should require
    branching and/or generate cutting planes), so the test actually
    exercises LP relaxation, cut separation and branch-and-bound.

Usage:
    python3 gen_jssp_search.py [--min-time 15] [--max-time 120] \\
        [--min-nodes 20] [--jobs 7] [--time-limit 150]

Writes candidate .mps.gz files (via the disjunctive/big-M formulation
in gen_jssp_fixtures.py) to a scratch directory and prints a report of
which ones are "interesting" per the criteria above. It does NOT write
into mips/ automatically -- promote the ones you like with
gen_jssp_diverse.py.
"""

import argparse
import itertools
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_jssp_fixtures import generate_jssp_mps

MIPSTER_BIN = os.environ.get("MIPSTER_BIN") or (
    str(Path(os.environ["MIPSTER_PREFIX"]) / "bin" / "mipster")
    if "MIPSTER_PREFIX" in os.environ else "mipster"
)


def build_instance(n_jobs, n_machines, pt_low, pt_high, pt_pattern, seed):
    """Build a random JSSP instance: each job visits every machine exactly
    once, in a random order; processing times drawn per pt_pattern."""
    rng = random.Random(seed)
    jobs = []
    for j in range(n_jobs):
        machine_order = list(range(n_machines))
        rng.shuffle(machine_order)

        if pt_pattern == "uniform":
            times = [rng.randint(pt_low, pt_high) for _ in machine_order]
        elif pt_pattern == "skewed":
            # A few long operations, most short -- creates imbalance that
            # tends to force more interesting branching on machine order.
            times = []
            for _ in machine_order:
                if rng.random() < 0.2:
                    times.append(rng.randint(pt_high, pt_high * 3))
                else:
                    times.append(rng.randint(pt_low, pt_high // 2))
        elif pt_pattern == "bimodal":
            times = [rng.choice([rng.randint(pt_low, pt_low + 5),
                                  rng.randint(pt_high - 5, pt_high)])
                     for _ in machine_order]
        else:
            raise ValueError(f"unknown pt_pattern {pt_pattern}")

        jobs.append(list(zip(machine_order, times)))

    return jobs


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
    ap.add_argument("--max-time", type=float, default=120.0)
    ap.add_argument("--min-nodes", type=int, default=20)
    ap.add_argument("--time-limit", type=float, default=60.0)
    ap.add_argument("--jobs", type=int, default=7)
    ap.add_argument("--out", default="/tmp/jssp_search_report.json")
    args = ap.parse_args()

    grid = list(itertools.product(
        [6, 7, 8, 9],                  # n_jobs
        [5, 6, 7],                     # n_machines
        [(1, 20), (1, 50), (1, 99)],   # (pt_low, pt_high)
        ["uniform", "skewed", "bimodal"],  # pt_pattern
        [1, 2, 3],                     # seed
    ))

    print(f"=== Searching {len(grid)} JSSP parameter combinations "
          f"(jobs={args.jobs}, time_limit={args.time_limit}s) ===\n")

    tmpdir = tempfile.mkdtemp()
    tasks = []
    for (n_jobs, n_machines, (pt_low, pt_high), pt_pattern, seed) in grid:
        name = f"jssp_n{n_jobs}_m{n_machines}_{pt_pattern}_pt{pt_low}-{pt_high}_s{seed}"
        jobs = build_instance(n_jobs, n_machines, pt_low, pt_high, pt_pattern, seed)
        mps_path = Path(tmpdir) / f"{name}.mps.gz"
        generate_jssp_mps(name, n_jobs, n_machines, jobs, mps_path)
        tasks.append((name, mps_path, n_jobs, n_machines, pt_low, pt_high, pt_pattern, seed))

    def worker(task):
        name, mps_path, n_jobs, n_machines, pt_low, pt_high, pt_pattern, seed = task
        stats = solve_with_mipster(mps_path, args.time_limit)
        stats.update(name=name, n_jobs=n_jobs, n_machines=n_machines,
                      pt_low=pt_low, pt_high=pt_high, pt_pattern=pt_pattern,
                      seed=seed)
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
    print(f"Scratch .mps.gz files kept in {tmpdir}")


if __name__ == "__main__":
    main()
