# mip-sanity-data

## Overview

**16 generated problem families (365 instances) plus 6 imported MIPLIB
2017(+spp) reference instances plus 65 imported MIPLIB3 (1996 classic set)
instances plus 35 imported public CBC-regression-test-set instances — 471
instances total.** Each instance ships as a `.mps.gz` file
with a certified best-known (in most cases optimal) objective value in
`bks.tsv` and at least one reference integer-feasible solution in `sols/`.
Every generated family has a generator under `generators/<family>/` so the
dataset can be regenerated, extended, or ported to another solver's test
suite. The 6 MIPLIB 2017(+spp) instances are taken directly from MIPster's
own C-interface regression test suite (`test/fixtures/`), included here for
extra external-benchmark coverage. The 65 MIPLIB3 instances are the classic
real-world 1996 MIPLIB benchmark set, included for broad, well-known
regression coverage.

## Dataset with interesting mip instances (in .mps.gz) for quick tests with reference:

- optimal/best known solution value (bks.tsv)
- complete integer feasible solution(s) - from the best known solution at least-
    - useful to debug wrong cuts/pre-processing/bound tightening

## By interesting we mean

- not trivially solvable, i.e. exercises LP, pre-proc, cuts, b&b
- not too expensive to run: we have limited time for tests and it is always better when we can investigate problems using instances which are quick to debug, ideally producing interesting results (i.e. feasible solution(s) or, even better, complete the search in 5 seconds to 2 minutes
- not required to prove optimality always in truncated runs (limited nodes and time limit), but they should at least typically find one or more integer feasible solutions during this time
- code coverage:
    - tests should cover most of the code, i.e. some cuts/heuristic/pre-processing parts only succeed in specific instances

## What to verify ?
### Validation scripts for mip solvers should check:

- for all each integer feasible solutions produced by the solver:
    - primal feasibility, validating variable values assigned (bound feasibility), integrality and constraint satisfaction
    - objective function: recompute the FO and validate for each feasible solution found, we can have the same absolute tolerance (1e-4) and also a relative tolerance
- for the case where search was concluded (i.e. not stopped due to time / node or any other limit):
    - IF optimality is claimed by the solver (search completed), then the best objective solution value found should match the expected optimal
    - IF problem is claimed to be infeasible, we should check if this instance is really infeasible
- tolerances : could be 1e-4, looser than default tolerances of solvers as post-processing and un-scaling can introduce some additional errors

## Problem families

| Family | Instances | Description |
|---|---|---|
| [`jssp`](generators/jssp) | 21 | Job Shop Scheduling — disjunctive/big-M formulation (per-job operation sequencing on machines, no overlap); classic Fisher & Thompson / Lawrence / Applegate & Cook benchmarks with certified makespans. |
| [`cvrp`](generators/cvrp) | 33 | Capacitated Vehicle Routing (and Pickup-Delivery variant) — MTZ-style load-tracking subtour elimination `u[i]-u[j]+Q*x[i,j] <= Q-d[j]`. |
| [`bpc`](generators/bpc) | 21 | Bin Packing with Conflicts — classic bin packing plus pairwise item-conflict constraints forbidding certain items from sharing a bin. |
| [`gap`](generators/gap) | 26 | Generalized Assignment Problem — assign tasks to capacitated agents minimizing cost; varies agent/task ratio, capacity tightness, and cost correlation. |
| [`mis`](generators/mis) | 25 | Maximum (Weighted) Independent Set — canonical clique-cut/odd-hole testbed; independent set in G ≡ clique in complement graph. |
| [`spp`](generators/spp) | 23 | Set Packing Problem — maximize weighted disjoint sets picked; conflict graph forms maximal cliques, exercising clique/odd-wheel cuts. |
| [`qap`](generators/qap) | 19 | Quadratic Assignment Problem — facility-location cost `sum f[i][j]*d[x[i]][x[j]]`, linearized (Kaufman-Broeckx) into a MIP. |
| [`graph_coloring`](generators/graph_coloring) | 27 | Graph Coloring — asymmetric representatives formulation (each color class represented by its lowest-indexed vertex); random/geometric/planar/k-partite/Mycielski graphs. |
| [`steiner`](generators/steiner) | 23 | Steiner Tree Problem — directed single-commodity flow formulation routing flow from a root to all terminals over a minimum-cost edge subset. |
| [`upms`](generators/upms) | 21 | Unrelated Parallel Machine Scheduling with Sequence-Dependent Setup Times — big-M disjunctive formulation, makespan or weighted-completion-time objective. |
| [`rcpsp`](generators/rcpsp) | 14 | Resource-Constrained Project Scheduling — two-phase time-indexed formulation (phase 1 finds an upper-bound makespan, phase 2 builds the time-indexed MIP over the optimal horizon). |
| [`tsp`](generators/tsp) | 26 | Traveling Salesman Problem — compact Miller-Tucker-Zemlin (MTZ) formulation; both symmetric Euclidean and asymmetric (directional-cost) instances. |
| [`fcnf`](generators/fcnf) | 24 | Fixed-Charge Network Flow — single-commodity flow with per-arc binary "open" decision and a fixed-charge + variable-cost objective; exercises flow cuts and VUB/MIR. |
| [`hop_nd`](generators/hop_nd) | 24 | Hop-Constrained Network Design — binary edge-install decisions supporting multi-commodity flow with a hop limit, enforced via a layered (time-expanded) graph; capacity is shared across commodities on each built edge. |
| [`sppc`](generators/sppc) | 20 | Generalized Set Partitioning/Packing/Covering — a single binary program mixing `=1`/`<=1`/`>=1` row types over one shared column set (crew-scheduling style); dense overlapping packing/covering rows force genuine branch-and-bound; specifically designed to exercise the conflict-graph structure over both original and complemented literals. Includes a permanent bug-repro fixture for a known MIPster preprocessing wrong-optimal issue. |
| [`cttp`](generators/cttp) | 18 | Class-Teacher Timetabling (Santos-style) — assign each class/teacher meeting's weekly lessons to day/timeslot "patterns" (1 lesson, or 2 consecutive lessons per day); binds teacher and class occupancy across all meetings, so it is not decomposable per pair. Objective minimizes (1) number of teacher-days-used ("day-off" preference) and (2) within-day idle gaps in a teacher's schedule; supports per-teacher-day/timeslot unavailability. Includes a genuinely infeasible fixture and two weight-variant fixtures (gap-focused vs. day-focused objective). |

## Imported instances (non-generated)

6 real-world MIPLIB 2017(+spp) instances imported directly from MIPster's
own C-interface regression test suite (`test/fixtures/` in the `mipster`
repo), rather than produced by a generator. No `generators/` subfolder
exists for these — they ship only as `.mps.gz` + `.sol` + `bks.tsv`/
`features.tsv`/`limits.tsv` rows like any other instance.

| Instance | Rows × Cols | Description | Status |
|---|---|---|---|
| `A-1` | 1015 × 18598 | Project-scheduling instance (MIPLIB 2017). | optimal (3200022), matches MIPster's own test suite |
| `attfInst1` | 1187 × 1163 | ATIF multi-commodity flow instance (MIPLIB 2017+spp). | optimal (202); MIPster validates the incumbent as feasible but doesn't close the gap within 150s itself — confirmed at 0% gap independently |
| `graphdraw-domain` | 865 × 254 | Graph-drawing / entity-placement instance (MIPLIB 2017). | optimal (19686); documented as "hard" in MIPster's own test, but closes to 0% gap in well under a minute with a different MILP solver |
| `leo1` | 593 × 6731 | Set packing/covering instance from the COR@L test set (MIPLIB 2017). | optimal (404227536.16), matches the MIPLIB-certified value exactly |
| `yue20013.1.150` | 3684 × 874 | Instance from the fonsecasantos collection (MIPLIB 2017+spp). | optimal (29), matches MIPster's own test suite |
| `j3041_1` | 344 × 801 | MIPLIB 2017+spp instance. | optimal (3), matches MIPster's own test suite |

For `attfInst1`, `graphdraw-domain`, and `leo1`, MIPster's own default
solve does not close the optimality gap within a short time budget (this
is expected and documented in MIPster's own tests) — the certified/
independently-verified optimal value was used to seed MIPster via
`-mipStart`, and MIPster validated the resulting solution as feasible
before writing the reference `.sol` file.

## MIPLIB3 instances (non-generated)

65 real-world instances from the classic 1996 MIPLIB benchmark set
(`miplib.cat`/`mps_format`/`references` metadata files excluded), compressed
to `.mps.gz` and validated the same way as every other instance in this
repo. As with the MIPLIB 2017(+spp) imports above, no `generators/`
subfolder exists for these.

61 of the 65 are proven optimal (bks status `optimal`); 4 remain open and
are recorded as `best_known`:

| Instance | Best known objective | Notes |
|---|---|---|
| `dano3mip` | 688.85 | ~16% gap remaining; notably better than the classic catalog value (728.11). See special limits note below. |
| `markshare2` | 14 | 100% reported gap — this instance is famous for an extremely weak/degenerate LP relaxation that provides essentially no useful lower bound; real integer-feasible solutions are found readily, satisfying the "interesting instance" bar. |
| `seymour` | 423 | ~0.7% gap remaining; matches the classic catalog's own "(not opt)" value exactly. |
| `swath` | 467.41 | ~8.6% gap remaining. |

**`dano3mip` special limits:** this instance's root-node cut generation and
postprocessing phases are not interruptible by MIPster's nominal time-limit
check, so a naive 120s/300s limit pair can significantly overrun (observed:
an internal budget of 60s overran to 163s in calibration, and an internal
budget of 240s overran to ~320s in later testing). To keep this instance
usable for quick tests while avoiding hard-kill truncation mid-phase, it is
given relaxed limits (`time_limit_sec=240`, `hard_kill_sec=480`) instead of
the file-wide default (`120`/`300`).

Reference solutions for all 65 instances were obtained directly from an
independent MILP solver's native `.sol` output (copied as-is into `sols/`)
and validated feasible with MIPster's own `mipster_validate_sol` tool —
this avoids a discovered MIPster preprocessing/mipStart interaction issue
that can silently corrupt a seeded incumbent when preprocessing is enabled
(tracked separately, out of scope for this dataset).

## CBC regression test set instances (non-generated)

35 real-world/public MIP benchmark instances (`a05100`, `a10100`, `a10200`,
`a20200`, `c05100`, `drayage-100-23`, `dt_optimization`, `eilB76`, `eilC76`,
`enlight_hard`, `exp-1-500-5-5`, `h80x6320`, `haprp`, `irp`, `markshare_4_0`,
`neos-1440225`, `neos17`, `neos-3226448-wkra`, `neos-777800`, `neos-827175`,
`neos-913984`, `p200x1188c`, `sp150x300d`, `T2_200_2000_0`, `T2_300_1000_0`,
`T2_300_5000_0`, `trd445c`, `trdta0010`, `trdta5581`, `wqueens-100`,
`wqueens-200`, `wqueens-300`, `wqueens-50`, `sprint08_j`, `etDecsi`), selected
from a broader CBC solver-regression run (MIPster v0.3.12, `stats.csv`) as
instances that finished (proved optimal, proved optimal within gap
tolerance, or proved infeasible) in <=100 seconds. As with the other
imported sets, no `generators/` subfolder exists for these.

`sprint08_j` (sports scheduling, 3522 rows x 10250 cols) and `etDecsi`
(university course timetabling, 17917 rows x 10606 cols) were added later
from the same `~/inst/super` extended/super set. Both were solved to
proven optimality directly with this repo's own CBC build (objective 56 in
13 nodes/57s, and objective 7 in 2120 nodes/125s respectively) and
independently cross-verified with Gurobi (`MIPGap=0`), which closed both to
a matching 0% gap in a single node. `bks.tsv` records both as `optimal`;
reference `.sol` files are CBC's own native solution output.

All CBC-reported "optimal" results were accepted as-is. The 6 instances CBC
reported as "optimal within gap tolerance" only (`drayage-100-23`,
`dt_optimization`, `haprp`, `neos-3226448-wkra`, `neos-827175`, `trd445c`)
and the one instance CBC reported infeasible (`trdta5581`) were re-solved
independently with a second MILP solver (`MIPGap=0`, 600s budget) to
confirm the result: all 6 gap-tolerance instances closed to a proven 0%
gap at the same objective value CBC found, and the infeasibility of
`trdta5581` was independently confirmed. `bks.tsv` records `optimal`/
`infeasible` status for these accordingly (not `best_known`), and notes
"re-solved independently to confirm result" in the `source` column for
this subset. Since CBC's own solution already matched the confirmed
optimum in all 6 gap-tolerance cases, CBC's native `.sol` output (copied
as-is into `sols/`) was kept as the reference solution rather than
resolving with a different solver; every reference `.sol` in this subset
was validated feasible with `mipster_validate_sol`. `trdta5581` (proven
infeasible) has a `bks.tsv` row but no `sols/` entry, consistent with the
other infeasible fixtures in this dataset.

