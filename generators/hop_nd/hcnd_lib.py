"""Shared library for the Hop-Constrained Capacitated Network Design Problem
(HCNDP) instance generation using a layered-graph (hop-indexed) formulation.

Given a candidate graph with per-edge fixed install cost and capacity, and a
set of point-to-point commodities (each with a demand), decide which edges
to build (binary) so that every commodity's demand can be routed using paths
of at most H hops (edges), splittable across multiple such paths, without
exceeding the shared capacity of any built edge. Minimize total install cost.

This is a "network design" MIP with both binary (edge-install) and
continuous (per-commodity, per-hop-layer flow) variables, distinct from
plain fixed-charge network flow (FCNF) in two ways:
  - capacity/design decisions are SHARED across all commodities (multiple
    commodities compete for the same built edge's capacity), and
  - the hop limit is enforced structurally via a layered ("time-expanded")
    graph: H+1 copies of each node (layer 0..H), with flow only allowed to
    move strictly forward one layer per hop. This makes the LP relaxation
    weak (fractional routing can spread demand across many hop-limited
    paths sharing capacity) and forces genuine branch-and-bound even on
    small instances.

Formulation (per commodity k = (s, t, d), hop limit H, candidate edges
e = (i, j) with cost c_e and capacity u_e):

  Variables:
    y_e in {0,1}                          edge e installed
    f[k][u][v][h] >= 0                    flow of commodity k on arc u->v
                                           (u, v adjacent via some edge e)
                                           moving from layer h to h+1

  Layered pruning: an arc u->v at hop-step h is only created if the
  (uncapacitated) graph shortest-hop-distance from s to u is <= h, and from
  s to v is <= h+1 (a node can only appear at a layer if it is structurally
  reachable by that many hops). The sink t has no outgoing arcs (absorbing);
  the source s only appears at layer 0.

  Constraints:
    - supply:      sum_v f[k][s][v][0] = d_k                     (per k)
    - demand:      sum_{h,u} f[k][u][t][h] = d_k                  (per k)
    - conservation: for each transshipment node v (v != s, v != t) at each
      reachable intermediate layer h: outflow(v, h) = inflow(v, h)
    - capacity/design link (shared across commodities & directions):
        sum_k sum_h (f[k][i][j][h] + f[k][j][i][h]) <= u_e * y_e   (per edge e)

  Objective: minimize sum_e c_e * y_e
"""

import gzip
import math
import random
import re
import subprocess
from collections import deque
from pathlib import Path

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")


# ──────────────────────────────────────────────────────────────────────────
# Instance generation
# ──────────────────────────────────────────────────────────────────────────

def _bfs_hop_dist(n, adj, source):
    dist = [None] * n
    dist[source] = 0
    q = deque([source])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if dist[v] is None:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist


def _adjacency(n, edges):
    adj = [[] for _ in range(n)]
    for i, j, _c, _u in edges:
        adj[i].append(j)
        adj[j].append(i)
    return adj


def _connected_components(n, adj):
    comp = [-1] * n
    c = 0
    for start in range(n):
        if comp[start] != -1:
            continue
        comp[start] = c
        q = deque([start])
        while q:
            u = q.popleft()
            for v in adj[u]:
                if comp[v] == -1:
                    comp[v] = c
                    q.append(v)
        c += 1
    return comp, c


