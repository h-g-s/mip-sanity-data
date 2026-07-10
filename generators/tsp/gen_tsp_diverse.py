#!/usr/bin/env python3
"""Generate a curated set of "interesting" TSP instances (MTZ formulation)
selected from the parameter-grid search (gen_tsp_search.py). Each entry
was found to be proven optimal by mipster in roughly 15-70s of wall time
with genuine branch-and-bound (834 to 8877 nodes) -- MTZ's notoriously
weak LP relaxation means the solver must actually search, even at these
modest sizes.

Writes MPS files directly into mips/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tsp_lib as T

REPO_ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = REPO_ROOT / "mips"

TIME_LIMIT = 120

# (n, seed, kind)
CURATED = [
    (16, 1, "euclidean"),
    (17, 1, "euclidean"),
    (18, 1, "euclidean"),
    (18, 4, "euclidean"),
    (19, 1, "euclidean"),
    (20, 1, "euclidean"),
    (21, 3, "euclidean"),
    (22, 3, "euclidean"),
    (22, 5, "euclidean"),
    (18, 1, "asymmetric"),
    (18, 4, "asymmetric"),
    (19, 3, "asymmetric"),
    (20, 5, "asymmetric"),
    (21, 2, "asymmetric"),
    (22, 2, "asymmetric"),
]


def main():
    MIPS_DIR.mkdir(exist_ok=True, parents=True)
    results = []

    for n, seed, kind in CURATED:
        name = f"tsp_{kind}_n{n}_sd{seed}"
        print(f"=== {name} ===", flush=True)
        mps_text, info = T.build_instance(name, n, seed, kind)
        gz_path = MIPS_DIR / f"{name}.mps.gz"
        T.write_mps_gz(mps_text, gz_path)
        r = T.solve_with_mipster(gz_path, TIME_LIMIT)
        print(f"  -> obj={r['obj']} optimal={r['optimal']} nodes={r['nodes']} wall={r['wall']}s", flush=True)
        if not r["optimal"]:
            print(f"  WARNING: not proven optimal, removing {gz_path}", flush=True)
            gz_path.unlink(missing_ok=True)
            continue
        results.append((name, r))

    print(f"\nGenerated {len(results)}/{len(CURATED)} curated TSP instances into {MIPS_DIR}")
    for name, r in results:
        print(f"{name}\t{r['obj']}\t{r['optimal']}\t{r['nodes']}\t{r['wall']}")


if __name__ == "__main__":
    main()