## Solver coverage (full-run snapshot)

> Snapshot predates the `cttp` family; counts below are out of the 347
> instances that existed at the time of the run, not the current 365.

A full run of all 347 instances (7 parallel cores, 300s internal time limit,
360s hard kill) was performed to check how much of MIPster's cut/heuristic/
preprocessing machinery this dataset actually exercises. Results: 326 proven
optimal, 10 proven optimal within gap tolerance, 10 stopped on the time limit
(genuinely hard instances, useful for time/node-limited regression testing),
1 correctly proven infeasible (`cvrp_capacity_tight`, matches `bks.tsv`).

**Cut generators exercised** (instances active / 347, total cuts generated):
`gomory` (278, 379k), `twomircuts` (277, 110k), `probing` (254, 200k),
`mixedintegerrounding2` (217, 125k), `knapsack` (126, 7.6k), `zerohalf`
(107, 22k), `clique` (77, 47k), `flowcover` (52, 3.3k).

**Never exercised by any instance** (coverage gap): `gomory(2)`, `gomoryL1`,
`gomoryL2`, `oddwheel`, `reduce-and-split` (and `(2)` variant),
`liftandproject`, `residualcapacity`, `stored`, `twomircutsL1`,
`twomircutsL2` — likely disabled by default parameters rather than a dataset
gap, but worth investigating if a future family should target them
specifically.