def generate_instance(n, edge_prob, num_commodities, hop_limit, seed,
                       cost_scale=(0.7, 1.3), capacity_range=(4, 12),
                       demand_range=(1, 4), grid=1000, min_hops=2):
    """Random Euclidean candidate graph + random commodities. Ensures the
    graph is connected and every chosen commodity has an (uncapacitated)
    shortest-hop distance in [min_hops, hop_limit] so the hop constraint is
    both satisfiable and non-trivial (not just a direct edge)."""
    rng = random.Random(seed)
    points = [(rng.uniform(0, grid), rng.uniform(0, grid)) for _ in range(n)]

    def dist_cost(i, j):
        dx = points[i][0] - points[j][0]
        dy = points[i][1] - points[j][1]
        base = math.hypot(dx, dy)
        return max(1, round(base * rng.uniform(*cost_scale)))

    edges = []
    edge_set = set()
    for i in range(n):
        for j in range(i + 1, n):
            if rng.random() < edge_prob:
                edges.append((i, j, dist_cost(i, j), rng.randint(*capacity_range)))
                edge_set.add((i, j))

    # Ensure connectivity: link components with a cheap extra edge each.
    adj = _adjacency(n, edges)
    comp, ncomp = _connected_components(n, adj)
    while ncomp > 1:
        reps = {}
        for v in range(n):
            reps.setdefault(comp[v], v)
        rep_list = list(reps.values())
        a, b = rep_list[0], rep_list[1]
        i, j = (a, b) if a < b else (b, a)
        if (i, j) not in edge_set:
            edges.append((i, j, dist_cost(i, j), rng.randint(*capacity_range)))
            edge_set.add((i, j))
        adj = _adjacency(n, edges)
        comp, ncomp = _connected_components(n, adj)

    adj = _adjacency(n, edges)

    commodities = []
    attempts = 0
    while len(commodities) < num_commodities and attempts < 5000:
        attempts += 1
        s, t = rng.sample(range(n), 2)
        dist = _bfs_hop_dist(n, adj, s)
        if dist[t] is None:
            continue
        if not (min_hops <= dist[t] <= hop_limit):
            continue
        d = rng.randint(*demand_range)
        commodities.append((s, t, d))

    return dict(n=n, edges=edges, commodities=commodities, hop_limit=hop_limit,
                seed=seed, edge_prob=edge_prob)


# ──────────────────────────────────────────────────────────────────────────
# Layered-graph MPS construction
# ──────────────────────────────────────────────────────────────────────────

