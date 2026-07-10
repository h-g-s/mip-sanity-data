"""Shared library for Generalized Set Partitioning/Packing/Covering (SPPC)
instance generation: a single binary program mixing all three classical
row types over one shared set of columns (binary variables), modeled after
real crew-scheduling-style "generalized set partitioning" formulations.

  Variables:
    x_j in {0,1}    for each candidate column j (a "duty"/"pairing" choice)

  Objective: minimize sum_j c_j * x_j

  Row types (each row i is a subset S_i of columns):
    - Partition ("=1"):  sum_{j in S_i} x_j = 1     (task i must be done by
      exactly one of its candidate columns)
    - Packing   ("<=1"): sum_{j in S_i} x_j <= 1    (shared resource i used
      by at most one of the columns competing for it)
    - Covering  (">=1"): sum_{j in S_i} x_j >= 1    (requirement i must be
      met by at least one of its columns, redundancy allowed)

This combination is deliberately chosen to exercise the conflict-graph
infrastructure with BOTH original and complemented literals:
  - a degree-2 packing row x_i + x_j <= 1 gives a conflict edge between the
    ORIGINAL literals x_i, x_j (can't both be 1);
  - a degree-2 covering row x_i + x_j >= 1 gives a conflict edge between the
    COMPLEMENTED literals ~x_i, ~x_j (can't both be 0, i.e. not(x_i=0 and
    x_j=0));
  - a degree-2 partition row x_i + x_j = 1 gives BOTH simultaneously (x_i
    and x_j are exact complements of one another): the richest possible
    case for a conflict-graph implementation, since it must correctly
    combine a packing-type edge and a covering-type edge on the same pair.

Construction/feasibility strategy
----------------------------------
Each partition (task) row i gets 2-6 "candidate" columns; exactly one
candidate is flagged the row's *reference* candidate, drawn from a costlier
sub-range than the non-reference ("alternative") candidates -- so the
reference solution is deliberately expensive and the solver is tempted to
deviate towards cheaper alternatives (not necessarily successfully: this is
what forces genuine search).

Packing and covering rows are built DENSELY, sampling with heavy overlap
from the ENTIRE column pool (at most one column per task per row, since two
candidates of the same task are already mutually exclusive via the
partition row). The same column therefore recurs across MANY different
packing/covering rows -- much like classical hard set-partitioning
benchmarks where each column appears in several rows. This dense overlap is
what actually forces genuine branch-and-bound: an earlier design that built
each row independently from a single "hot" per-task candidate, or sampled
fresh candidates per row with little cross-row reuse, always solved
trivially at the root node (0 nodes) regardless of instance scale, because
the resulting packing/covering structure was too weakly coupled to create a
fractional-but-not-obviously-roundable LP relaxation.

Packing rows are drawn from NON-reference candidates plus at most one
optional reference candidate -- this guarantees the reference solution
(selecting exactly the reference candidate of every task row) never
violates a packing row. Covering rows always include at least one reference
candidate (guaranteeing >= 1 is met by the reference solution) plus dense
random extras (harmless for a ">=1" row regardless of their status).

The reference solution (one reference candidate per task row) is therefore
always feasible by construction; MIPster (or any solver) must still SEARCH
for the true optimum, since cheaper non-reference candidates/columns are
deliberately present and may or may not be usable depending on
packing/covering-row contention.
"""

import gzip
import random
from pathlib import Path

MIPSTER_PATH = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")


# ──────────────────────────────────────────────────────────────────────────
# Instance generation
# ──────────────────────────────────────────────────────────────────────────

