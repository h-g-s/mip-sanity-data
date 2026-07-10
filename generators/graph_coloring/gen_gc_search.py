#!/usr/bin/env python3
"""Parameter-grid search to find "interesting" Graph Coloring instances:
proven optimal by mipster in roughly 15-90s of wall time, with genuine
branch-and-bound (not solved at the root node).

Exploratory testing showed the difficulty cliff for the asymmetric
representatives formulation on random G(n,p) graphs sits around
n=48-60, p=0.4-0.6 (below that: solved at the root node in well under a
second; n>=60 already risks not proving optimality within 90s).
"""
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_lib as G

TIME_LIMIT = 90
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 20
SCRATCH = Path("/tmp/gc_search_scratch")
SCRATCH.mkdir(exist_ok=True)


def solve_one(n, p, seed, pattern="random"):
    name = f"gc_search_n{n}_p{p}_{pattern}_sd{seed}"
    mps_text, info = G.build_instance(name, n, seed, pattern, p)
    mps_path = SCRATCH / f"{name}.mps.gz"
    G.write_mps_gz(mps_text, mps_path)
    r = G.solve_with_mipster(mps_path, TIME_LIMIT)
    mps_path.unlink(missing_ok=True)
    interesting = bool(r["optimal"] and r["obj"] is not None and r["nodes"] is not None
                        and MIN_TIME <= r["wall"] <= MAX_TIME and r["nodes"] >= MIN_NODES)
    return dict(name=name, n=n, p=p, seed=seed, pattern=pattern,
                obj=r["obj"], nodes=r["nodes"], wall=r["wall"],
                optimal=r["optimal"], interesting=interesting)


def main():
    combos = []
    for n in [48, 50, 52, 54, 56, 58, 60]:
        for p in [0.4, 0.5, 0.6]:
            for seed in [1, 2, 3, 4, 5]:
                combos.append((n, p, seed))
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
            print(f"[{done}/{len(combos)}] n={r['n']} p={r['p']} sd={r['seed']} "
                  f"-> obj={r['obj']} optimal={r['optimal']} nodes={r['nodes']} wall={r['wall']}s{tag}",
                  flush=True)

    interesting = [r for r in results if r["interesting"]]
    print(f"\nFound {len(interesting)} interesting out of {len(combos)}")
    with open("/tmp/gc_search_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Report written to /tmp/gc_search_report.json")


if __name__ == "__main__":
    main()
