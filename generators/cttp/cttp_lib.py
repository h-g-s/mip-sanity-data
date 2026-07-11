"""Shared library for the Class-Teacher Timetabling Problem (CTTP), in the
spirit of the classical formulation studied by Santos et al. (e.g. "Strong
bounds with cut and column generation for class-teacher timetabling",
Annals of OR, 2012): the core combinatorial structure is a bipartite
multigraph edge-coloring between classes and teachers (each required
weekly lesson is an "edge" that must be assigned a timeslot, with no class
or teacher double-booked at the same slot) -- but extended here with the
scheduling rules and soft preferences actually requested for this dataset:

  - The week is split into ``num_days`` days of ``slots_per_day`` timeslots
    each (a "day" = a contiguous block of slots; NOT wrapped across days).
  - Each (class, teacher) pair with a nonzero weekly requirement must teach
    either 1 or 2 lessons on any day it meets; if 2, they must be in
    CONSECUTIVE timeslots of that day (a "double period").
  - Teachers may be unavailable at specific (day, slot) combinations
    (part-time contracts, other commitments) -- no lesson may be scheduled
    for that teacher at an unavailable slot.
  - Objective (two lexicographically-weighted components, combined with
    tunable weights so instances can stress one or the other):
      1) MIN TEACHER DAYS-OFF preference: minimize the total number of
         (teacher, day) pairs on which that teacher has ANY lesson at all
         (across every class they teach that day) -- i.e. concentrate each
         teacher's whole weekly workload into as FEW distinct days as
         possible, ideally leaving some days completely free.
      2) MIN GAPS: minimize the number of idle ("hole") timeslots that fall
         strictly between a teacher's first and last used slot on any
         given day they do work -- i.e. once a teacher is in the building
         that day, their lessons (across ALL classes) should be back-to-back
         with no free periods in between.

Formulation
-----------
For each required (class c, teacher t) meeting with weekly requirement
``req[c,t] > 0``, and for each day d, define a small set of DAILY PATTERNS:
  - "single(s)"  -- exactly one lesson, at slot s               (1 lesson)
  - "double(s)"  -- exactly two lessons, at consecutive slots
                    (s, s+1)                                     (2 lessons)
A pattern is only offered if all of its slots are available for teacher t
on day d (not marked unavailable). Binary variable z[c,t,d,k] selects at
most one pattern per (c,t,d) triple -- this directly enforces "1 or 2
lessons per day, and if 2 then consecutive" by construction (there is no
way to represent 2 non-consecutive lessons, or 3+ lessons, in a day).

  sum_k z[c,t,d,k] <= 1                         for every (c,t) in M, day d
  sum_{d,k} lessons(k) * z[c,t,d,k] = req[c,t]  for every (c,t) in M

Slot-occupancy auxiliary variables (continuous in [0,1], forced integral by
the equality/definition constraints below since all inputs are binary):

  o[t,d,s] = sum over (c,t) in M, k using slot s of z[c,t,d,k]   (teacher
             busy indicator; <= 1 enforces "teacher not double-booked")
  e[c,d,s] = sum over (c,t) in M, k using slot s of z[c,t,d,k]   (class
             busy indicator; <= 1 enforces "class not double-booked")

Teacher day-off indicator (binary, forced to the OR of that day's o's by
minimization pressure + one-sided >= constraints -- classic "aggregated OR"
trick, cheaper than a tight big-M):

  w[t,d] >= o[t,d,s]                             for every slot s

Prefix/suffix "has taught by/from here" indicators (continuous [0,1],
again pinned to their true OR value by minimization pressure since they
only ever appear with POSITIVE weight on the gap-forcing constraint, so
the solver has no incentive to inflate them, and the >= constraints forbid
deflating them below the truth):

  before[t,d,0] = 0
  before[t,d,s] >= before[t,d,s-1]                for s = 1..S-1
  before[t,d,s] >= o[t,d,s-1]                     for s = 1..S-1

  after[t,d,S-1] = 0
  after[t,d,s]   >= after[t,d,s+1]                for s = 0..S-2
  after[t,d,s]   >= o[t,d,s+1]                     for s = 0..S-2

Gap indicator: slot s is a genuine "hole" on day d for teacher t iff it is
NOT used (o=0) but the teacher DOES teach something earlier that day
(before=1) AND something later that day (after=1):

  gap[t,d,s] >= before[t,d,s] + after[t,d,s] - o[t,d,s] - 1

No upper bound is needed on gap/before/after: minimization alone drives
each down to its true (0/1) value given the one-sided >= constraints.

Objective:  minimize  day_weight * sum_{t,d} w[t,d]
                     + gap_weight * sum_{t,d,s} gap[t,d,s]

This couples DIFFERENT (class, teacher) meetings together (through shared
teacher/class slot-occupancy and the teacher-level day-off/gap objective),
which is what makes the problem genuinely combinatorial rather than
decomposable per-pair -- similar in spirit to how SPPC's dense row overlap
forces real branch-and-bound.
"""