def generate_instance(num_tasks, cand_range, num_packing, num_covering, seed,
                       pack_size_range=(3, 6), cover_size_range=(3, 6),
                       cost_range=(5, 30), ref_cost_range=None, alt_cost_range=None):
    """Build a random SPPC instance.

    Reference candidates are drawn from a costlier sub-range (``ref_cost_range``,
    defaults to the top third of ``cost_range``) while alternative (non-
    reference) candidates are drawn from a cheaper sub-range (``alt_cost_range``,
    defaults to the bottom two-thirds). This makes the reference solution
    deliberately unattractive/expensive so the solver is tempted to deviate
    towards cheaper alternatives.

    Packing and covering rows are built by sampling DENSELY and with
    replacement/overlap from the ENTIRE column pool (subject to at most one
    column per task per row, since two candidates of the same task are
    already mutually exclusive via the partition row and would make the
    packing/covering row structurally redundant). This means the same
    column recurs across MANY different packing/covering rows -- much like
    classical hard set-partitioning benchmarks where each column appears in
    several rows -- which is what actually forces genuine branch-and-bound
    (a sparse, one-off/independent-row design was tried first and always
    solved trivially at the root node regardless of instance scale).

    Returns dict with:
      columns: list of dicts {cost, task, is_reference}
      partition_rows: list of list[col_idx]        (=1 rows, one per task)
      packing_rows:   list of list[col_idx]         (<=1 rows)
      covering_rows:  list of list[col_idx]         (>=1 rows)
      reference_cost: sum of reference candidates' costs (a feasible upper
        bound, NOT necessarily optimal)
    """
    rng = random.Random(seed)

    lo, hi = cost_range
    span = hi - lo
    if ref_cost_range is None:
        ref_cost_range = (lo + round(span * 2 / 3), hi)
    if alt_cost_range is None:
        alt_cost_range = (lo, lo + round(span * 2 / 3))

    columns = []               # each: dict(cost, task, is_reference)
    task_candidates = []        # task_candidates[t] = list of column indices

    for t in range(num_tasks):
        k = rng.randint(*cand_range)
        ref_local = rng.randrange(k)
        cols_for_task = []
        for local_idx in range(k):
            is_ref = (local_idx == ref_local)
            cost = rng.randint(*(ref_cost_range if is_ref else alt_cost_range))
            col_idx = len(columns)
            columns.append(dict(cost=cost, task=t, is_reference=is_ref))
            cols_for_task.append(col_idx)
        task_candidates.append(cols_for_task)

    partition_rows = list(task_candidates)

    # reference_cols[t] = the column index of task t's reference candidate
    reference_cols = [
        next(j for j in task_candidates[t] if columns[j]["is_reference"])
        for t in range(num_tasks)
    ]
    reference_set = set(reference_cols)
    non_ref_all = [j for j in range(len(columns)) if j not in reference_set]

    # ---- Packing rows: dense, overlapping subsets of NON-reference columns
    # drawn from DIFFERENT tasks (at most one column per task per row) --
    # guarantees the all-reference solution never violates a packing row.
    packing_rows = []
    for _ in range(num_packing):
        size = rng.randint(*pack_size_range)
        pool = non_ref_all[:]
        rng.shuffle(pool)
        used_tasks = set()
        members = []
        for c in pool:
            if len(members) >= size:
                break
            t = columns[c]["task"]
            if t in used_tasks:
                continue
            members.append(c)
            used_tasks.add(t)
        # optionally add exactly one reference candidate (from a task not
        # already represented, to keep it interesting)
        if rng.random() < 0.4 and reference_cols:
            rc = rng.choice(reference_cols)
            if columns[rc]["task"] not in used_tasks:
                members.append(rc)
        members = sorted(set(members))
        if len(members) >= 2:
            packing_rows.append(members)

    # ---- Covering rows: at least one reference candidate + dense random
    # extras from the whole pool (harmless for a ">=1" row regardless).
    covering_rows = []
    for _ in range(num_covering):
        size = rng.randint(*cover_size_range)
        ref_c = rng.choice(reference_cols)
        members = {ref_c}
        pool = list(range(len(columns)))
        rng.shuffle(pool)
        for c in pool:
            if len(members) >= size:
                break
            members.add(c)
        covering_rows.append(sorted(members))

    reference_cost = sum(columns[j]["cost"] for j in reference_cols)

    return dict(
        num_columns=len(columns),
        columns=columns,
        partition_rows=partition_rows,
        packing_rows=packing_rows,
        covering_rows=covering_rows,
        reference_cols=reference_cols,
        reference_cost=reference_cost,
    )


