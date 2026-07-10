#!/usr/bin/env python3
"""Generate a curated set of "interesting" RCPSP instances (time-indexed
formulation, two-phase build) selected from the parameter-grid search.

Each entry was found by gen_rcpsp_search.py to be proven optimal by mipster
in roughly 15-40s of wall time with a genuine amount of branch-and-bound
(nodes >= ~20, several in the thousands). Because the resource capacity
in rcpsp_lib.generate_instance() is floored at the maximum single-job
demand, varying cap_factor alone frequently yields an identical instance;
the tuples below were de-duplicated to keep only distinct base graphs
(unique n_jobs/extra_edge_prob/seed combinations), each solved with a
single representative cap_factor.

Writes final (phase-2) MPS files directly into mips/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rcpsp_lib as R

REPO_ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = REPO_ROOT / "mips"
SCRATCH = Path("/tmp/rcpsp_diverse_scratch")

# (n_jobs, n_resources, dur_lo, dur_hi, extra_edge_prob, cap_factor, seed)
CURATED = [
    (9, 2, 2, 6, 0.2, 1.3, 7),
    (9, 2, 2, 6, 0.4, 1.3, 7),
    (9, 2, 2, 6, 0.2, 1.3, 8),
    (9, 2, 2, 6, 0.4, 1.3, 8),
    (9, 2, 2, 6, 0.2, 1.3, 1),
    (10, 2, 2, 6, 0.4, 1.5, 42),
    (11, 2, 2, 6, 0.2, 1.3, 7),
    (11, 2, 2, 6, 0.4, 1.3, 7),
    (11, 2, 2, 6, 0.4, 1.3, 4),
]

PHASE1_TIME_LIMIT = 90
PHASE2_TIME_LIMIT = 120


def main():
    MIPS_DIR.mkdir(exist_ok=True, parents=True)
    SCRATCH.mkdir(exist_ok=True, parents=True)

    results = []
    for n_jobs, n_resources, dur_lo, dur_hi, ep, cf, seed in CURATED:
        name = f"rcpsp_n{n_jobs}_r{n_resources}_ep{ep}_s{seed}"
        print(f"=== {name} ===", flush=True)
        instance = R.generate_instance(
            seed=seed, n_jobs=n_jobs, n_resources=n_resources,
            dur_lo=dur_lo, dur_hi=dur_hi, extra_edge_prob=ep,
            res_demand_lo=1, res_demand_hi=6, res_capacity_factor=cf,
        )
        result = R.two_phase_build(
            name, instance, MIPS_DIR,
            phase1_time_limit=PHASE1_TIME_LIMIT,
            phase2_time_limit=PHASE2_TIME_LIMIT,
            scratch_dir=SCRATCH, verbose=True,
        )
        if result is None:
            print(f"  FAILED (phase1 not proven optimal) -- skipping {name}", flush=True)
            continue
        p2 = result["phase2"]
        if not p2["optimal"]:
            print(f"  WARNING: phase2 not proven optimal for {name}, obj={p2['obj']}", flush=True)
        results.append((name, result))
        print(f"  -> T*={result['T_opt']} obj={p2['obj']} nodes={p2['nodes']} wall={p2['wall']}s", flush=True)

    print(f"\nGenerated {len(results)}/{len(CURATED)} curated RCPSP instances into {MIPS_DIR}")
    for name, result in results:
        p2 = result["phase2"]
        print(f"{name}\t{p2['obj']}\t{p2['optimal']}\t{p2['nodes']}\t{p2['wall']}")


if __name__ == "__main__":
    main()