**Heuristics exercised** (instances with >=1 solution found / 347, total
solutions): `feasibilityjump` (272, 309), `divecoefficient` (116, 161),
`rins` (114, 114), `rounding` (7, 7), `greedy_equality` (2, 2).

**Never exercised**: `combine_solutions`, `dantzig-wolfe-expansion`, all
`Dive*` variants except `DiveCoefficient`, `dynamic_pass_thru`,
`feasibility_pump` (distinct from `FeasibilityJump`), `greedy_cover`,
`linked`, `multiple_root_solvers`, `naive`, `partial_solution_given`,
`random_rounding`, `RENS`/`RENSdj`/`RENSub`, `VND`.

**Clique strengthening ("clique merge")** fired in 111/347 instances; best
test cases are in the `graph_coloring` family (e.g. `gc_random_n60_p0.6_sd1`:
4607 extended, 19203 dominated).

Per-cut/heuristic/technique top-5 test-instance tables are available in the
full report generated by the run (not checked into this repo, but
reproducible via `mipster -csvStatistics ... -solve -writeStatistics` across
`mips/*.mps.gz` — see `limits.tsv` below for suggested per-instance limits to
use for such runs).

## `limits.tsv`

Suggested per-instance node/time limits for fast regression testing,
derived from the full-coverage run above. Columns:

