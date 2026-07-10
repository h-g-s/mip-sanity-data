#!/usr/bin/env python3
"""Generate the curated SPPC (Generalized Set Partitioning/Packing/Covering)
fixture set: two tiny brute-force-verified baseline instances, one minimal
bug-repro instance that triggers a genuine MIPster preprocessing wrong-optimal
bug (deliberately preserved -- see the ``bug_wrongopt_preprocess`` entry
below), and a diverse set of mid/large-scale instances selected from a
parameter-grid search (``gen_sppc_search.py``) to require genuine
branch-and-bound (hundreds to thousands of nodes) while proving optimality
within roughly 8-55 seconds.

Writes .mps.gz files to mips/ and reference .sol files to sols/ (solved with
mipster; the bug-repro fixture is solved with ``-preprocess off`` since
default settings produce a WRONG result on it by design).
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from sppc_lib import (generate_instance, generate_instance_bug_repro_v1,
                       build_sppc_mps, write_mps_gz, solve_with_solu)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = REPO_ROOT / "mips"
SOLS_DIR = REPO_ROOT / "sols"
MIPSTER_PATH = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")

# (name, generate_instance kwargs, expected optimal from brute force or search)
BASELINE_SMALL = [
    ("sppc_small_1", dict(num_tasks=4, cand_range=(2, 3), num_packing=6, num_covering=4, seed=2), 90),
    ("sppc_small_2", dict(num_tasks=4, cand_range=(2, 3), num_packing=6, num_covering=4, seed=3), 94),
]

# Diverse mid/large-scale instances, picked from gen_sppc_search.py results to
# span a range of scales (50-100 tasks) and wall-clock times (8-55s) while
# requiring genuine branch-and-bound (78-3375 nodes).
DIVERSE = [
    ("sppc_t50_p75_c75_s1",   dict(num_tasks=50,  cand_range=(3, 6), num_packing=75,  num_covering=75,  seed=1)),
    ("sppc_t50_p100_c100_s8", dict(num_tasks=50,  cand_range=(3, 6), num_packing=100, num_covering=100, seed=8)),
    ("sppc_t50_p125_c75_s2",  dict(num_tasks=50,  cand_range=(3, 6), num_packing=125, num_covering=75,  seed=2)),
    ("sppc_t60_p90_c90_s7",   dict(num_tasks=60,  cand_range=(3, 6), num_packing=90,  num_covering=90,  seed=7)),
    ("sppc_t60_p120_c90_s1",  dict(num_tasks=60,  cand_range=(3, 6), num_packing=120, num_covering=90,  seed=1)),
    ("sppc_t60_p150_c60_s5",  dict(num_tasks=60,  cand_range=(3, 6), num_packing=150, num_covering=60,  seed=5)),
    ("sppc_t60_p180_c60_s8",  dict(num_tasks=60,  cand_range=(3, 6), num_packing=180, num_covering=60,  seed=8)),
    ("sppc_t80_p120_c80_s2",  dict(num_tasks=80,  cand_range=(3, 6), num_packing=120, num_covering=80,  seed=2)),
    ("sppc_t80_p160_c80_s1",  dict(num_tasks=80,  cand_range=(3, 6), num_packing=160, num_covering=80,  seed=1)),
    ("sppc_t80_p160_c120_s4", dict(num_tasks=80,  cand_range=(3, 6), num_packing=160, num_covering=120, seed=4)),
    ("sppc_t80_p200_c80_s6",  dict(num_tasks=80,  cand_range=(3, 6), num_packing=200, num_covering=80,  seed=6)),
    ("sppc_t80_p200_c160_s5", dict(num_tasks=80,  cand_range=(3, 6), num_packing=200, num_covering=160, seed=5)),
    ("sppc_t80_p240_c120_s1", dict(num_tasks=80,  cand_range=(3, 6), num_packing=240, num_covering=120, seed=1)),
    ("sppc_t100_p150_c100_s8", dict(num_tasks=100, cand_range=(3, 6), num_packing=150, num_covering=100, seed=8)),
    ("sppc_t100_p200_c100_s1", dict(num_tasks=100, cand_range=(3, 6), num_packing=200, num_covering=100, seed=1)),
    ("sppc_t100_p250_c150_s6", dict(num_tasks=100, cand_range=(3, 6), num_packing=250, num_covering=150, seed=6)),
    ("sppc_t100_p300_c200_s6", dict(num_tasks=100, cand_range=(3, 6), num_packing=300, num_covering=200, seed=6)),
]

# The bug-repro fixture is generated separately in this same run (kept small
# and fixed, NOT part of the search grid): num_tasks=3, cand_range=(2,3),
# num_packing=2, num_covering=2, seed=1. Default mipster settings claim a
# WRONG optimal (30) due to a preprocessing + Feasibility Jump interaction
# bug; the correct optimal (43, brute-force verified over all 2^7 cases) is
# obtained with ``-preprocess off``.
BUG_REPRO = ("sppc_bug_wrongopt_preprocess",
             dict(num_tasks=3, cand_range=(2, 3), num_packing=2, num_covering=2, seed=1))


def build_and_solve(name, kwargs, extra_mipster_args=None, generator=generate_instance):
    inst = generator(**kwargs)
    mps = build_sppc_mps(name, inst)
    mps_path = MIPS_DIR / f"{name}.mps.gz"
    write_mps_gz(mps, str(mps_path))
    sol_path = SOLS_DIR / f"{name}.sol"
    args = [MIPSTER_PATH, str(mps_path), "-sec", "150"]
    if extra_mipster_args:
        args += extra_mipster_args
    args += ["-solve", "-solu", str(sol_path)]
    log = subprocess.run(args, capture_output=True, text=True, timeout=200)
    return inst, mps_path, sol_path, log.stdout + log.stderr


def main():
    MIPS_DIR.mkdir(exist_ok=True)
    SOLS_DIR.mkdir(exist_ok=True)

    for name, kwargs, expected in BASELINE_SMALL:
        inst, mps_path, sol_path, out = build_and_solve(name, kwargs)
        print(f"{name}: ncols={inst['num_columns']} expected={expected}")
        if "Optimal solution found" not in out:
            print(f"  WARNING: {name} did not report optimal!\n{out[-500:]}")

    for name, kwargs in DIVERSE:
        inst, mps_path, sol_path, out = build_and_solve(name, kwargs)
        print(f"{name}: ncols={inst['num_columns']}")
        if "Optimal solution found" not in out:
            print(f"  WARNING: {name} did not report optimal!\n{out[-500:]}")

    name, kwargs = BUG_REPRO
    inst, mps_path, sol_path, out = build_and_solve(
        name, kwargs, extra_mipster_args=["-preprocess", "off"],
        generator=generate_instance_bug_repro_v1)
    print(f"{name}: ncols={inst['num_columns']} (generated with -preprocess off; "
          f"default MIPster settings intentionally produce a WRONG result on this "
          f"instance -- kept as a permanent bug-repro fixture)")
    if "Optimal solution found" not in out:
        print(f"  WARNING: {name} did not report optimal even with -preprocess off!\n{out[-500:]}")


if __name__ == "__main__":
    main()
