#!/usr/bin/env python3
"""Parameter-grid search to find "interesting" TSP instances (MTZ
formulation): proven optimal by mipster in roughly 15-90s of wall time,
with genuine branch-and-bound (not solved at/near the root node).

Exploratory testing showed the MTZ formulation's weak LP relaxation makes
difficulty extremely seed-sensitive already at n=17-22 (Euclidean random
instances): some seeds solve in a few seconds, others take 30-90s+ with
thousands of nodes. n<=15 is essentially always trivial; n>=23 risks not
proving optimality within 90s.
"""
import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tsp_lib as T

TIME_LIMIT = 90
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 200
SCRATCH = Path("/tmp/tsp_search_scratch")
SCRATCH.mkdir(exist_ok=True)


def solve_one(n, seed, kind="euclidean"):
    name = f"tsp_search_n{n}_{kind}_sd{seed}"
    mps_text, info = T.build_instance(name, n, seed, kind)
    mps_path = SCRATCH / f"{name}.mps.gz"
    T.write_mps_gz(mps_text, mps_path)
    r = T.solve_with_mipster(mps_path, TIME_LIMIT)
    mps_path.unlink(missing_ok=True)
    interesting = bool(r["optimal"] and r["obj"] is not None and r["nodes"] is not None
                        and MIN_TIME <= r["wall"] <= MAX_TIME and r["nodes"] >= MIN_NODES)
    return dict(name=name, n=n, seed=seed, kind=kind,
                obj=r["obj"], nodes=r["nodes"], wall=r["wall"],
                optimal=r["optimal"], interesting=interesting)


def main():
    combos = []
    for kind in ["euclidean", "asymmetric"]:
        for n in [16, 17, 18, 19, 20, 21, 22]:
            for seed in range(1, 9):
                combos.append((n, seed, kind))
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
            print(f"[{done}/{len(combos)}] n={r['n']} kind={r['kind']} sd={r['seed']} "
                  f"-> obj={r['obj']} optimal={r['optimal']} nodes={r['nodes']} wall={r['wall']}s{tag}",
                  flush=True)

    interesting = [r for r in results if r["interesting"]]
    print(f"\nFound {len(interesting)} interesting out of {len(combos)}")
    with open("/tmp/tsp_search_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Report written to /tmp/tsp_search_report.json")


if __name__ == "__main__":
    main()
