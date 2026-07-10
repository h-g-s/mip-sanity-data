# mip-sanity-data

## Overview

**15 problem families, 347 instances.** Each instance ships as a `.mps.gz` file
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

## File structure

```
README.md        # description
features.tsv     # instance features tabulated
bks.tsv          # best known solution values (in most cases optimal) - infeasible cases should be labeled here also
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
│   └── sppc/          # generalized set partitioning/packing/covering
```
