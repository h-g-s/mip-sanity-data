"""Shared library for Graph Coloring instance generation using the
Asymmetric Representatives Formulation (Campelo, Correa, Frota).

Problem: given G=(V,E), find the minimum number of colors such that no
two adjacent vertices share a color.

Formulation (fix a linear order 0..n-1 on V):
  Variables:
    x[i][j]  binary, for j <= i, meaning "vertex i is assigned to the
             color class represented by vertex j". x[i][i] = 1 means
             vertex i is itself the representative of a (new) color
             class -- i.e. a color is "opened" at i.

  Objective: minimize sum_i x[i][i]      (number of colors used)

  Constraints:
    - Assignment: sum_{j=0}^{i} x[i][j] = 1        for every vertex i
                  (each vertex is assigned to exactly one representative
                  with index <= its own -- this alone breaks most of the
                  color-permutation symmetry present in the classical
                  assignment formulation).
    - Validity:   x[i][j] <= x[j][j]                for all j < i
                  (a vertex can only be assigned to a representative that
                  is itself "open").
    - Conflict:   x[i][j] + x[k][j] <= x[j][j]       for every edge (i,k),
                  i < k, and every j <= i
                  (adjacent vertices cannot share a color class; this also
                  subsumes the validity constraint for the j=i/j=k cases).

This formulation is much tighter in practice than the classical
assignment formulation (x[v][c], y[c]) because it eliminates color
symmetry structurally rather than via added symmetry-breaking cuts.
"""

import gzip
import math
import random
import re
import subprocess
from pathlib import Path

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")


# ──────────────────────────────────────────────────────────────────────────
# Graph generation
# ──────────────────────────────────────────────────────────────────────────

