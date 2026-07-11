"""Broad candidate search for the CTTP diverse fixture set: generates many
instances across a range of scales/parameters, solves each with a moderate
time budget, and records results to a JSON file for later curated
selection (see gen_cttp_diverse.py). Filters out infeasible/degenerate
candidates automatically -- this dataset's convention is to discard
infeasible-by-accident instances rather than engineer a perfect generator
(the same pragmatic approach used for SPPC/graph_coloring).
"""

import json
import sys
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
import cttp_lib as lib

TIME_LIMIT = 90


def try_config(cfg):
    nc, nt, nd, ns, subj_range, req_range, day_w, gap_w, p_slot, p_dayoff, util, seed = cfg
    name = f"cttp_c{nc}_t{nt}_d{nd}_s{ns}_r{req_range[0]}-{req_range[1]}_sd{seed}"
    mps_text, info, instance = lib.build_instance(
        name, num_classes=nc, num_teachers=nt, num_days=nd, slots_per_day=ns,
        subjects_per_class_range=subj_range, req_range=req_range, seed=seed,
        day_weight=day_w, gap_weight=gap_w,
        p_random_slot=p_slot, p_day_off=p_dayoff,
        max_class_utilization=util, max_teacher_utilization=util)
    with tempfile.NamedTemporaryFile(suffix=".mps.gz", delete=False) as f:
        path = f.name
    lib.write_mps_gz(mps_text, path)
    try:
        res = lib.solve_with_mipster(path, TIME_LIMIT)
    finally:
        Path(path).unlink(missing_ok=True)
    return dict(name=name, nc=nc, nt=nt, nd=nd, ns=ns, subj_range=list(subj_range),
                req_range=list(req_range), day_w=day_w, gap_w=gap_w, p_slot=p_slot,
                p_dayoff=p_dayoff, util=util, seed=seed,
                obj=res["obj"], optimal=res["optimal"], infeasible=res["infeasible"],
                nodes=res["nodes"], wall=res["wall"], lower_bound=res["lower_bound"],
                num_meetings=info["num_meetings"], total_req=info["total_req"])


def main():
    configs = []
    scales = [
        (4, 5, 5, 6), (5, 6, 5, 6), (6, 7, 5, 6), (6, 8, 5, 6),
        (7, 9, 5, 6), (8, 10, 5, 6), (9, 11, 5, 6), (10, 12, 5, 6),
        (6, 6, 5, 5), (8, 8, 5, 7),
    ]
    for nc, nt, nd, ns in scales:
        for req_range in [(2, 3), (2, 4)]:
            for util in [0.75, 0.85]:
                for seed in range(1, 4):
                    configs.append((nc, nt, nd, ns, (4, 6), req_range,
                                     10.0, 1.0, 0.05, 0.1, util, seed))

    print(f"Total configs: {len(configs)}", flush=True)
    results = []
    done = 0
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = [ex.submit(try_config, cfg) for cfg in configs]
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            done += 1
            status = "OPT" if r["optimal"] else ("INF" if r["infeasible"] else "TIMEOUT")
            print(f"[{done}/{len(configs)}] {r['name']} util={r['util']} {status} "
                  f"nodes={r['nodes']} wall={r['wall']}s obj={r['obj']}", flush=True)

    out_path = Path(__file__).parent / "search_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=1)
    print(f"\nWrote {len(results)} results to {out_path}", flush=True)

    feasible_solved = [r for r in results if r["optimal"]]
    print(f"Feasible+optimal: {len(feasible_solved)}/{len(results)}", flush=True)


if __name__ == "__main__":
    main()