| Column | Meaning |
|---|---|
| `instance` | instance name (matches `mips/<instance>.mps.gz`) |
| `category` | `concluded_fast` (proved in <60s), `concluded_slow` (proved but took 60-300s), or `not_concluded` (hit the 300s time limit without proving optimality/infeasibility) |
| `node_limit` | suggested `Cbc_setMaximumNodes` value |
| `time_limit_sec` | suggested wall-clock time limit (`-sec`) |
| `hard_kill_sec` | suggested hard-kill timeout (e.g. via `timeout -k`) for a wrapper script, in case the solver hangs past its own limits |
| `observed_nodes` / `observed_elapsed_sec` / `observed_result` | raw data from the full-coverage run, for reference |

Derivation rules:
- **`concluded_fast`** (elapsed < 60s): `node_limit = 3x` observed nodes,
  `time_limit = 60s`, `hard_kill = time_limit + 120s`.
- **`concluded_slow`** (proved optimal/infeasible but took 60-300s):
  `node_limit = 3x` observed nodes, `time_limit` = observed elapsed rounded
  up to the next full minute, `hard_kill = time_limit + 120s`.
- **`not_concluded`** (hit the 300s limit without proving optimality):
  `node_limit` = observed nodes scaled down to the rate that would be
  reached in ~60s (`nodes * 60 / elapsed`), `time_limit = 120s`,
  `hard_kill = 180s`.