def generate_graph(n_vertices, seed, pattern="random", edge_prob=0.3):
    """Generate a graph. Returns (edges) as a sorted list of (u, v), u < v.

    Patterns:
      random     - Erdos-Renyi G(n, p)
      geometric  - unit disk graph (proximity in the 2D plane)
      planar     - grid-based planar graph with some diagonals
      k_partite  - k-partite graph (k=3), edges only across parts
      mycielski  - Mycielski-style construction seeded from a small odd
                   cycle (triangle-free, but with growing chromatic number)
    """
    rng = random.Random(seed)
    edges = set()

    if pattern == "random":
        for u in range(n_vertices):
            for v in range(u + 1, n_vertices):
                if rng.random() < edge_prob:
                    edges.add((u, v))

    elif pattern == "geometric":
        positions = [(rng.random() * 100, rng.random() * 100) for _ in range(n_vertices)]
        threshold = 100 * math.sqrt(edge_prob / (math.pi * 0.7))
        for u in range(n_vertices):
            for v in range(u + 1, n_vertices):
                dx = positions[u][0] - positions[v][0]
                dy = positions[u][1] - positions[v][1]
                if math.hypot(dx, dy) < threshold:
                    edges.add((u, v))

    elif pattern == "planar":
        side = max(2, int(math.sqrt(n_vertices)))
        for u in range(n_vertices):
            row_u, col_u = divmod(u, side)
            if col_u < side - 1 and u + 1 < n_vertices:
                edges.add((u, u + 1))
            if row_u < side - 1 and u + side < n_vertices:
                edges.add((u, u + side))
        for u in range(n_vertices):
            row_u, col_u = divmod(u, side)
            if row_u < side - 1 and col_u < side - 1 and rng.random() < 0.3:
                v = u + side + 1
                if v < n_vertices:
                    edges.add((u, v))

    elif pattern == "k_partite":
        k = 3
        part_size = max(1, n_vertices // k)
        for u in range(n_vertices):
            part_u = min(u // part_size, k - 1)
            for v in range(u + 1, n_vertices):
                part_v = min(v // part_size, k - 1)
                if part_u != part_v and rng.random() < min(1.0, edge_prob * 1.8):
                    edges.add((u, v))

    elif pattern == "mycielski":
        # Start from a base odd cycle C_5 and apply the Mycielski
        # construction repeatedly until reaching (approximately) n_vertices.
        base_edges = [(i, (i + 1) % 5) for i in range(5)]
        cur_edges = [(min(u, v), max(u, v)) for u, v in base_edges]
        cur_n = 5
        while cur_n < n_vertices:
            # Mycielskian: for each vertex v in 0..cur_n-1, add a "shadow"
            # vertex v' connected to N(v); add one extra "apex" vertex
            # connected to all shadows.
            shadow_of = {v: cur_n + v for v in range(cur_n)}
            apex = cur_n + cur_n
            new_edges = list(cur_edges)
            for u, v in cur_edges:
                new_edges.append((min(u, shadow_of[v]), max(u, shadow_of[v])))
                new_edges.append((min(v, shadow_of[u]), max(v, shadow_of[u])))
            for v in range(cur_n):
                new_edges.append((min(shadow_of[v], apex), max(shadow_of[v], apex)))
            cur_edges = sorted(set(new_edges))
            cur_n = apex + 1
        # Trim down to n_vertices if the construction overshot; keep only
        # edges among the first n_vertices vertices.
        edges = {(u, v) for u, v in cur_edges if u < n_vertices and v < n_vertices}

    else:
        raise ValueError(f"unknown pattern: {pattern}")

    return sorted(edges)


# ──────────────────────────────────────────────────────────────────────────
# Vertex ordering / heuristics
# ──────────────────────────────────────────────────────────────────────────

def degree_order(n_vertices, edges):
    """Order vertices by non-increasing degree (ties broken by index).
    Used as the linear order for the representatives formulation: putting
    high-degree vertices first tends to produce tighter/faster models."""
    deg = [0] * n_vertices
    for u, v in edges:
        deg[u] += 1
        deg[v] += 1
    order = sorted(range(n_vertices), key=lambda v: (-deg[v], v))
    # position[v] = index of v in the new order (0-based)
    position = [0] * n_vertices
    for pos, v in enumerate(order):
        position[v] = pos
    return order, position


def greedy_coloring_ub(n_vertices, edges, order):
    """Greedy sequential coloring in the given order; returns an upper
    bound on the chromatic number (number of colors used)."""
    adj = [set() for _ in range(n_vertices)]
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    color = [-1] * n_vertices
    for v in order:
        used = {color[u] for u in adj[v] if color[u] != -1}
        c = 0
        while c in used:
            c += 1
        color[v] = c
    return max(color) + 1 if n_vertices > 0 else 0


def greedy_clique(n_vertices, edges, order):
    """Greedy heuristic to find a reasonably large clique (used to fix a
    lower bound / break symmetry: every vertex in the clique must get its
    own color, so can be fixed as its own representative)."""
    adj = [set() for _ in range(n_vertices)]
    for u, v in edges:
        adj[u].add(v)
        adj[v].add(u)
    clique = []
    candidates = list(order)
    for v in order:
        if all(v in adj[c] for c in clique):
            clique.append(v)
    return clique


# ──────────────────────────────────────────────────────────────────────────
# MPS construction
# ──────────────────────────────────────────────────────────────────────────

def build_coloring_mps(name, n_vertices, edges, order, fixed_clique=None):
    """Build the asymmetric representatives formulation MPS text.

    order: a permutation of range(n_vertices) giving the linear order used
    to index representatives (order[0] is "vertex 0" in formulation terms,
    i.e. the only vertex allowed to represent itself with no predecessor
    candidates). We relabel vertices 0..n-1 according to `order` internally.
    fixed_clique: optional list of *original* vertex ids to fix as their
    own representative (x[i][i] = 1) for symmetry breaking / a valid LB.
    """
    # relabel: pos[v] = new index of original vertex v
    pos = [0] * n_vertices
    for new_idx, v in enumerate(order):
        pos[v] = new_idx
    relabeled_edges = sorted({(min(pos[u], pos[v]), max(pos[u], pos[v])) for u, v in edges})
    fixed_positions = set(pos[v] for v in (fixed_clique or []))

    n = n_vertices
    var_name = lambda i, j: f"x_{i}_{j}"

    rows = []          # (name, sense, rhs)
    row_index = {}
    def add_row(rname, sense, rhs):
        row_index[rname] = len(rows)
        rows.append((rname, sense, rhs))

    col_rows = {}       # var -> list of (row_name, coeff)
    def add_coeff(vname, rname, coeff):
        col_rows.setdefault(vname, []).append((rname, coeff))

    all_vars = []
    for i in range(n):
        for j in range(i + 1):
            all_vars.append((i, j))

    # (1) Assignment: sum_{j<=i} x_i_j = 1
    for i in range(n):
        rname = f"ASSIGN_{i}"
        add_row(rname, "E", 1.0)
        for j in range(i + 1):
            add_coeff(var_name(i, j), rname, 1.0)

    # (2) Validity: x_i_j - x_j_j <= 0, for j < i
    for i in range(n):
        for j in range(i):
            rname = f"LINK_{i}_{j}"
            add_row(rname, "L", 0.0)
            add_coeff(var_name(i, j), rname, 1.0)
            add_coeff(var_name(j, j), rname, -1.0)

    # (3) Conflict: for edge (i,k), i<k, and every candidate representative
    # j <= i:
    #   - j <  i: x_i_j + x_k_j - x_j_j <= 0   (neither i nor k is itself
    #             the representative j; tightened against y_j = x_j_j)
    #   - j == i: x_i_i + x_k_i <= 1            (i opens its own color; k
    #             cannot join that same class). Note x_j_j == x_i_i here,
    #             so the "j < i" RHS form degenerates to a tautology and
    #             must NOT be used for this case.
    for i, k in relabeled_edges:
        for j in range(i):
            rname = f"EDGE_{i}_{k}_{j}"
            add_row(rname, "L", 0.0)
            add_coeff(var_name(i, j), rname, 1.0)
            add_coeff(var_name(k, j), rname, 1.0)
            add_coeff(var_name(j, j), rname, -1.0)
        rname = f"EDGE_{i}_{k}_{i}"
        add_row(rname, "L", 1.0)
        add_coeff(var_name(i, i), rname, 1.0)
        add_coeff(var_name(k, i), rname, 1.0)

    # Objective: minimize sum_i x_i_i
    obj = {var_name(i, i): 1.0 for i in range(n)}

    L = []
    L.append(f"NAME          {name}")
    L.append("ROWS")
    L.append(" N  OBJ")
    for rname, sense, _ in rows:
        L.append(f" {sense}  {rname}")

    L.append("COLUMNS")
    L.append("    MARK0001  'MARKER'                 'INTORG'")
    for i, j in all_vars:
        vname = var_name(i, j)
        if vname in obj:
            L.append(f"    {vname:<14s}  OBJ           {obj[vname]}")
        for rname, coeff in col_rows.get(vname, []):
            L.append(f"    {vname:<14s}  {rname:<14s}  {coeff}")
    L.append("    MARK0001  'MARKER'                 'INTEND'")

    L.append("RHS")
    for rname, _, rhs in rows:
        if rhs != 0.0:
            L.append(f"    RHS           {rname:<14s}  {rhs}")

    L.append("BOUNDS")
    for i, j in all_vars:
        vname = var_name(i, j)
        if i == j and i in fixed_positions:
            L.append(f" FX BOUND         {vname}       1.0")
        else:
            L.append(f" BV BOUND         {vname}")

    L.append("ENDATA")
    return "\n".join(L) + "\n"


def write_mps_gz(mps_text, path):
    with gzip.open(path, "wt") as f:
        f.write(mps_text)


# ──────────────────────────────────────────────────────────────────────────
# Instance construction (end-to-end)
# ──────────────────────────────────────────────────────────────────────────

def build_instance(name, n_vertices, seed, pattern="random", edge_prob=0.3,
                    use_clique_fix=False):
    """Generate a graph and build the representatives-formulation MPS text.
    Returns (mps_text, info) where info has n, m, ub (greedy UB), clique
    size, and order used."""
    edges = generate_graph(n_vertices, seed, pattern, edge_prob)
    order, _ = degree_order(n_vertices, edges)
    ub = greedy_coloring_ub(n_vertices, edges, order)
    clique = greedy_clique(n_vertices, edges, order) if use_clique_fix else []
    mps_text = build_coloring_mps(name, n_vertices, edges, order,
                                  fixed_clique=clique if use_clique_fix else None)
    info = dict(n=n_vertices, m=len(edges), ub=ub, clique_size=len(clique),
                pattern=pattern, edge_prob=edge_prob, seed=seed)
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
