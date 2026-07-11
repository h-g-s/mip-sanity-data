# mip-sanity-data

## Overview

**16 problem families, 365 instances.** Each instance ships as a `.mps.gz` file
with a certified best-known (in most cases optimal) objective value in
`bks.tsv` and at least one reference integer-feasible solution in `sols/`.
Every family has a generator under `generators/<family>/` so the dataset can
be regenerated, extended, or ported to another solver's test suite.

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
