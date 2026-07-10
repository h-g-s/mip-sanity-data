#!/usr/bin/env python3
"""Generate baseline Graph Coloring fixtures (asymmetric representatives
formulation). Small/quick instances with certifiable or easily-verified
chromatic numbers, covering a variety of graph patterns, plus a couple of
medium random instances for basic size coverage.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gc_lib as G

REPO_ROOT = Path(__file__).resolve().parents[2]
MIPS_DIR = REPO_ROOT / "mips"


def custom_graph_spec(name, n, edges, timeout=10):
    return dict(name=name, n=n, edges=edges, timeout=timeout)


# Hand-built small graphs with known chromatic numbers (used to sanity
# check the formulation itself, and for very fast CI smoke tests).
CUSTOM_SPECS = [
    custom_graph_spec("gc_triangle_k3", 3, [(0, 1), (1, 2), (0, 2)]),
    custom_graph_spec("gc_cycle_c5", 5, [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)]),
    custom_graph_spec("gc_cycle_c4_bipartite", 4, [(0, 1), (1, 2), (2, 3), (3, 0)]),
    custom_graph_spec("gc_complete_k6", 6, [(i, j) for i in range(6) for j in range(i + 1, 6)]),
    custom_graph_spec("gc_petersen", 10, [
        (0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
        (5, 7), (7, 9), (9, 6), (6, 8), (8, 5),
        (0, 5), (1, 6), (2, 7), (3, 8), (4, 9),
    ], timeout=20),
]

# Randomly generated instances: (n_vertices, seed, pattern, edge_prob, timeout)
RANDOM_SPECS = [
    (20, 42, "random", 0.3, 15),
    (30, 137, "random", 0.4, 30),
    (25, 42, "geometric", 0.3, 20),
    (24, 137, "k_partite", 0.35, 20),
    (11, 1, "mycielski", 0.0, 10),
    (23, 1, "mycielski", 0.0, 30),
    (28, 42, "planar", 0.3, 20),
]


def generate_custom(spec):
    name = spec["name"]
    n, edges = spec["n"], spec["edges"]
    order, _ = G.degree_order(n, edges)
    ub = G.greedy_coloring_ub(n, edges, order)
    mps_text = G.build_coloring_mps(name, n, edges, order)
    return name, mps_text, dict(n=n, m=len(edges), ub=ub, timeout=spec["timeout"])


def main():
    MIPS_DIR.mkdir(exist_ok=True, parents=True)
    results = []

    for spec in CUSTOM_SPECS:
        name, mps_text, info = generate_custom(spec)
        print(f"=== {name} (n={info['n']}, m={info['m']}, greedy_ub={info['ub']}) ===", flush=True)
        gz_path = MIPS_DIR / f"{name}.mps.gz"
        G.write_mps_gz(mps_text, gz_path)
        r = G.solve_with_mipster(gz_path, info["timeout"])
        print(f"  -> obj={r['obj']} optimal={r['optimal']} nodes={r['nodes']} wall={r['wall']}", flush=True)
        if not r["optimal"]:
            print(f"  WARNING: not proven optimal, removing {gz_path}", flush=True)
            gz_path.unlink(missing_ok=True)
            continue
        results.append((name, r))

    for n, seed, pattern, edge_prob, timeout in RANDOM_SPECS:
        name = f"gc_{pattern}_n{n}_sd{seed}"
        print(f"=== {name} ===", flush=True)
        mps_text, info = G.build_instance(name, n, seed, pattern, edge_prob)
        print(f"  n={info['n']} m={info['m']} greedy_ub={info['ub']}", flush=True)
        gz_path = MIPS_DIR / f"{name}.mps.gz"
        G.write_mps_gz(mps_text, gz_path)
        r = G.solve_with_mipster(gz_path, timeout)
        print(f"  -> obj={r['obj']} optimal={r['optimal']} nodes={r['nodes']} wall={r['wall']}", flush=True)
        if not r["optimal"]:
            print(f"  WARNING: not proven optimal, removing {gz_path}", flush=True)
            gz_path.unlink(missing_ok=True)
            continue
        results.append((name, r))

    print(f"\nGenerated {len(results)} baseline graph coloring instances into {MIPS_DIR}")
    for name, r in results:
        print(f"{name}\t{r['obj']}\t{r['optimal']}\t{r['nodes']}\t{r['wall']}")


if __name__ == "__main__":
    main()
