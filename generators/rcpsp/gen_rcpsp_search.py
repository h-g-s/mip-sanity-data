#!/usr/bin/env python3
"""
Parameter-grid search harness for RCPSP time-indexed instances.

The two-phase construction (see rcpsp_lib.py) means each candidate requires
TWO solves: phase 1 (large UB horizon = sum of durations) to find the
optimal makespan T*, then phase 2 (tight horizon = T*) which is the model
actually stored and classified for "interesting"-ness.

Baseline exploration (gen_rcpsp_fixtures.py) showed a sharp difficulty
cliff: n_jobs<=10 is trivial (root-node solve), n_jobs>=12 already fails
to prove optimality within 90s at phase 1. This search scans n_jobs in
[9,10,11], varying resource count, capacity tightness, precedence density,
and duration/demand ranges, to find genuine branch-and-bound difficulty
in the phase-2 (final, stored) model.

Classification is based on phase 2 stats only (that's the model we keep):
  - proven optimal
  - MIN_TIME <= wall <= MAX_TIME
  - nodes >= MIN_NODES

Writes a JSON report to /tmp/rcpsp_search_report.json.
"""

import json
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
import rcpsp_lib as R

PHASE1_TIME_LIMIT = 60
PHASE2_TIME_LIMIT = 90
MIN_TIME = 15
MAX_TIME = 90
MIN_NODES = 20

SCRATCH = Path("/tmp/rcpsp_search_scratch")
SCRATCH.mkdir(exist_ok=True)


def solve_one(n_jobs, n_resources, dur_lo, dur_hi, cap_factor, extra_edge_prob,
              res_demand_lo, res_demand_hi, seed):
    name = (f"rcpsp_search_n{n_jobs}_r{n_resources}_cf{cap_factor}"
            f"_ep{extra_edge_prob}_d{dur_lo}-{dur_hi}_sd{seed}")
    instance = R.generate_instance(
        seed=seed, n_jobs=n_jobs, n_resources=n_resources,
        dur_lo=dur_lo, dur_hi=dur_hi,
        extra_edge_prob=extra_edge_prob,
        res_demand_lo=res_demand_lo, res_demand_hi=res_demand_hi,
        res_capacity_factor=cap_factor,
    )
    result = R.two_phase_build(
        name, instance, SCRATCH / "out", phase1_time_limit=PHASE1_TIME_LIMIT,
        phase2_time_limit=PHASE2_TIME_LIMIT, scratch_dir=SCRATCH, verbose=False,
    )
    # clean up the phase-2 mps written into scratch/out (we only need stats here)
    if result is not None:
        result["mps_path"].unlink(missing_ok=True)

    if result is None:
        return dict(
            name=name, n_jobs=n_jobs, n_resources=n_resources, dur_lo=dur_lo,
            dur_hi=dur_hi, cap_factor=cap_factor, extra_edge_prob=extra_edge_prob,
            res_demand_lo=res_demand_lo, res_demand_hi=res_demand_hi, seed=seed,
            phase1_optimal=False, T_opt=None, obj=None, nodes=None, wall=None,
            optimal=False, interesting=False,
        )

    p2 = result["phase2"]
    interesting = bool(
        p2["optimal"] and p2["obj"] is not None and p2["nodes"] is not None
        and MIN_TIME <= p2["wall"] <= MAX_TIME and p2["nodes"] >= MIN_NODES
    )
    return dict(
        name=name, n_jobs=n_jobs, n_resources=n_resources, dur_lo=dur_lo,
        dur_hi=dur_hi, cap_factor=cap_factor, extra_edge_prob=extra_edge_prob,
        res_demand_lo=res_demand_lo, res_demand_hi=res_demand_hi, seed=seed,
        phase1_optimal=True, T_opt=result["T_opt"],
        obj=p2["obj"], nodes=p2["nodes"], wall=p2["wall"], optimal=p2["optimal"],
        interesting=interesting,
    )


def main():
    combos = []
    for n_jobs in [9, 10, 11]:
        for n_resources in [2, 3]:
            for cap_factor in [1.15, 1.3, 1.5]:
                for extra_edge_prob in [0.2, 0.4]:
                    for seed in [42, 137, 7]:
                        combos.append((n_jobs, n_resources, 2, 6, cap_factor,
                                        extra_edge_prob, 1, 6, seed))

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
            p1s = "OK" if r["phase1_optimal"] else "FAIL"
            print(f"[{done}/{len(combos)}] n={r['n_jobs']} r={r['n_resources']} "
                  f"cf={r['cap_factor']} ep={r['extra_edge_prob']} sd={r['seed']} "
                  f"-> phase1={p1s} T*={r['T_opt']} obj={r['obj']} nodes={r['nodes']} "
                  f"wall={r['wall']}s{tag}", flush=True)

    interesting = [r for r in results if r["interesting"]]
    print(f"\nFound {len(interesting)} interesting out of {len(combos)}")

    with open("/tmp/rcpsp_search_report.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Report written to /tmp/rcpsp_search_report.json")


if __name__ == "__main__":
    main()
