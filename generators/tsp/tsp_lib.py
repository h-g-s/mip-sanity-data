"""Shared library for (Asymmetric/Euclidean) Traveling Salesman Problem
instance generation using the Miller-Tucker-Zemlin (MTZ) formulation.

The MTZ formulation is compact (no exponential subtour-elimination
constraints, unlike DFJ), which is required since we ship a static MPS
file rather than a solver with lazy cut callbacks. Its LP relaxation is
notoriously weak, which is actually a good fit for this dataset's goal:
it forces genuine branch-and-bound work even on fairly small instances,
rather than being solved trivially at the root node.

Formulation (n cities, 0 = depot):
  Variables:
    x[i][j]  binary, for i != j, i,j in 0..n-1: arc i->j used in the tour.
    u[i]     continuous, for i in 1..n-1: position of city i in the tour
             (u[0] is fixed at 0 and needs no variable).

  Objective: minimize sum_{i!=j} c[i][j] * x[i][j]

  Constraints:
    - out-degree: sum_{j!=i} x[i][j] = 1               for every i
    - in-degree:  sum_{i!=j} x[i][j] = 1                for every j
    - MTZ subtour elimination:
        u[i] - u[j] + (n-1) * x[i][j] <= n-2
        for all i,j in 1..n-1, i != j
      (u[i] in [1, n-1] for i in 1..n-1)

Costs are Euclidean distances between random 2D points, rounded to the
nearest integer (as in TSPLIB's EUC_2D convention) for symmetric
instances; asymmetric instances additionally perturb c[i][j] != c[j][i].
"""

import gzip
import math
import random
import re
import subprocess
from pathlib import Path

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")


# ──────────────────────────────────────────────────────────────────────────
# Instance generation
# ──────────────────────────────────────────────────────────────────────────

