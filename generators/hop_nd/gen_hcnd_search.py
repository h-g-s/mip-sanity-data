#!/usr/bin/env python3
"""Parameter-grid search for "interesting" Hop-Constrained Network Design
(HCND) instances: proven optimal within a moderate time budget, but only
after genuine branch-and-bound (not solved at the root node).

Explored zone (from manual scale probing): n=14-16, edge_prob=0.3-0.4,
num_commodities=8-10, hop_limit=4. This region shows extreme seed
sensitivity (same n/edge_prob/commodities: ~3s/50 nodes vs ~90s/14500
nodes), similar to what was observed for TSP/MTZ.

Writes a JSON report to /tmp/hcnd_search_report.json for later curation
by gen_hcnd_diverse.py.
"""

import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
from hcnd_lib import build_layered_mps, write_mps_gz, solve_with_mipster, generate_instance

TIME_LIMIT = 100
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 100

GRID = []
for n in (14, 15, 16):
    for ep in (0.3, 0.35, 0.4):
        for k in (8, 10):
            for seed in range(1, 9):
                GRID.append(dict(n=n, edge_prob=ep, num_commodities=k, hop_limit=4, seed=seed))


def run_one(spec):
    name = f"n{spec['n']}_ep{spec['edge_prob']}_k{spec['num_commodities']}_H{spec['hop_limit']}_s{spec['seed']}"
    instance = generate_instance(spec["n"], spec["edge_prob"], spec["num_commodities"],
                                  spec["hop_limit"], spec["seed"])
    mps_text = build_layered_mps(name, instance)
    path = Path("/tmp") / f"hcnd_search_{name}.mps.gz"
    write_mps_gz(mps_text, path)
    r = solve_with_mipster(path, TIME_LIMIT)
    path.unlink(missing_ok=True)
    interesting = bool(r["optimal"] and MIN_TIME <= r["wall"] <= MAX_TIME and
                        (r["nodes"] or 0) >= MIN_NODES)
    return dict(name=name, spec=spec, num_edges=len(instance["edges"]),
                num_commodities=len(instance["commodities"]),
                obj=r["obj"], optimal=r["optimal"], nodes=r["nodes"], wall=r["wall"],
                interesting=interesting)


def main():
    results = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = {ex.submit(run_one, spec): spec for spec in GRID}
        done = 0
        for fut in as_completed(futs):
            res = fut.result()
            results.append(res)
            done += 1
            tag = "  *** INTERESTING ***" if res["interesting"] else ""
            print(f"[{done}/{len(GRID)}] {res['name']:35s} optimal={res['optimal']!s:5} "
                  f"nodes={res['nodes']!s:>6} wall={res['wall']:>6.2f}s{tag}")

    n_interesting = sum(1 for r in results if r["interesting"])
    print(f"\n{n_interesting}/{len(results)} interesting "
          f"(proven optimal, {MIN_TIME}-{MAX_TIME}s, >={MIN_NODES} nodes)")
    print(f"total wall: {time.time() - t0:.1f}s")

    Path("/tmp/hcnd_search_report.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
