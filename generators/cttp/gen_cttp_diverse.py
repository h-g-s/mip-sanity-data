"""Curated CTTP fixture generator: builds the final diverse instance set for
this dataset from calibrated parameter combinations (see
gen_cttp_diverse_search.py / search_results.json for the calibration sweep
that identified these as genuinely search-exercising).

Produces .mps.gz + .sol pairs directly under mips/ and sols/ at the repo
root, and prints a TSV-ready summary line per instance for bks.tsv.
"""

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import cttp_lib as lib

REPO_ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = REPO_ROOT / "mips"
SOLS_DIR = REPO_ROOT / "sols"

# (name, nc, nt, nd, ns, req_range, util, seed, time_limit_for_solu, expected_status)
# expected_status: "optimal" (search proved it) or "best_known" (best incumbent,
# search timed out at 90s during calibration) or "infeasible"
FIXTURES = [
    # --- tiny baselines: fast, fully proven ---
    ("cttp_tiny_c4t5_r2-4_sd2", 4, 5, 5, 6, (2, 4), 0.85, 2, "optimal"),
    ("cttp_tiny_c4t5_r2-3_sd2", 4, 5, 5, 6, (2, 3), 0.75, 2, "optimal"),

    # --- small-medium, genuine B&B (hundreds of nodes), proven optimal ---
    ("cttp_small_c5t6_r2-4_sd1", 5, 6, 5, 6, (2, 4), 0.75, 1, "optimal"),
    ("cttp_small_c5t6_r2-3_sd1", 5, 6, 5, 6, (2, 3), 0.75, 1, "optimal"),
    ("cttp_small_c6t6_s5_r2-3_sd3", 6, 6, 5, 5, (2, 3), 0.75, 3, "optimal"),
    ("cttp_small_c6t8_r2-4_sd1", 6, 8, 5, 6, (2, 4), 0.75, 1, "optimal"),
    ("cttp_small_c6t8_r2-3_sd3", 6, 8, 5, 6, (2, 3), 0.75, 3, "optimal"),

    # --- medium-large, proven optimal but near the calibration time budget ---
    ("cttp_medium_c6t8_r2-4_sd2", 6, 8, 5, 6, (2, 4), 0.75, 2, "optimal"),
    ("cttp_medium_c8t8_s7_r2-3_sd3", 8, 8, 5, 7, (2, 3), 0.75, 3, "optimal"),
    ("cttp_medium_c9t11_r2-4_sd3", 9, 11, 5, 6, (2, 4), 0.85, 3, "optimal"),

    # --- hard: search did not conclude in 90s during calibration; best_known ---
    ("cttp_hard_c6t6_s5_r2-4_sd3", 6, 6, 5, 5, (2, 4), 0.75, 3, "best_known"),
    ("cttp_hard_c6t7_r2-3_sd3", 6, 7, 5, 6, (2, 3), 0.75, 3, "best_known"),
    ("cttp_hard_c7t9_r2-3_sd1", 7, 9, 5, 6, (2, 3), 0.75, 1, "best_known"),
    ("cttp_hard_c9t11_r2-4_sd1", 9, 11, 5, 6, (2, 4), 0.75, 1, "best_known"),
    ("cttp_hard_c10t12_r2-3_sd2", 10, 12, 5, 6, (2, 3), 0.75, 2, "best_known"),

    # --- infeasible fixture (confirmed via calibration sweep) ---
    ("cttp_infeasible_c10t12_r2-4_sd2", 10, 12, 5, 6, (2, 4), 0.85, 2, "infeasible"),
]

# (name, nc, nt, nd, ns, req_range, util, seed, day_weight, gap_weight)
WEIGHT_VARIANTS = [
    ("cttp_gapfocus_c6t8_sd9", 6, 8, 5, 6, (2, 4), 0.75, 9, 1.0, 10.0),
    ("cttp_dayfocus_c6t8_sd10", 6, 8, 5, 6, (2, 4), 0.75, 10, 20.0, 0.5),
]

SOLVE_TIME = 300  # generous, since these are being solved ONCE at build time


def build_fixed(name, nc, nt, nd, ns, req_range, util, seed, expected_status):
    mps_text, info, instance = lib.build_instance(
        name, num_classes=nc, num_teachers=nt, num_days=nd, slots_per_day=ns,
        subjects_per_class_range=(4, 6), req_range=req_range, seed=seed,
        day_weight=10.0, gap_weight=1.0,
        p_random_slot=0.05, p_day_off=0.1,
        max_class_utilization=util, max_teacher_utilization=util)
    return mps_text, info, instance


def build_weighted(name, nc, nt, nd, ns, req_range, util, seed, day_w, gap_w):
    mps_text, info, instance = lib.build_instance(
        name, num_classes=nc, num_teachers=nt, num_days=nd, slots_per_day=ns,
        subjects_per_class_range=(4, 6), req_range=req_range, seed=seed,
        day_weight=day_w, gap_weight=gap_w,
        p_random_slot=0.05, p_day_off=0.1,
        max_class_utilization=util, max_teacher_utilization=util)
    return mps_text, info, instance


def main():
    MIPS_DIR.mkdir(exist_ok=True)
    SOLS_DIR.mkdir(exist_ok=True)
    bks_lines = []

    all_specs = [(f, "fixed") for f in FIXTURES] + [(f, "weighted") for f in WEIGHT_VARIANTS]

    for spec, kind in all_specs:
        if kind == "fixed":
            name, nc, nt, nd, ns, req_range, util, seed, expected_status = spec
            mps_text, info, instance = build_fixed(name, nc, nt, nd, ns, req_range, util, seed, expected_status)
        else:
            name, nc, nt, nd, ns, req_range, util, seed, day_w, gap_w = spec
            expected_status = "optimal"
            mps_text, info, instance = build_weighted(name, nc, nt, nd, ns, req_range, util, seed, day_w, gap_w)

        mps_path = MIPS_DIR / f"{name}.mps.gz"
        lib.write_mps_gz(mps_text, mps_path)
        print(f"Built {name}: meetings={info['num_meetings']} total_req={info['total_req']}")

        if expected_status == "infeasible":
            res = lib.solve_with_mipster(mps_path, SOLVE_TIME)
            status = "infeasible" if res["infeasible"] else "UNEXPECTED-" + str(res)
            print(f"  -> {name}: {status}")
            bks_lines.append((name, "infeasible", "", "min", "CTTP generator (Santos-style class-teacher timetabling)"))
            continue

        sol_path = SOLS_DIR / f"{name}.sol"
        res = lib.solve_with_solu(mps_path, sol_path, SOLVE_TIME)
        proven = res["optimal"]
        obj = res["obj"]
        status = "optimal" if proven else "best_known"
        print(f"  -> {name}: status={status} obj={obj}")
        bks_lines.append((name, status, obj, "min", "CTTP generator (Santos-style class-teacher timetabling)"))

    print("\n--- bks.tsv lines ---")
    for name, status, obj, sense, source in bks_lines:
        print(f"{name}\t{status}\t{obj}\t{sense}\t{source}")


if __name__ == "__main__":
    main()
