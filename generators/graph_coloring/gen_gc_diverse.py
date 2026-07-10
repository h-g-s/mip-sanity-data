#!/usr/bin/env python3
"""Generate a curated set of "interesting" Graph Coloring instances
(asymmetric representatives formulation) selected from the parameter-grid
search (gen_gc_search.py). Each entry was found to be proven optimal by
mipster in roughly 17-82s of wall time with genuine branch-and-bound
(62 to 526 nodes) -- i.e. the LP relaxation alone is not enough and the
solver must actually search.

Writes MPS files directly into mips/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_lib as G

REPO_ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = REPO_ROOT / "mips"

TIME_LIMIT = 120

# (n_vertices, edge_prob, seed) -- all "random" G(n,p) pattern
CURATED = [
    (48, 0.5, 3),
    (52, 0.4, 4),
    (52, 0.4, 5),
    (52, 0.5, 1),
    (52, 0.5, 4),
    (54, 0.4, 1),
    (54, 0.4, 5),
    (54, 0.5, 1),
    (56, 0.4, 2),
    (56, 0.4, 3),
    (56, 0.5, 3),
    (58, 0.5, 1),
    (58, 0.6, 1),
    (60, 0.4, 5),
    (60, 0.6, 1),
]


def main():
    MIPS_DIR.mkdir(exist_ok=True, parents=True)
    results = []

    for n, p, seed in CURATED:
        name = f"gc_random_n{n}_p{p}_sd{seed}"
        print(f"=== {name} ===", flush=True)
        mps_text, info = G.build_instance(name, n, seed, "random", p)
        print(f"  n={info['n']} m={info['m']} greedy_ub={info['ub']}", flush=True)
        gz_path = MIPS_DIR / f"{name}.mps.gz"
        G.write_mps_gz(mps_text, gz_path)
        r = G.solve_with_mipster(gz_path, TIME_LIMIT)
        print(f"  -> obj={r['obj']} optimal={r['optimal']} nodes={r['nodes']} wall={r['wall']}s", flush=True)
        if not r["optimal"]:
            print(f"  WARNING: not proven optimal, removing {gz_path}", flush=True)
            gz_path.unlink(missing_ok=True)
            continue
        results.append((name, r))

    print(f"\nGenerated {len(results)}/{len(CURATED)} curated graph coloring instances into {MIPS_DIR}")
    for name, r in results:
        print(f"{name}\t{r['obj']}\t{r['optimal']}\t{r['nodes']}\t{r['wall']}")


if __name__ == "__main__":
    main()
