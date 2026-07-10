#!/usr/bin/env python3
"""Generate a curated set of 'interesting' UPMSP-ST instances.

These (n, m, proc_lo, proc_hi, setup_lo, setup_hi, obj_type, seed) tuples
were selected from a 240-combo parameter-grid search (see
gen_upms_search.py) as instances that:
  - are proven optimal by mipster within roughly 15-90 seconds
  - require genuine branch-and-bound (tens to hundreds of thousands of
    nodes -- the big-M UPMSP-ST formulation is notably hard even at
    small n, so node counts here are much higher than in other families)

Note: n=9 with m=3 is already close to the intractable frontier for this
formulation; most n=9 combos in the search timed out without proof, so
only a few very favorable seeds at n=9 are "interesting" here.
"""

import gzip
import random
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import gen_upms_fixtures as G  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent.parent
MIPS_DIR = REPO_ROOT / "mips"
MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")

# (n, m, proc_lo, proc_hi, setup_lo, setup_hi, obj_type, seed)
DIVERSE_INSTANCES = [
    (7, 3, 5, 18, 8, 22, "cmax", 21),
    (7, 3, 6, 22, 3, 11, "wct", 137),
    (8, 2, 6, 22, 3, 11, "wct", 7),
    (8, 3, 5, 18, 8, 22, "cmax", 7),
    (8, 3, 5, 18, 2, 9, "wct", 137),
    (8, 2, 5, 18, 2, 9, "cmax", 42),
    (7, 2, 5, 18, 8, 22, "cmax", 21),
    (8, 3, 5, 18, 2, 9, "cmax", 42),
    (9, 3, 5, 18, 2, 9, "wct", 7),
    (8, 2, 7, 25, 3, 12, "wct", 42),
    (8, 3, 7, 25, 3, 12, "cmax", 7),
    (9, 3, 6, 22, 3, 11, "wct", 137),
    (8, 2, 6, 22, 3, 11, "cmax", 99),
    (9, 2, 6, 22, 3, 11, "wct", 7),
    (9, 3, 6, 22, 3, 11, "wct", 7),
]


def main():
    MIPS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for n, m, proc_lo, proc_hi, setup_lo, setup_hi, obj_type, seed in DIVERSE_INSTANCES:
        name = f"upms_search_n{n}_m{m}_{obj_type}_p{proc_lo}-{proc_hi}_s{setup_lo}-{setup_hi}_sd{seed}"
        print(f"Generating {name}...")
        rng = random.Random(seed)
        proc = G.gen_proc(rng, n, m, lo=proc_lo, hi=proc_hi, asymmetry=True)
        setup = G.gen_setup(rng, n, m, lo=setup_lo, hi=setup_hi)
        weights = None
        if obj_type == "wct":
            weights = [rng.randint(1, 5) for _ in range(n)]

        mps_text = G.make_upms_mps(name, n, m, proc, setup, weights)
        mps_path = MIPS_DIR / f"{name}.mps.gz"
        with gzip.open(mps_path, "wt") as f:
            f.write(mps_text)

        proc_r = subprocess.run(
            [MIPSTER, str(mps_path), "-sec", "120", "-solve"],
            capture_output=True, text=True, timeout=150,
        )
        out = proc_r.stdout + proc_r.stderr
        obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
        optimal = "Optimal solution found" in out
        obj = float(obj_m.group(1)) if obj_m else None
        print(f"  -> obj={obj} optimal={optimal}")
        results.append((name, obj, optimal))

    print("\nSummary:")
    for name, obj, optimal in results:
        print(f"  {name}: obj={obj} optimal={optimal}")


if __name__ == "__main__":
    main()