import gzip
import random
from pathlib import Path

MIPSTER_PATH = str(Path.home() / "prog" / "mipster" / "bin" / "mipster")


# ──────────────────────────────────────────────────────────────────────────
# Requirement matrix + teacher-unavailability generation
# ──────────────────────────────────────────────────────────────────────────

def generate_req(num_classes, num_teachers, capacity, subjects_per_class_range,
                  req_range, seed, max_tries_per_subject=200,
                  max_class_utilization=0.9, max_teacher_utilization=0.9,
                  teacher_available_days=None):
    """Randomly build a sparse req[c,t] (weekly lesson requirement) matrix.

    Each class gets a random number of "subjects" (subjects_per_class_range),
    each taught by a distinct teacher (teachers CAN be shared across several
    classes) with a random weekly lesson count (req_range). Utilization caps
    keep both classes and teachers below full calendar capacity so a
    feasible schedule is achievable, while still generating dense sharing
    (contention) among classes/teachers.

    ``teacher_available_days[t]`` (if given) is the number of days on which
    teacher t is NOT fully unavailable; the requirement is capped at
    ``2 * available_days`` (max 2 lessons/day) as a cheap NECESSARY
    feasibility condition -- avoids the obviously-infeasible case of asking
    a teacher for more lessons than could ever fit even ignoring all other
    classes/teachers.
    """
    rng = random.Random(seed)
    req = {}
    class_load = [0] * num_classes
    teacher_load = [0] * num_teachers
    class_cap = capacity * max_class_utilization
    teacher_cap = capacity * max_teacher_utilization

    for c in range(num_classes):
        k = rng.randint(*subjects_per_class_range)
        chosen = set()
        tries = 0
        while len(chosen) < k and tries < max_tries_per_subject * k:
            tries += 1
            t = rng.randrange(num_teachers)
            if t in chosen:
                continue
            r = rng.randint(*req_range)
            if teacher_available_days is not None:
                r = min(r, 2 * teacher_available_days[t])
                if r <= 0:
                    continue
            if class_load[c] + r > class_cap:
                continue
            if teacher_load[t] + r > teacher_cap:
                continue
            chosen.add(t)
            req[(c, t)] = r
            class_load[c] += r
            teacher_load[t] += r
    return req


def generate_unavailability(num_teachers, num_days, slots_per_day, seed,
                             p_random_slot=0.05, p_day_off=0.1):
    """Return unavail[t] = set of (day, slot) the teacher CANNOT be used.

    Two independent mechanisms, combined:
      - p_day_off: probability a teacher has one full random day marked
        entirely unavailable (e.g. part-time contract, external duty day).
      - p_random_slot: independent probability each remaining (day, slot)
        is individually unavailable (e.g. admin period, other school).
    """
    rng = random.Random(seed * 1000003 + 7)
    unavail = [set() for _ in range(num_teachers)]
    for t in range(num_teachers):
        if rng.random() < p_day_off:
            off_day = rng.randrange(num_days)
            for s in range(slots_per_day):
                unavail[t].add((off_day, s))
        for d in range(num_days):
            for s in range(slots_per_day):
                if (d, s) in unavail[t]:
                    continue
                if rng.random() < p_random_slot:
                    unavail[t].add((d, s))
    return unavail


