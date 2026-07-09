#!/usr/bin/env python3
"""Search a CVRP parameter grid for "interesting" instances.

An instance is considered interesting when solving it with mipster:
  - reaches proven optimality within a target wall-clock window
    (default 15s - 120s), and
  - does not solve trivially at the root node (it should require
    branching and/or generate cutting planes), so the test actually
    exercises LP relaxation, cut separation and branch-and-bound.

Usage:
    python3 gen_cvrp_search.py [--min-time 15] [--max-time 120] \\
        [--min-nodes 20] [--jobs 7] [--time-limit 150]

Writes candidate .mps.gz files to a scratch directory and prints a
report of which ones are "interesting" per the criteria above. It does
NOT write into mips/ automatically -- promote the ones you like by
calling write_cvrp_mps() directly (see promote_instance()) or by
re-running the specific parameter combination through gen_vrp_fixtures.py.
"""

import argparse
import gzip
import itertools
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from gen_vrp_fixtures import (generate_positions, compute_cost_matrix,
                               generate_demands)

import os

MIPSTER_BIN = os.environ.get("MIPSTER_BIN") or (
    str(Path(os.environ["MIPSTER_PREFIX"]) / "bin" / "mipster")
    if "MIPSTER_PREFIX" in os.environ else "mipster"
)


def write_cvrp_mps_to(path, K, customers, Q, demands, costs):
    """Write a CVRP MPS file to an explicit path (plain text, not gzipped)."""
    N = len(customers)
    with open(path, "w") as f:
        f.write(f"NAME          instance\n")
        f.write("ROWS\n")
        f.write(" N  OBJ\n")

        for i in customers:
            f.write(f" E  OUT{i}\n")
            f.write(f" E  IN{i}\n")
            f.write(f" E  FLOW{i}\n")

        f.write(" L  FLEET\n")

        cap_idx = 0
        cap_map = {}
        for i in [0] + customers:
            for j in customers:
                if i == j:
                    continue
                cap_map[(i, j)] = cap_idx
                f.write(f" L  CAP{cap_idx}\n")
                cap_idx += 1

        for i in customers:
            f.write(f" G  DLBO{i}\n")
            f.write(f" L  DUBO{i}\n")

        f.write("COLUMNS\n")
        f.write("    MARK0000  'MARKER'                 'INTORG'\n")

        for i in [0] + customers:
            for j in [0] + customers:
                if i == j:
                    continue
                v = f"x{i}_{j}"
                f.write(f"    {v:12s}  OBJ       {costs.get((i, j), 9999):.2f}\n")
                if i > 0:
                    f.write(f"    {v:12s}  OUT{i}     1\n")
                if j > 0:
                    f.write(f"    {v:12s}  IN{j}      1\n")
                if i > 0:
                    f.write(f"    {v:12s}  FLOW{i}    1\n")
                if j > 0:
                    f.write(f"    {v:12s}  FLOW{j}   -1\n")
                if i == 0:
                    f.write(f"    {v:12s}  FLEET      1\n")
                if (i, j) in cap_map:
                    idx = cap_map[(i, j)]
                    f.write(f"    {v:12s}  CAP{idx}    {Q}\n")

        f.write("    MARK0000  'MARKER'                 'INTEND'\n")

        for i in customers:
            v = f"u{i}"
            for (arc_i, arc_j) in cap_map:
                idx = cap_map[(arc_i, arc_j)]
                if i == arc_i and arc_i > 0:
                    f.write(f"    {v:12s}  CAP{idx}     1\n")
                elif i == arc_j:
                    f.write(f"    {v:12s}  CAP{idx}    -1\n")
            f.write(f"    {v:12s}  DLBO{i}    1\n")
            f.write(f"    {v:12s}  DUBO{i}    1\n")

        f.write("RHS\n")
        for i in customers:
            f.write(f"    RHS1      OUT{i}      1\n")
            f.write(f"    RHS1      IN{i}       1\n")
        f.write(f"    RHS1      FLEET      {K}\n")

        for (i, j), idx in cap_map.items():
            rhs = Q - demands[j]
            f.write(f"    RHS1      CAP{idx}     {rhs}\n")

        for i in customers:
            f.write(f"    RHS1      DLBO{i}    {demands[i]}\n")
            f.write(f"    RHS1      DUBO{i}    {Q}\n")

        f.write("BOUNDS\n")
        f.write("ENDATA\n")


def build_instance(n_customers, k_vehicles, cap_factor, demand_pattern,
                    pos_pattern, cost_type, seed):
    """Build one CVRP instance from a parameter combination."""
    customers = list(range(1, n_customers + 1))
    positions = generate_positions(n_customers + 1, pattern=pos_pattern, seed=seed)
    # generate_positions(n+1, ...) returns node keys 0..n: node 0 is the
    # depot, nodes 1..n_customers are the customers -- matches directly.
    costs = compute_cost_matrix(positions, cost_type=cost_type)
    demands = generate_demands(n_customers, pattern=demand_pattern, seed=seed)

    avg_demand = sum(demands.values()) / n_customers
    Q = max(1, round(avg_demand * n_customers / k_vehicles * cap_factor))

    return customers, Q, demands, costs


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
    # Count root-relaxation cut rounds as a proxy for "cuts exercised"
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
    ap.add_argument("--out", default="/tmp/cvrp_search_report.json")
    args = ap.parse_args()

    grid = list(itertools.product(
        [10, 12, 14, 16],             # n_customers
        [2, 3],                       # k_vehicles
        [1.0, 1.15, 1.3],             # cap_factor (tightness)
        ["uniform", "skewed", "varied"],   # demand_pattern
        ["uniform", "clustered"],     # pos_pattern
        [42, 137],                    # seed
    ))

    print(f"=== Searching {len(grid)} CVRP parameter combinations "
          f"(jobs={args.jobs}, time_limit={args.time_limit}s) ===\n")

    tmpdir = tempfile.mkdtemp()
    tasks = []
    for (n, k, capf, dpat, ppat, seed) in grid:
        name = f"cvrp_n{n}_k{k}_c{capf}_{dpat}_{ppat}_s{seed}"
        customers, Q, demands, costs = build_instance(n, k, capf, dpat, ppat, "euclidean", seed)
        mps_path = Path(tmpdir) / f"{name}.mps"
        write_cvrp_mps_to(mps_path, k, customers, Q, demands, costs)
        tasks.append((name, mps_path, n, k, capf, dpat, ppat, seed))

    def worker(task):
        name, mps_path, n, k, capf, dpat, ppat, seed = task
        stats = solve_with_mipster(mps_path, args.time_limit)
        stats.update(name=name, n=n, k=k, cap_factor=capf,
                      demand_pattern=dpat, pos_pattern=ppat, seed=seed)
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