def generate_instance_bug_repro_v1(num_tasks, cand_range, num_packing, num_covering, seed,
                                    pack_size_range=(2, 4), cover_size_range=(2, 4),
                                    cost_range=(5, 30)):
    """Frozen, exact reproduction of the ORIGINAL (pre-redesign)
    ``generate_instance`` logic used when the MIPster preprocessing
    wrong-optimal bug was first discovered (see
    ``mips/sppc_bug_wrongopt_preprocess.mps.gz``). This function must NEVER
    be changed -- it exists solely so that fixture can be regenerated
    byte-identically if ever needed, independent of any later evolution of
    ``generate_instance`` (whose packing-row/cost-range strategy has since
    been redesigned twice to create genuinely hard instances at scale).

    With num_tasks=3, cand_range=(2,3), num_packing=2, num_covering=2,
    seed=1, this produces the specific 7-variable/7-row instance where
    default MIPster settings claim a WRONG optimal (30, actually infeasible
    -- MIPster self-detects this and prints "Postprocessed model is
    infeasible - possible tolerance issue - try without preprocessing" but
    still reports the wrong result), while ``-preprocess off`` correctly
    finds the true optimum (43, exhaustively verified via brute force over
    all 2**7 = 128 combinations).
    """
    rng = random.Random(seed)

    columns = []
    task_candidates = []

    for t in range(num_tasks):
        k = rng.randint(*cand_range)
        ref_local = rng.randrange(k)
        cols_for_task = []
        for local_idx in range(k):
            cost = rng.randint(*cost_range)
            col_idx = len(columns)
            columns.append(dict(cost=cost, task=t, is_reference=(local_idx == ref_local)))
            cols_for_task.append(col_idx)
        task_candidates.append(cols_for_task)

    partition_rows = list(task_candidates)

    reference_cols = [
        next(j for j in task_candidates[t] if columns[j]["is_reference"])
        for t in range(num_tasks)
    ]
    reference_set = set(reference_cols)

    packing_rows = []
    for _ in range(num_packing):
        size = rng.randint(*pack_size_range)
        n_tasks_needed = min(size, num_tasks)
        tasks_sample = rng.sample(range(num_tasks), n_tasks_needed)
        members = []
        for t in tasks_sample:
            candidates = [c for c in task_candidates[t] if c not in reference_set]
            if candidates:
                members.append(rng.choice(candidates))
        if rng.random() < 0.5 and reference_cols:
            extra_task = rng.randrange(num_tasks)
            ref_col = reference_cols[extra_task]
            if ref_col not in members:
                members.append(ref_col)
        members = sorted(set(members))
        if len(members) >= 2:
            packing_rows.append(members)

    covering_rows = []
    for _ in range(num_covering):
        size = rng.randint(*cover_size_range)
        anchor_task = rng.randrange(num_tasks)
        members = {reference_cols[anchor_task]}
        pool = [j for j in range(len(columns)) if j != reference_cols[anchor_task]]
        extra = rng.sample(pool, min(size - 1, len(pool)))
        members.update(extra)
        covering_rows.append(sorted(members))

    reference_cost = sum(columns[j]["cost"] for j in reference_cols)

    return dict(
        num_columns=len(columns),
        columns=columns,
        partition_rows=partition_rows,
        packing_rows=packing_rows,
        covering_rows=covering_rows,
        reference_cols=reference_cols,
        reference_cost=reference_cost,
    )


# ──────────────────────────────────────────────────────────────────────────
# MPS construction
# ──────────────────────────────────────────────────────────────────────────

