#!/usr/bin/env python3
"""Generate baseline TSP fixtures (MTZ formulation). Small instances with
brute-force-verifiable optima, plus a few small/medium random Euclidean
and asymmetric instances for basic size/variant coverage.
"""
import sys
import itertools
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tsp_lib as T

REPO_ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = REPO_ROOT / "mips"


def brute_force_optimum(n, cost):
    best = None
    for perm in itertools.permutations(range(1, n)):
        tour = (0,) + perm
        total = sum(cost[tour[i]][tour[(i + 1) % n]] for i in range(n))
        if best is None or total < best:
            best = total
    return best


# Tiny instances: brute-forced for a double-check on top of mipster's own
# optimality proof. (n_vertices, seed, kind, timeout)
TINY_SPECS = [
    (4, 1, "euclidean", 10),
    (5, 1, "euclidean", 10),
    (6, 1, "euclidean", 10),
    (7, 1, "euclidean", 10),
    (8, 1, "euclidean", 15),
    (7, 1, "asymmetric", 15),
]

# Small/medium random instances (no brute force, just mipster-certified
# optimal): (n_vertices, seed, kind, timeout)
RANDOM_SPECS = [
    (10, 42, "euclidean", 15),
    (12, 137, "euclidean", 20),
    (14, 42, "euclidean", 30),
    (10, 42, "asymmetric", 20),
    (12, 137, "asymmetric", 30),
]


def main():
    MIPS_DIR.mkdir(exist_ok=True, parents=True)
    results = []

    for n, seed, kind, timeout in TINY_SPECS:
        name = f"tsp_{kind}_n{n}_sd{seed}"
        print(f"=== {name} ===", flush=True)
        if kind == "euclidean":
            _, cost = T.generate_euclidean_instance(n, seed)
        else:
            cost = T.generate_asymmetric_instance(n, seed)
        bf = brute_force_optimum(n, cost)
        mps_text = T.build_mtz_mps(name, n, cost)
        gz_path = MIPS_DIR / f"{name}.mps.gz"
        T.write_mps_gz(mps_text, gz_path)
        r = T.solve_with_mipster(gz_path, timeout)
        match = (r["obj"] is not None and abs(r["obj"] - bf) < 1e-6)
        print(f"  brute_force={bf} mipster_obj={r['obj']} optimal={r['optimal']} match={match} wall={r['wall']}", flush=True)
        if not (r["optimal"] and match):
            print(f"  WARNING: mismatch or not optimal, removing {gz_path}", flush=True)
            gz_path.unlink(missing_ok=True)
            continue
        results.append((name, r))

    for n, seed, kind, timeout in RANDOM_SPECS:
        name = f"tsp_{kind}_n{n}_sd{seed}"
        print(f"=== {name} ===", flush=True)
        mps_text, info = T.build_instance(name, n, seed, kind)
        gz_path = MIPS_DIR / f"{name}.mps.gz"
        T.write_mps_gz(mps_text, gz_path)
        r = T.solve_with_mipster(gz_path, timeout)
        print(f"  -> obj={r['obj']} optimal={r['optimal']} nodes={r['nodes']} wall={r['wall']}", flush=True)
        if not r["optimal"]:
            print(f"  WARNING: not proven optimal, removing {gz_path}", flush=True)
            gz_path.unlink(missing_ok=True)
            continue
        results.append((name, r))

    print(f"\nGenerated {len(results)} baseline TSP instances into {MIPS_DIR}")
    for name, r in results:
        print(f"{name}\t{r['obj']}\t{r['optimal']}\t{r['nodes']}\t{r['wall']}")


if __name__ == "__main__":
    main()
