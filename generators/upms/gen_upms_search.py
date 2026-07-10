#!/usr/bin/env python3
"""
Parameter-grid search harness for UPMSP-ST (Unrelated Parallel Machine
Scheduling with Sequence-Dependent Setup Times) instances.

The big-M formulation used by gen_upms_fixtures.py is quite hard even at
small scale: n=9,m=3 baseline instances already take 180s+ without proving
optimality (1M+ nodes, ~1.5% gap). This search explores n in [6,9],
m in [2,3], both objective types (Cmax / WCT), and varying proc/setup
time ranges to find the genuine "interesting" difficulty sweet spot
(proven optimal in 15-90s wall time with real branch-and-bound).

Writes a JSON report to /tmp/upms_search_report.json for later curation
via gen_upms_diverse.py.
"""

import json
import re
import subprocess
import sys
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_upms_fixtures as G  # noqa: E402

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")
TIME_LIMIT = 100
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 20

SCRATCH = Path("/tmp/upms_search_scratch")
SCRATCH.mkdir(exist_ok=True)


def solve_one(n, m, proc_lo, proc_hi, setup_lo, setup_hi, obj_type, seed):
    rng = random.Random(seed)
    proc = G.gen_proc(rng, n, m, lo=proc_lo, hi=proc_hi, asymmetry=True)
    setup = G.gen_setup(rng, n, m, lo=setup_lo, hi=setup_hi)
    weights = None
    if obj_type == "wct":
        weights = [rng.randint(1, 5) for _ in range(n)]

    name = f"upms_search_n{n}_m{m}_{obj_type}_p{proc_lo}-{proc_hi}_s{setup_lo}-{setup_hi}_sd{seed}"
    mps_text = G.make_upms_mps(name, n, m, proc, setup, weights)
    mps_path = SCRATCH / f"{name}.mps.gz"
    import gzip
    with gzip.open(mps_path, "wt") as f:
        f.write(mps_text)

    t0 = time.time()
    try:
        proc_r = subprocess.run(
            [MIPSTER, str(mps_path), "-sec", str(TIME_LIMIT), "-solve"],
            capture_output=True, text=True, timeout=TIME_LIMIT + 30,
        )
        out = proc_r.stdout + proc_r.stderr
    except subprocess.TimeoutExpired:
        out = ""
    wall = time.time() - t0

    obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
    nodes_m = re.search(r"Enumerated nodes:\s*(\d+)", out)
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    b_nodes = int(nodes_m.group(1)) if nodes_m else None

    interesting = bool(
        optimal and obj is not None and b_nodes is not None
        and MIN_TIME <= wall <= MAX_TIME and b_nodes >= MIN_NODES
    )

    mps_path.unlink(missing_ok=True)

    return {
        "n": n, "m": m, "obj_type": obj_type,
        "proc_lo": proc_lo, "proc_hi": proc_hi,
        "setup_lo": setup_lo, "setup_hi": setup_hi, "seed": seed,
        "obj": obj, "nodes": b_nodes, "optimal": optimal, "wall": round(wall, 2),
        "interesting": interesting,
    }


def main():
    combos = []
    for n in [7, 8, 9]:
        for m in [2, 3]:
            for obj_type in ["cmax", "wct"]:
                for (proc_lo, proc_hi, setup_lo, setup_hi) in [
                    (5, 18, 2, 9), (6, 22, 3, 11), (7, 25, 3, 12), (5, 18, 8, 22),
                ]:
                    for seed in [42, 137, 7, 99, 21]:
                        combos.append((n, m, proc_lo, proc_hi, setup_lo, setup_hi, obj_type, seed))

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
            print(f"[{done}/{len(combos)}] n={r['n']} m={r['m']} obj_type={r['obj_type']} "
                  f"p={r['proc_lo']}-{r['proc_hi']} s={r['setup_lo']}-{r['setup_hi']} sd={r['seed']} "
                  f"-> obj={r['obj']} nodes={r['nodes']} optimal={r['optimal']} wall={r['wall']}s{tag}",
                  flush=True)

    interesting = [r for r in results if r["interesting"]]
    print(f"\nFound {len(interesting)} interesting out of {len(combos)}")

    with open("/tmp/upms_search_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Report written to /tmp/upms_search_report.json")


if __name__ == "__main__":
    main()