def generate_euclidean_instance(n, seed, grid=1000):
    """Random 2D Euclidean TSP instance. Returns (points, cost) where cost
    is an n x n integer matrix (rounded Euclidean distance, symmetric)."""
    rng = random.Random(seed)
    points = [(rng.uniform(0, grid), rng.uniform(0, grid)) for _ in range(n)]
    cost = [[0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                dx = points[i][0] - points[j][0]
                dy = points[i][1] - points[j][1]
                cost[i][j] = round(math.hypot(dx, dy))
    return points, cost


def generate_asymmetric_instance(n, seed, grid=1000, asym_factor=0.3):
    """Random Euclidean base, then perturb each direction independently so
    c[i][j] != c[j][i] (models one-way streets / directional costs)."""
    rng = random.Random(seed)
    _, cost = generate_euclidean_instance(n, seed, grid)
    for i in range(n):
        for j in range(n):
            if i != j:
                factor = 1.0 + rng.uniform(-asym_factor, asym_factor)
                cost[i][j] = max(1, round(cost[i][j] * factor))
    return cost


# ──────────────────────────────────────────────────────────────────────────
# MPS construction (MTZ formulation)
# ──────────────────────────────────────────────────────────────────────────

def build_mtz_mps(name, n, cost):
    """Build the MTZ-formulation MPS text for an n-city TSP given an n x n
    cost matrix (cost[i][i] is ignored)."""
    xvar = lambda i, j: f"x_{i}_{j}"
    uvar = lambda i: f"u_{i}"

    rows = []            # (name, sense, rhs)
    def add_row(rname, sense, rhs):
        rows.append((rname, sense, rhs))

    col_rows = {}         # var -> list of (row_name, coeff)
    def add_coeff(vname, rname, coeff):
        col_rows.setdefault(vname, []).append((rname, coeff))

    obj = {}

    arcs = [(i, j) for i in range(n) for j in range(n) if i != j]
    for i, j in arcs:
        obj[xvar(i, j)] = cost[i][j]

    # out-degree: sum_j x[i][j] = 1
    for i in range(n):
        rname = f"OUT_{i}"
        add_row(rname, "E", 1.0)
        for j in range(n):
            if j != i:
                add_coeff(xvar(i, j), rname, 1.0)

    # in-degree: sum_i x[i][j] = 1
    for j in range(n):
        rname = f"IN_{j}"
        add_row(rname, "E", 1.0)
        for i in range(n):
            if i != j:
                add_coeff(xvar(i, j), rname, 1.0)

    # MTZ subtour elimination: u_i - u_j + (n-1)*x_ij <= n-2, i,j in 1..n-1, i!=j
    for i in range(1, n):
        for j in range(1, n):
            if i == j:
                continue
            rname = f"MTZ_{i}_{j}"
            add_row(rname, "L", float(n - 2))
            add_coeff(uvar(i), rname, 1.0)
            add_coeff(uvar(j), rname, -1.0)
            add_coeff(xvar(i, j), rname, float(n - 1))

    L = []
    L.append(f"NAME          {name}")
    L.append("ROWS")
    L.append(" N  OBJ")
    for rname, sense, _ in rows:
        L.append(f" {sense}  {rname}")

    L.append("COLUMNS")
    L.append("    MARK0001  'MARKER'                 'INTORG'")
    for i, j in arcs:
        vname = xvar(i, j)
        L.append(f"    {vname:<14s}  OBJ           {obj[vname]}")
        for rname, coeff in col_rows.get(vname, []):
            L.append(f"    {vname:<14s}  {rname:<14s}  {coeff}")
    L.append("    MARK0001  'MARKER'                 'INTEND'")
    # u variables are continuous
    for i in range(1, n):
        vname = uvar(i)
        for rname, coeff in col_rows.get(vname, []):
            L.append(f"    {vname:<14s}  {rname:<14s}  {coeff}")

    L.append("RHS")
    for rname, _, rhs in rows:
        if rhs != 0.0:
            L.append(f"    RHS           {rname:<14s}  {rhs}")

    L.append("BOUNDS")
    for i, j in arcs:
        L.append(f" BV BOUND         {xvar(i, j)}")
    for i in range(1, n):
        L.append(f" LO BOUND         {uvar(i)}       1.0")
        L.append(f" UP BOUND         {uvar(i)}       {float(n - 1)}")

    L.append("ENDATA")
    return "\n".join(L) + "\n"


def write_mps_gz(mps_text, path):
    with gzip.open(path, "wt") as f:
        f.write(mps_text)


# ──────────────────────────────────────────────────────────────────────────
# Instance construction (end-to-end)
# ──────────────────────────────────────────────────────────────────────────

def build_instance(name, n, seed, kind="euclidean", grid=1000, asym_factor=0.3):
    if kind == "euclidean":
        _, cost = generate_euclidean_instance(n, seed, grid)
    elif kind == "asymmetric":
        cost = generate_asymmetric_instance(n, seed, grid, asym_factor)
    else:
        raise ValueError(f"unknown kind: {kind}")
    mps_text = build_mtz_mps(name, n, cost)
    info = dict(n=n, kind=kind, seed=seed)
    return mps_text, info


# ──────────────────────────────────────────────────────────────────────────
# Solving via mipster
# ──────────────────────────────────────────────────────────────────────────

def solve_with_mipster(mps_path, time_limit, extra_args=None):
    import time
    args = [MIPSTER, str(mps_path), "-sec", str(time_limit), "-solve"]
    if extra_args:
        args = [MIPSTER, str(mps_path)] + extra_args + ["-sec", str(time_limit), "-solve"]
    t0 = time.time()
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=time_limit + 30)
        out = r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        out = ""
    wall = time.time() - t0

    obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
    nodes_m = re.search(r"Enumerated nodes:\s*(\d+)", out)
    lb_m = re.search(r"Lower bound:\s*([\-0-9.eE]+)", out)
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    nodes = int(nodes_m.group(1)) if nodes_m else None
    lb = float(lb_m.group(1)) if lb_m else None

    return dict(obj=obj, optimal=optimal, nodes=nodes, wall=round(wall, 2),
                lower_bound=lb, raw_out=out)


def solve_with_solu(mps_path, sol_path, time_limit):
    r = subprocess.run(
        [MIPSTER, str(mps_path), "-sec", str(time_limit), "-solve", "-solu", str(sol_path)],
        capture_output=True, text=True, timeout=time_limit + 30,
    )
    out = r.stdout + r.stderr
    obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    return dict(obj=obj, optimal=optimal, raw_out=out)