def build_sppc_mps(name, instance):
    columns = instance["columns"]
    n = len(columns)
    xvar = lambda j: f"x_{j}"

    rows = []                      # (name, sense, rhs)
    col_rows = {}                  # var -> list[(row_name, coeff)]

    def add_row(rname, sense, rhs):
        rows.append((rname, sense, rhs))

    def add_coeff(vname, rname, coeff=1.0):
        col_rows.setdefault(vname, []).append((rname, coeff))

    for i, members in enumerate(instance["partition_rows"]):
        rname = f"PART_{i}"
        add_row(rname, "E", 1.0)
        for j in members:
            add_coeff(xvar(j), rname)

    for i, members in enumerate(instance["packing_rows"]):
        rname = f"PACK_{i}"
        add_row(rname, "L", 1.0)
        for j in members:
            add_coeff(xvar(j), rname)

    for i, members in enumerate(instance["covering_rows"]):
        rname = f"COVER_{i}"
        add_row(rname, "G", 1.0)
        for j in members:
            add_coeff(xvar(j), rname)

    L = []
    L.append(f"NAME          {name}")
    L.append("ROWS")
    L.append(" N  OBJ")
    for rname, sense, _ in rows:
        L.append(f" {sense}  {rname}")

    L.append("COLUMNS")
    L.append("    MARK0001  'MARKER'                 'INTORG'")
    for j in range(n):
        vname = xvar(j)
        L.append(f"    {vname:<14s}  OBJ           {columns[j]['cost']}")
        for rname, coeff in col_rows.get(vname, []):
            L.append(f"    {vname:<14s}  {rname:<14s}  {coeff}")
    L.append("    MARK0001  'MARKER'                 'INTEND'")

    L.append("RHS")
    for rname, _sense, rhs in rows:
        L.append(f"    RHS           {rname:<14s}  {rhs}")

    L.append("BOUNDS")
    for j in range(n):
        L.append(f" BV BOUND         {xvar(j)}")

    L.append("ENDATA")
    return "\n".join(L) + "\n"


def write_mps_gz(mps_text, path):
    with gzip.open(path, "wt") as f:
        f.write(mps_text)


def build_instance(name, num_tasks, cand_range, num_packing, num_covering, seed, **kw):
    instance = generate_instance(num_tasks, cand_range, num_packing, num_covering, seed, **kw)
    mps_text = build_sppc_mps(name, instance)
    info = dict(num_tasks=num_tasks, num_columns=instance["num_columns"],
                num_packing=len(instance["packing_rows"]),
                num_covering=len(instance["covering_rows"]), seed=seed)
    return mps_text, info, instance


# ──────────────────────────────────────────────────────────────────────────
# Solving via mipster
# ──────────────────────────────────────────────────────────────────────────

def solve_with_mipster(mps_path, time_limit, extra_args=None):
    import re
    import subprocess
    import time
    args = [MIPSTER_PATH, str(mps_path)]
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
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    nodes = int(nodes_m.group(1)) if nodes_m else None
    lb = float(lb_m.group(1)) if lb_m else None

    return dict(obj=obj, optimal=optimal, nodes=nodes, wall=round(wall, 2),
                lower_bound=lb, raw_out=out)


def solve_with_solu(mps_path, sol_path, time_limit):
    import re
    import subprocess
    r = subprocess.run(
        [MIPSTER_PATH, str(mps_path), "-sec", str(time_limit), "-solve", "-solu", str(sol_path)],
        capture_output=True, text=True, timeout=time_limit + 30,
    )
    out = r.stdout + r.stderr
    obj_m = re.search(r"Objective value:\s*([\-0-9.eE]+)", out)
    optimal = "Optimal solution found" in out
    obj = float(obj_m.group(1)) if obj_m else None
    return dict(obj=obj, optimal=optimal, raw_out=out)
