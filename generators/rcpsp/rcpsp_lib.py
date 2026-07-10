"""Shared library for RCPSP (Resource-Constrained Project Scheduling Problem)
time-indexed MPS instance generation.

Formulation (Pritsker et al. time-indexed):
  Activities 0..n+1: 0 = dummy source (duration 0, no resource demand),
  1..n = real jobs, n+1 = dummy sink (duration 0, no resource demand).
  Precedence is a DAG; source precedes all jobs with no other predecessor,
  sink succeeds all jobs with no other successor (single terminal activity
  used to read off the makespan).

  Variables:
    x[j][t]  binary, 1 if job j starts at time t, for j in 1..n+1 and
              t in [ES[j], LS[j]] (time windows tightened via CPM against
              the current horizon T). The source (job 0) is a constant
              start-time-0 activity and needs no variable.

  Objective: minimize sum_t t * x[sink][t]   (start time of sink = makespan,
             since the sink has zero duration).

  Constraints:
    - Assignment:   sum_t x[j][t] = 1                      for each job j
    - Precedence:   sum_t t*x[j][t] - sum_t t*x[i][t] >= d[i]
                    for every precedence arc (i,j) with i a real job
                    (arcs from the dummy source need no constraint, since
                    d[source]=0 and ES already reflects this).
    - Resource:     sum_j sum_{t' <= t < t'+d[j]} r[j][k]*x[j][t'] <= R[k]
                    for every renewable resource k and every period t
                    (only real jobs contribute; source/sink have zero
                    demand).

Two-phase construction (per project convention):
  Phase 1: build the time-indexed model with horizon T = UB = sum of all
           job durations (a simple, always-valid upper bound: a fully
           serial schedule where jobs run one at a time never violates any
           resource capacity, as long as no single job's demand exceeds
           capacity, which the generator enforces). Solve to optimality
           with mipster to obtain the true optimal makespan T*.
  Phase 2: rebuild the time-indexed model with horizon T = T* (the tight,
           optimal horizon). This is the final, canonical MPS instance
           stored in mips/ -- it is provably equivalent (same optimal
           makespan) but much smaller than the phase-1 model, and solving
           it again should reproduce the same optimal objective as a
           sanity check.
"""

import gzip
import random
import re
import subprocess
import sys
from pathlib import Path

MIPSTER = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")


# ──────────────────────────────────────────────────────────────────────────
# Instance generation
# ──────────────────────────────────────────────────────────────────────────

def generate_instance(seed, n_jobs, n_resources,
                       dur_lo=2, dur_hi=8,
                       n_levels=None,
                       extra_edge_prob=0.3,
                       res_demand_lo=1, res_demand_hi=6,
                       res_capacity_factor=1.6):
    """Generate a random layered-DAG RCPSP instance.

    Activities: 0 = source, 1..n_jobs = real jobs, n_jobs+1 = sink.
    Jobs are assigned to levels 1..n_levels (topological layers); each job
    gets at least one predecessor from the previous level (or the source
    if level==1), plus possible extra precedence edges from earlier levels
    (extra_edge_prob) for added structure. Jobs with no successor connect
    to the sink; jobs with no predecessor connect from the source.

    Resource capacities are derived from the demand distribution so that
    genuine contention exists (capacity < sum of concurrent demands in
    typical schedules) but no single job's demand ever exceeds capacity
    (so a purely serial schedule is always resource-feasible).
    """
    rng = random.Random(seed)
    n = n_jobs
    sink = n + 1

    if n_levels is None:
        n_levels = max(2, round(n ** 0.5))

    # Assign each job to a level 1..n_levels (roughly balanced).
    levels = [1 + (j % n_levels) for j in range(n)]
    rng.shuffle(levels)
    jobs_by_level = {L: [] for L in range(1, n_levels + 1)}
    for j, L in enumerate(levels, start=1):
        jobs_by_level[L].append(j)

    preds = {a: set() for a in range(n + 2)}
    succs = {a: set() for a in range(n + 2)}

    def add_edge(i, j):
        if i != j and j not in preds.get(i, set()):
            preds[j].add(i)
            succs[i].add(j)

    for L in range(1, n_levels + 1):
        for j in jobs_by_level[L]:
            if L == 1:
                add_edge(0, j)
            else:
                prev_jobs = jobs_by_level[L - 1]
                if prev_jobs:
                    add_edge(rng.choice(prev_jobs), j)
                else:
                    add_edge(0, j)
                # extra precedence edges from any strictly earlier level
                for Lp in range(1, L):
                    for i in jobs_by_level[Lp]:
                        if rng.random() < extra_edge_prob:
                            add_edge(i, j)

    # Ensure every job with no predecessor connects from source, and every
    # job with no successor connects to sink.
    for j in range(1, n + 1):
        if not preds[j]:
            add_edge(0, j)
        if not succs[j]:
            add_edge(j, sink)
    if not preds[sink]:
        # degenerate all-source case shouldn't happen for n>=1, but guard anyway
        for j in range(1, n + 1):
            add_edge(j, sink)

    # Durations: source/sink are 0-duration dummies.
    durations = [0] * (n + 2)
    for j in range(1, n + 1):
        durations[j] = rng.randint(dur_lo, dur_hi)

    # Resource demands and capacities.
    demands = [[0] * n_resources for _ in range(n + 2)]
    for j in range(1, n + 1):
        for k in range(n_resources):
            demands[j][k] = rng.randint(res_demand_lo, res_demand_hi)

    capacities = []
    for k in range(n_resources):
        max_demand = max(demands[j][k] for j in range(1, n + 1))
        avg_demand = sum(demands[j][k] for j in range(1, n + 1)) / n
        cap = max(max_demand, round(avg_demand * res_capacity_factor))
        capacities.append(cap)

    return dict(
        n_jobs=n, n_resources=n_resources, sink=sink,
        durations=durations, demands=demands, capacities=capacities,
        preds=preds, succs=succs,
    )


