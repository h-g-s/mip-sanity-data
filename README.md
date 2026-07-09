# mip-sanity-data

## Dataset with interesting mip instances (in .mps.gz) for quick tests with reference:
    - optimal/best known solution value (bks.tsv)
    - complete integer feasible solution(s) - from the best known solution at least
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

## File structure

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
│   └── jssp/    # example, generator for jssp instances