# ──────────────────────────────────────────────────────────────────────────
# Daily patterns
# ──────────────────────────────────────────────────────────────────────────

def day_patterns(slots_per_day, unavailable_slots):
    """List of (kind, slots_tuple, lessons) patterns usable on a single day,
    given the set of slots (ints) UNAVAILABLE for a specific teacher on
    that day. ``kind`` is 'single' or 'double' (2 consecutive slots)."""
    patterns = []
    for s in range(slots_per_day):
        if s not in unavailable_slots:
            patterns.append(("single", (s,), 1))
    for s in range(slots_per_day - 1):
        if s not in unavailable_slots and (s + 1) not in unavailable_slots:
            patterns.append(("double", (s, s + 1), 2))
    return patterns


# ──────────────────────────────────────────────────────────────────────────
# Instance generation
# ──────────────────────────────────────────────────────────────────────────

def generate_instance(num_classes, num_teachers, num_days, slots_per_day,
                       subjects_per_class_range, req_range, seed,
                       day_weight=10.0, gap_weight=1.0,
                       p_random_slot=0.05, p_day_off=0.1,
                       max_class_utilization=0.9, max_teacher_utilization=0.9):
    capacity = num_days * slots_per_day
    unavail = generate_unavailability(num_teachers, num_days, slots_per_day,
                                       seed, p_random_slot=p_random_slot,
                                       p_day_off=p_day_off)
    # a day counts as "available" for a teacher if at least 1 slot is free
    # that day (a lesson could still be scheduled, even if not a double)
    teacher_available_days = []
    for t in range(num_teachers):
        avail_days = 0
        for d in range(num_days):
            if any((d, s) not in unavail[t] for s in range(slots_per_day)):
                avail_days += 1
        teacher_available_days.append(avail_days)

    req = generate_req(num_classes, num_teachers, capacity,
                        subjects_per_class_range, req_range, seed,
                        max_class_utilization=max_class_utilization,
                        max_teacher_utilization=max_teacher_utilization,
                        teacher_available_days=teacher_available_days)
    meetings = sorted(req.keys())

    # z_vars[(c,t)][d] = list of (pattern_idx, kind, slots, lessons)
    z_vars = {}
    for (c, t) in meetings:
        per_day = []
        for d in range(num_days):
            unavail_today = {s for (dd, s) in unavail[t] if dd == d}
            per_day.append(day_patterns(slots_per_day, unavail_today))
        z_vars[(c, t)] = per_day

    return dict(
        num_classes=num_classes, num_teachers=num_teachers,
        num_days=num_days, slots_per_day=slots_per_day,
        req=req, meetings=meetings, unavail=unavail, z_vars=z_vars,
        day_weight=day_weight, gap_weight=gap_weight,
    )


# ──────────────────────────────────────────────────────────────────────────
# MPS construction
# ──────────────────────────────────────────────────────────────────────────