# ──────────────────────────────────────────────────────────────────────────
# CPM time-window computation
# ──────────────────────────────────────────────────────────────────────────

def topological_order(instance):
    """Kahn's algorithm topological order over activities 0..n+1."""
    n = instance["n_jobs"]
    sink = instance["sink"]
    preds = instance["preds"]
    succs = instance["succs"]
    indeg = {a: len(preds[a]) for a in range(n + 2)}
    queue = [a for a in range(n + 2) if indeg[a] == 0]
    order = []
    while queue:
        a = queue.pop(0)
        order.append(a)
        for b in succs[a]:
            indeg[b] -= 1
            if indeg[b] == 0:
                queue.append(b)
    assert len(order) == n + 2, "instance precedence graph must be acyclic"
    return order


def compute_time_windows(instance, horizon):
    """Forward pass for ES (earliest start, ignoring resources), backward
    pass for LS (latest start, given horizon T), both clipped to
    [0, horizon]."""
    n = instance["n_jobs"]
    sink = instance["sink"]
    durations = instance["durations"]
    preds = instance["preds"]
    succs = instance["succs"]
    order = topological_order(instance)

    ES = {0: 0}
    for a in order:
        if a == 0:
            continue
        ES[a] = max((ES[p] + durations[p] for p in preds[a]), default=0)

    LS = {sink: horizon}
    for a in reversed(order):
        if a == sink:
            continue
        LS[a] = min((LS[s] - durations[a] for s in succs[a]), default=horizon)

    for a in range(n + 2):
        if ES[a] > LS[a]:
            # horizon too tight for this precedence chain; clip (caller
            # should ensure horizon >= critical path length)
            LS[a] = ES[a]
    return ES, LS


# ──────────────────────────────────────────────────────────────────────────
# MPS writer
# ──────────────────────────────────────────────────────────────────────────

def build_time_indexed_mps(name, instance, horizon):
    """Return MPS text for the time-indexed RCPSP model with the given
    horizon T. Returns (mps_text, ES, LS)."""
    n = instance["n_jobs"]
    sink = instance["sink"]
    n_res = instance["n_resources"]
    durations = instance["durations"]
    demands = instance["demands"]
    capacities = instance["capacities"]
    preds = instance["preds"]

    ES, LS = compute_time_windows(instance, horizon)

    # variable jobs: 1..n (real) + sink
    var_jobs = list(range(1, n + 1)) + [sink]

    # column index: col_x[j] -> {t: col_idx}
    col_x = {}
    all_cols = []  # (col_idx, name)
    idx = 0
    for j in var_jobs:
        col_x[j] = {}
        for t in range(ES[j], LS[j] + 1):
            col_x[j][t] = idx
            all_cols.append((idx, f"x_{j}_{t}"))
            idx += 1
    n_cols = idx

    rows = []  # (name, sense, rhs, {col: coef})

    def add(rname, sense, rhs, coefs):
        rows.append((rname, sense, rhs, coefs))

    # Assignment rows
    for j in var_jobs:
        add(f"asgn_{j}", "E", 1.0, {col_x[j][t]: 1.0 for t in col_x[j]})

    # Precedence rows: for arc (i,j) with i a real job (i>=1)
    for j in var_jobs:
        for i in preds[j]:
            if i == 0:
                continue
            coefs = {}
            for t, ci in col_x[j].items():
                coefs[ci] = coefs.get(ci, 0.0) + t
            for t, ci in col_x[i].items():
                coefs[ci] = coefs.get(ci, 0.0) - t
            add(f"prec_{i}_{j}", "G", float(durations[i]), coefs)

    # Resource rows: for each resource k, each period t in [0, horizon-1]
    for k in range(n_res):
        for t in range(horizon):
            coefs = {}
            for j in range(1, n + 1):
                dj = durations[j]
                rjk = demands[j][k]
                if rjk == 0 or dj == 0:
                    continue
                for tp, ci in col_x[j].items():
                    if tp <= t < tp + dj:
                        coefs[ci] = coefs.get(ci, 0.0) + rjk
            if coefs:
                add(f"res_{k}_{t}", "L", float(capacities[k]), coefs)

    # column -> rows inverted index
    col_rows = {}
    for ri, (_, _, _, coefs) in enumerate(rows):
        for ci, coef in coefs.items():
            col_rows.setdefault(ci, []).append((ri, coef))

    # objective: minimize sum_t t * x[sink][t]
    obj = {}
    for t, ci in col_x[sink].items():
        if t != 0:
            obj[ci] = float(t)

    L = []
    L.append(f"NAME          {name}")
    L.append("ROWS")
    L.append(" N  OBJ")
    for rname, sense, _, _ in rows:
        L.append(f" {sense}  {rname}")

    L.append("COLUMNS")
    L.append("    MARK0000  'MARKER'                 'INTORG'")
    for ci, cname in all_cols:
        if ci in obj:
            L.append(f"    {cname:<14s}  OBJ           {obj[ci]}")
        for ri, coef in col_rows.get(ci, []):
            rname = rows[ri][0]
            L.append(f"    {cname:<14s}  {rname:<14s}  {coef}")
    L.append("    MARK0001  'MARKER'                 'INTEND'")

    L.append("RHS")
    for rname, _, rhs, _ in rows:
        if rhs != 0.0:
            L.append(f"    RHS           {rname:<14s}  {rhs}")

    L.append("BOUNDS")
    for ci, cname in all_cols:
        L.append(f" BV BOUND         {cname}")

    L.append("ENDATA")
    return "\n".join(L) + "\n", ES, LS


