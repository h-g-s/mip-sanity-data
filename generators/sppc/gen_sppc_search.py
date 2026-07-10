#!/usr/bin/env python3
"""Parameter-grid search for "interesting" SPPC instances: proven optimal
within a target wall-time window, with a genuine (non-trivial) branch-and-
bound node count. Writes a JSON report to /tmp/sppc_search_report.json.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sppc_lib import generate_instance, build_sppc_mps, write_mps_gz, solve_with_mipster

TIME_LIMIT = 60
MIN_WALL, MAX_WALL = 8, 55
MIN_NODES = 20

configs = []
for num_tasks in [30, 40, 50, 60, 80, 100]:
    for np_ratio in [1.5, 2.0, 2.5, 3.0]:
        for nc_ratio in [1.0, 1.5, 2.0]:
            for seed in range(1, 9):
                np_ = int(num_tasks * np_ratio)
                nc_ = int(num_tasks * nc_ratio)
                configs.append((num_tasks, np_, nc_, seed))


def run(cfg):
    num_tasks, np_, nc_, seed = cfg
    inst = generate_instance(num_tasks=num_tasks, cand_range=(3, 6),
                              num_packing=np_, num_covering=nc_, seed=seed)
    name = f"search_t{num_tasks}_p{np_}_c{nc_}_s{seed}"
    mps = build_sppc_mps(name, inst)
    path = f"/tmp/{name}.mps.gz"
    write_mps_gz(mps, path)
    r = solve_with_mipster(path, TIME_LIMIT)
    return dict(num_tasks=num_tasks, num_packing=np_, num_covering=nc_, seed=seed,
                num_columns=inst["num_columns"],
                optimal=r.get("optimal"), obj=r.get("obj"),
                nodes=r.get("nodes"), wall=r.get("wall"))


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=7) as ex:
        results = list(ex.map(run, configs))

    interesting = [r for r in results
                   if r["optimal"] and r["nodes"] and r["nodes"] >= MIN_NODES
                   and MIN_WALL <= r["wall"] <= MAX_WALL]
    interesting.sort(key=lambda r: r["wall"])

    print(f"Total configs: {len(results)}")
    print(f"Interesting (optimal, nodes>={MIN_NODES}, {MIN_WALL}-{MAX_WALL}s): {len(interesting)}")
    for r in interesting:
        print(r)

    Path("/tmp/sppc_search_report.json").write_text(json.dumps(results, indent=2))