Scripts that need a quick, deterministic per-instance stopping point (e.g.
CI regression suites) should read `limits.tsv` and apply `node_limit` as the
primary stop (deterministic) with `time_limit_sec` as a loose wall-clock
fallback, per the node-limit-first testing convention used throughout this
dataset.

**`cttp` family limits** were calibrated directly (rather than scaled down
from a 300s run) since the family didn't exist during the original
full-coverage run: each instance was run with a 60s budget to measure how
many nodes it reaches in about a minute, always confirming at least one
integer-feasible solution was found by then. `node_limit` = observed nodes
at 60s for instances that don't conclude in that window, or `3x` observed
nodes for instances that already conclude within 60s (the infeasible
fixture uses a small fixed margin since it's proven infeasible at the root).
`time_limit_sec = 150` and `hard_kill_sec = 300` for all
18 `cttp` rows — more relaxed than the other families' limits since
CTTP's root-node cut generation can consume most of a 60s budget on
harder instances, leaving very few nodes for branch-and-bound.

## File structure

```
README.md        # description
features.tsv     # instance features tabulated
bks.tsv          # best known solution values (in most cases optimal) - infeasible cases should be labeled here also
limits.tsv       # suggested per-instance node/time/hard-kill limits for quick regression testing
├── mips/        # mps.gz files with instances
│   └── A-1.mps.gz
│   └── air03.mps.gz
│   └── ...
├── sols/        # reference solution
│   └── A-1.sol
│   └── air03.sol
│   └── ...
├── generators/  # scripts for generating instances for different applications
│   ├── jssp/          # job shop scheduling
│   ├── cvrp/          # capacitated vehicle routing
│   ├── bpc/           # bin packing with conflicts
│   ├── gap/           # generalized assignment problem
│   ├── mis/           # maximum independent set
│   ├── spp/           # set packing problem
│   ├── qap/           # quadratic assignment problem
│   ├── graph_coloring/ # graph coloring
│   ├── steiner/       # steiner tree problem
│   ├── upms/          # unrelated parallel machine scheduling
│   ├── rcpsp/         # resource-constrained project scheduling
│   ├── tsp/           # traveling salesman problem
│   ├── fcnf/          # fixed-charge network flow
│   ├── hop_nd/        # hop-constrained network design
│   ├── sppc/          # generalized set partitioning/packing/covering
│   └── cttp/          # class-teacher timetabling
```