def write_mps_gz(mps_text, path):
    with gzip.open(path, "wt") as f:
        f.write(mps_text)


# ──────────────────────────────────────────────────────────────────────────
# Solving via mipster
# ──────────────────────────────────────────────────────────────────────────

def solve_with_mipster(mps_path, time_limit, extra_args=None):
    """Solve mps_path with mipster; return dict with obj, optimal, nodes,
    wall, lower_bound."""
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
    """Solve and write the .sol reference file."""
    r = subprocess.run(
        [MIPSTER, str(mps_path), "-sec", str(time_limit), "-solve", "-solu", str(sol_path)],
        capture_output=True, text=True, timeout=time_limit + 30,
    )
    out = r.stdout + r.stderr
    obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    return dict(obj=obj, optimal=optimal, raw_out=out)


# ──────────────────────────────────────────────────────────────────────────
# Two-phase construction
# ──────────────────────────────────────────────────────────────────────────

def two_phase_build(name, instance, out_dir, phase1_time_limit=60, phase2_time_limit=100,
                     scratch_dir=None, verbose=True):
    """Phase 1: solve with horizon = sum(durations) UB to get optimal makespan.
    Phase 2: rebuild with horizon = optimal makespan, write final MPS into
    out_dir, solve again as a sanity check.

    Returns a dict with phase1/phase2 stats, or None if phase 1 failed to
    prove optimality.
    """
    durations = instance["durations"]
    ub_horizon = sum(durations)

    scratch_dir = Path(scratch_dir) if scratch_dir else Path("/tmp/rcpsp_scratch")
    scratch_dir.mkdir(exist_ok=True, parents=True)
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True, parents=True)

    mps1_text, ES1, LS1 = build_time_indexed_mps(f"{name}_p1", instance, ub_horizon)
    mps1_path = scratch_dir / f"{name}_p1.mps.gz"
    write_mps_gz(mps1_text, mps1_path)
    n_vars1 = mps1_text.count("\n    x_")

    if verbose:
        print(f"  [phase1] horizon={ub_horizon} solving...", flush=True)
    r1 = solve_with_mipster(mps1_path, phase1_time_limit)
    mps1_path.unlink(missing_ok=True)

    if not r1["optimal"] or r1["obj"] is None:
        if verbose:
            print(f"  [phase1] NOT proven optimal (obj={r1['obj']}) -- skipping", flush=True)
        return None

    T_opt = int(round(r1["obj"]))
    if verbose:
        print(f"  [phase1] optimal makespan T*={T_opt} wall={r1['wall']}s nodes={r1['nodes']}", flush=True)

    mps2_text, ES2, LS2 = build_time_indexed_mps(name, instance, T_opt)
    mps2_path = out_dir / f"{name}.mps.gz"
    write_mps_gz(mps2_text, mps2_path)

    if verbose:
        print(f"  [phase2] horizon={T_opt} solving...", flush=True)
    r2 = solve_with_mipster(mps2_path, phase2_time_limit)

    if verbose:
        print(f"  [phase2] obj={r2['obj']} optimal={r2['optimal']} "
              f"wall={r2['wall']}s nodes={r2['nodes']}", flush=True)

    return dict(
        name=name, ub_horizon=ub_horizon, T_opt=T_opt,
        phase1=r1, phase2=r2, mps_path=mps2_path,
    )