def build_layered_mps(name, instance):
    n = instance["n"]
    edges = instance["edges"]
    commodities = instance["commodities"]
    H = instance["hop_limit"]
    adj = _adjacency(n, edges)

    yvar = lambda i, j: f"y_{i}_{j}"
    fvar = lambda k, u, v, h: f"f_{k}_{u}_{v}_{h}"

    rows = []                      # (name, sense, rhs)
    row_index = {}

    def add_row(rname, sense, rhs):
        row_index[rname] = len(rows)
        rows.append([rname, sense, rhs])

    col_rows = {}                  # var -> list[(row_name, coeff)]

    def add_coeff(vname, rname, coeff):
        col_rows.setdefault(vname, []).append((rname, coeff))

    obj = {}
    edge_cost = {}
    edge_cap = {}
    for i, j, c, u in edges:
        obj[yvar(i, j)] = c
        edge_cost[(i, j)] = c
        edge_cap[(i, j)] = u
        add_row(f"CAP_{i}_{j}", "L", 0.0)
        add_coeff(yvar(i, j), f"CAP_{i}_{j}", -float(u))

    flow_vars = []   # (vname, ub) continuous vars, ub = min over its edge caps

    for k, (s, t, d) in enumerate(commodities):
        dist_from_s = _bfs_hop_dist(n, adj, s)

        add_row(f"SUP_{k}", "E", float(d))
        add_row(f"DEM_{k}", "E", float(d))

        # arcs at hop-step h: layer h -> layer h+1, h = 0 .. H-1
        outflow_rows = {}   # (v, h) -> row name (conservation, only created lazily)
        inflow_terms = {}   # (v, h+1) -> list handled directly via add_coeff to CONS row

        def cons_row(v, layer):
            rname = f"CONS_{k}_{v}_{layer}"
            if rname not in row_index:
                add_row(rname, "E", 0.0)
            return rname

        for h in range(H):
            for i, j, _c, u_cap in edges:
                for (u, v) in ((i, j), (j, i)):
                    if u == t:
                        continue                      # sink has no outgoing arcs
                    if h == 0 and u != s:
                        continue                      # layer 0 only has source active
                    if h > 0 and (dist_from_s[u] is None or dist_from_s[u] > h):
                        continue                       # u not reachable that fast
                    if v == s:
                        continue                       # never re-enter source
                    if dist_from_s[v] is None or dist_from_s[v] > h + 1:
                        continue                       # v not reachable that fast
                    if h + 1 == H and v != t:
                        continue                       # last layer only feeds sink

                    vname = fvar(k, u, v, h)
                    flow_vars.append((vname, float(min(u_cap, d))))

                    # capacity link (physical edge, either direction)
                    ei, ej = (i, j) if i < j else (j, i)
                    add_coeff(vname, f"CAP_{ei}_{ej}", 1.0)

                    if h == 0:
                        add_coeff(vname, f"SUP_{k}", 1.0)          # u == s, outflow
                    else:
                        add_coeff(vname, cons_row(u, h), 1.0)      # outflow of u at layer h

                    if v == t:
                        add_coeff(vname, f"DEM_{k}", 1.0)
                    else:
                        add_coeff(vname, cons_row(v, h + 1), -1.0)  # inflow of v at layer h+1

    # ---- Emit MPS text ----
    L = []
    L.append(f"NAME          {name}")
    L.append("ROWS")
    L.append(" N  OBJ")
    for rname, sense, _ in rows:
        L.append(f" {sense}  {rname}")

    L.append("COLUMNS")
    L.append("    MARK0001  'MARKER'                 'INTORG'")
    for i, j, _c, _u in edges:
        vname = yvar(i, j)
        L.append(f"    {vname:<14s}  OBJ           {obj[vname]}")
        for rname, coeff in col_rows.get(vname, []):
            L.append(f"    {vname:<14s}  {rname:<14s}  {coeff}")
    L.append("    MARK0001  'MARKER'                 'INTEND'")

    for vname, _ub in flow_vars:
        for rname, coeff in col_rows.get(vname, []):
            L.append(f"    {vname:<14s}  {rname:<14s}  {coeff}")

    L.append("RHS")
    for rname, _sense, rhs in rows:
        if rhs != 0.0:
            L.append(f"    RHS           {rname:<14s}  {rhs}")

    L.append("BOUNDS")
    for i, j, _c, _u in edges:
        L.append(f" BV BOUND         {yvar(i, j)}")
    for vname, ub in flow_vars:
        L.append(f" UP BOUND         {vname:<14s}  {ub}")

    L.append("ENDATA")
    return "\n".join(L) + "\n"


def write_mps_gz(mps_text, path):
    with gzip.open(path, "wt") as f:
        f.write(mps_text)


def build_instance(name, n, edge_prob, num_commodities, hop_limit, seed, **kw):
    instance = generate_instance(n, edge_prob, num_commodities, hop_limit, seed, **kw)
    mps_text = build_layered_mps(name, instance)
    info = dict(n=n, edge_prob=edge_prob, num_commodities=len(instance["commodities"]),
                hop_limit=hop_limit, seed=seed, num_edges=len(instance["edges"]))
    return mps_text, info, instance


# ──────────────────────────────────────────────────────────────────────────
# Solving via mipster
# ──────────────────────────────────────────────────────────────────────────

def solve_with_mipster(mps_path, time_limit, extra_args=None):
    import time
    args = [MIPSTER, str(mps_path)]
    if extra_args:
        args += extra_args
    args += ["-sec", str(time_limit), "-solve"]
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
    infeasible = "infeasible" in out.lower()
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    nodes = int(nodes_m.group(1)) if nodes_m else None
    lb = float(lb_m.group(1)) if lb_m else None

    return dict(obj=obj, optimal=optimal, nodes=nodes, wall=round(wall, 2),
                lower_bound=lb, infeasible=infeasible, raw_out=out)


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