def build_cttp_mps(name, instance):
    nc = instance["num_classes"]
    nt = instance["num_teachers"]
    nd = instance["num_days"]
    ns = instance["slots_per_day"]
    req = instance["req"]
    meetings = instance["meetings"]
    z_vars = instance["z_vars"]
    day_weight = instance["day_weight"]
    gap_weight = instance["gap_weight"]

    zvar = lambda c, t, d, k: f"z_{c}_{t}_{d}_{k}"
    ovar = lambda t, d, s: f"o_{t}_{d}_{s}"
    evar = lambda c, d, s: f"e_{c}_{d}_{s}"
    wvar = lambda t, d: f"w_{t}_{d}"
    bvar = lambda t, d, s: f"bf_{t}_{d}_{s}"
    avar = lambda t, d, s: f"af_{t}_{d}_{s}"
    gvar = lambda t, d, s: f"gp_{t}_{d}_{s}"

    rows = []               # (name, sense, rhs)
    col_rows = {}           # var -> list[(row_name, coeff)]
    obj_coeff = {}          # var -> cost
    bin_vars = []           # binary (integer) variables
    cont_vars = []          # continuous vars, all bounded to [0,1]
    fixed_zero = []         # vars fixed to 0 via FX bound

    def add_row(rname, sense, rhs):
        rows.append((rname, sense, rhs))

    def add_coeff(vname, rname, coeff=1.0):
        col_rows.setdefault(vname, []).append((rname, coeff))

    # o[t,d,s] busy-by-slot occupancy for teachers using slot s on day d
    o_users = {(t, d, s): [] for t in range(nt) for d in range(nd) for s in range(ns)}
    e_users = {(c, d, s): [] for c in range(nc) for d in range(nd) for s in range(ns)}

    # --- z variables + per-(c,t) at-most-one-pattern-per-day + weekly req ---
    for (c, t) in meetings:
        for d in range(nd):
            patterns = z_vars[(c, t)][d]
            rname_daily = f"DAY_{c}_{t}_{d}"
            add_row(rname_daily, "L", 1.0)
            for k, (kind, slots, lessons) in enumerate(patterns):
                v = zvar(c, t, d, k)
                bin_vars.append(v)
                add_coeff(v, rname_daily, 1.0)
                add_coeff(v, f"REQ_{c}_{t}", float(lessons))
                for s in slots:
                    o_users[(t, d, s)].append(v)
                    e_users[(c, d, s)].append(v)
        add_row(f"REQ_{c}_{t}", "E", float(req[(c, t)]))

    # --- o[t,d,s] definition + teacher-not-double-booked (<=1 via bound) ---
    for t in range(nt):
        for d in range(nd):
            for s in range(ns):
                v = ovar(t, d, s)
                cont_vars.append(v)
                rname = f"OCC_{t}_{d}_{s}"
                add_row(rname, "E", 0.0)
                add_coeff(v, rname, 1.0)
                for zv in o_users[(t, d, s)]:
                    add_coeff(zv, rname, -1.0)

    # --- e[c,d,s] definition + class-not-double-booked (<=1 via bound) ---
    for c in range(nc):
        for d in range(nd):
            for s in range(ns):
                v = evar(c, d, s)
                cont_vars.append(v)
                rname = f"CLS_{c}_{d}_{s}"
                add_row(rname, "E", 0.0)
                add_coeff(v, rname, 1.0)
                for zv in e_users[(c, d, s)]:
                    add_coeff(zv, rname, -1.0)

    # --- w[t,d] day-off indicator ---
    for t in range(nt):
        for d in range(nd):
            v = wvar(t, d)
            bin_vars.append(v)
            obj_coeff[v] = day_weight
            for s in range(ns):
                rname = f"WDEF_{t}_{d}_{s}"
                add_row(rname, "G", 0.0)
                add_coeff(v, rname, 1.0)
                add_coeff(ovar(t, d, s), rname, -1.0)

    # --- before[t,d,s] / after[t,d,s] prefix/suffix OR chains ---
    for t in range(nt):
        for d in range(nd):
            for s in range(ns):
                bv = bvar(t, d, s)
                av = avar(t, d, s)
                cont_vars.append(bv)
                cont_vars.append(av)
                if s == 0:
                    fixed_zero.append(bv)
                else:
                    r1 = f"BFCH_{t}_{d}_{s}"
                    add_row(r1, "G", 0.0)
                    add_coeff(bv, r1, 1.0)
                    add_coeff(bvar(t, d, s - 1), r1, -1.0)
                    r2 = f"BFO_{t}_{d}_{s}"
                    add_row(r2, "G", 0.0)
                    add_coeff(bv, r2, 1.0)
                    add_coeff(ovar(t, d, s - 1), r2, -1.0)
                if s == ns - 1:
                    fixed_zero.append(av)
                else:
                    r3 = f"AFCH_{t}_{d}_{s}"
                    add_row(r3, "G", 0.0)
                    add_coeff(av, r3, 1.0)
                    add_coeff(avar(t, d, s + 1), r3, -1.0)
                    r4 = f"AFO_{t}_{d}_{s}"
                    add_row(r4, "G", 0.0)
                    add_coeff(av, r4, 1.0)
                    add_coeff(ovar(t, d, s + 1), r4, -1.0)

    # --- gap[t,d,s] forcing constraint ---
    for t in range(nt):
        for d in range(nd):
            for s in range(ns):
                gv = gvar(t, d, s)
                cont_vars.append(gv)
                obj_coeff[gv] = gap_weight
                rname = f"GAP_{t}_{d}_{s}"
                add_row(rname, "G", -1.0)
                add_coeff(gv, rname, 1.0)
                add_coeff(bvar(t, d, s), rname, -1.0)
                add_coeff(avar(t, d, s), rname, -1.0)
                add_coeff(ovar(t, d, s), rname, 1.0)

    # --- emit MPS text ---
    L = []
    L.append(f"NAME          {name}")
    L.append("ROWS")
    L.append(" N  OBJ")
    for rname, sense, _ in rows:
        L.append(f" {sense}  {rname}")

    L.append("COLUMNS")
    L.append("    MARK0001  'MARKER'                 'INTORG'")
    for v in bin_vars:
        c = obj_coeff.get(v, 0.0)
        L.append(f"    {v:<16s}  OBJ           {c}")
        for rname, coeff in col_rows.get(v, []):
            L.append(f"    {v:<16s}  {rname:<14s}  {coeff}")
    L.append("    MARK0001  'MARKER'                 'INTEND'")
    for v in cont_vars:
        c = obj_coeff.get(v, 0.0)
        L.append(f"    {v:<16s}  OBJ           {c}")
        for rname, coeff in col_rows.get(v, []):
            L.append(f"    {v:<16s}  {rname:<14s}  {coeff}")

    L.append("RHS")
    for rname, _sense, rhs in rows:
        L.append(f"    RHS           {rname:<14s}  {rhs}")

    L.append("BOUNDS")
    for v in bin_vars:
        L.append(f" BV BOUND         {v}")
    fixed_zero_set = set(fixed_zero)
    for v in cont_vars:
        if v in fixed_zero_set:
            L.append(f" FX BOUND         {v}          0.0")
        else:
            L.append(f" UP BOUND         {v}          1.0")

    L.append("ENDATA")
    return "\n".join(L) + "\n"


def write_mps_gz(mps_text, path):
    with gzip.open(path, "wt") as f:
        f.write(mps_text)


def build_instance(name, num_classes, num_teachers, num_days, slots_per_day,
                    subjects_per_class_range, req_range, seed, **kw):
    instance = generate_instance(num_classes, num_teachers, num_days, slots_per_day,
                                  subjects_per_class_range, req_range, seed, **kw)
    mps_text = build_cttp_mps(name, instance)
    info = dict(num_classes=num_classes, num_teachers=num_teachers,
                num_days=num_days, slots_per_day=slots_per_day,
                num_meetings=len(instance["meetings"]),
                total_req=sum(instance["req"].values()), seed=seed)
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
    infeasible = "infeasible" in out.lower()
    obj = float(obj_m.group(1)) if obj_m else None
    nodes = int(nodes_m.group(1)) if nodes_m else None
    lb = float(lb_m.group(1)) if lb_m else None

    return dict(obj=obj, optimal=optimal, infeasible=infeasible, nodes=nodes,
                wall=round(wall, 2), lower_bound=lb, raw_out=out)


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
