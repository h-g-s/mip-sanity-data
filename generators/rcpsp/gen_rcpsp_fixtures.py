#!/usr/bin/env python3
"""Generate RCPSP (Resource-Constrained Project Scheduling Problem)
time-indexed MPS fixtures for MIPster testing.

See rcpsp_lib.py for the formulation and the two-phase construction
approach: phase 1 solves with horizon = sum(durations) [a safe, always-
valid upper bound] to find the optimal makespan T*, then phase 2 rebuilds
the model with the tight horizon T* and stores that as the final
instance.

Eight diverse baseline instances, varying job count, resource count,
duration/demand ranges, and network structure (levels/density).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import rcpsp_lib as R

REPO_ROOT = Path(__file__).parent.parent.parent
MIPS_DIR = REPO_ROOT / "mips"
SCRATCH = Path("/tmp/rcpsp_scratch")


def build_instances():
    insts = []

    # 1. n=6, 2 resources, small/simple
    insts.append(dict(
        name="rcpsp_n6_r2_s42",
        params=dict(seed=42, n_jobs=6, n_resources=2, dur_lo=2, dur_hi=6),
    ))

    # 2. n=8, 2 resources
    insts.append(dict(
        name="rcpsp_n8_r2_s137",
        params=dict(seed=137, n_jobs=8, n_resources=2, dur_lo=2, dur_hi=7),
    ))

    # 3. n=8, 3 resources, tighter capacity
    insts.append(dict(
        name="rcpsp_n8_r3_tight_s42",
        params=dict(seed=42, n_jobs=8, n_resources=3, dur_lo=2, dur_hi=6,
                    res_capacity_factor=1.3),
    ))

    # 4. n=10, 2 resources
    insts.append(dict(
        name="rcpsp_n10_r2_s7",
        params=dict(seed=7, n_jobs=10, n_resources=2, dur_lo=2, dur_hi=7),
    ))

    # 5. n=10, 3 resources, more precedence density
    insts.append(dict(
        name="rcpsp_n10_r3_dense_s99",
        params=dict(seed=99, n_jobs=10, n_resources=3, dur_lo=2, dur_hi=6,
                    extra_edge_prob=0.5),
    ))

    # 6. n=12, 2 resources
    insts.append(dict(
        name="rcpsp_n12_r2_s21",
        params=dict(seed=21, n_jobs=12, n_resources=2, dur_lo=2, dur_hi=6),
    ))

    # 7. n=12, 3 resources, tight capacity
    insts.append(dict(
        name="rcpsp_n12_r3_tight_s137",
        params=dict(seed=137, n_jobs=12, n_resources=3, dur_lo=2, dur_hi=5,
                    res_capacity_factor=1.3),
    ))

    # 8. n=14, 2 resources, larger
    insts.append(dict(
        name="rcpsp_n14_r2_s42",
        params=dict(seed=42, n_jobs=14, n_resources=2, dur_lo=2, dur_hi=6),
    ))

    return insts


def main():
    MIPS_DIR.mkdir(parents=True, exist_ok=True)
    instances = build_instances()
    results = []

    print("=== Generating RCPSP Fixtures (two-phase time-indexed) ===\n")

    for spec in instances:
        name = spec["name"]
        print(f"[{name}]  {spec['params']}")
        instance = R.generate_instance(**spec["params"])
        result = R.two_phase_build(
            name, instance, MIPS_DIR,
            phase1_time_limit=90, phase2_time_limit=100,
            scratch_dir=SCRATCH,
        )
        if result is None:
            print(f"  SKIPPED (phase 1 not proven optimal)\n")
            continue
        results.append(result)
        print()

    print("=== Summary ===")
    for r in results:
        p2 = r["phase2"]
        print(f"  {r['name']}: T*={r['T_opt']} obj={p2['obj']} "
              f"optimal={p2['optimal']} wall={p2['wall']}s nodes={p2['nodes']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
