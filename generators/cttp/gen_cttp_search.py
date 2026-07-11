"""Parameter-grid search for CTTP instances that force genuine
branch-and-bound (not solved trivially at the root node), analogous to the
searches used for the SPPC and graph_coloring families. Runs mipster with a
short time limit across many parameter combinations + seeds and reports
configs where the search took a nontrivial number of nodes/time.

Usage: python3 gen_cttp_search.py
"""

import sys
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))
import cttp_lib as lib

TIME_LIMIT = 30
MIN_WALL = 3
MAX_WALL = 27
MIN_NODES = 5


def try_config(nc, nt, nd, ns, subj_range, req_range, day_w, gap_w,
                p_slot, p_dayoff, seed):
    name = f"cttp_c{nc}_t{nt}_d{nd}_s{ns}_sd{seed}"
    mps_text, info, instance = lib.build_instance(
        name, num_classes=nc, num_teachers=nt, num_days=nd, slots_per_day=ns,
        subjects_per_class_range=subj_range, req_range=req_range, seed=seed,
        day_weight=day_w, gap_weight=gap_w,
        p_random_slot=p_slot, p_day_off=p_dayoff)
    with tempfile.NamedTemporaryFile(suffix=".mps.gz", delete=False) as f:
        path = f.name
    lib.write_mps_gz(mps_text, path)
    try:
        res = lib.solve_with_mipster(path, TIME_LIMIT)
    finally:
        Path(path).unlink(missing_ok=True)
    return dict(name=name, nc=nc, nt=nt, nd=nd, ns=ns, subj_range=subj_range,
                req_range=req_range, day_w=day_w, gap_w=gap_w, p_slot=p_slot,
                p_dayoff=p_dayoff, seed=seed, **res, num_meetings=info["num_meetings"],
                total_req=info["total_req"])


def main():
    configs = []
    for nc, nt, nd, ns in [
        (5, 6, 5, 6), (6, 8, 5, 6), (8, 10, 5, 6), (10, 12, 5, 6),
    ]:
        for subj_range in [(4, 6), (5, 8)]:
            for req_range in [(2, 4), (2, 6)]:
                for p_slot, p_dayoff in [(0.05, 0.1)]:
                    for seed in range(1, 4):
                        configs.append((nc, nt, nd, ns, subj_range, req_range,
                                         10.0, 1.0, p_slot, p_dayoff, seed))

    print(f"Total configs: {len(configs)}", flush=True)
    interesting = []
    all_results = []
    done = 0
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = [ex.submit(try_config, *cfg) for cfg in configs]
        for fut in as_completed(futs):
            r = fut.result()
            all_results.append(r)
            done += 1
            status = "OPT" if r["optimal"] else ("INF" if r["infeasible"] else "TIMEOUT")
            print(f"[{done}/{len(configs)}] {r['name']} {status} nodes={r['nodes']} "
                  f"wall={r['wall']}s obj={r['obj']}", flush=True)
            if (r["optimal"] and r["nodes"] is not None and r["nodes"] >= MIN_NODES
                    and MIN_WALL <= r["wall"] <= MAX_WALL):
                interesting.append(r)

    print(f"\nFound {len(interesting)} interesting configs out of {len(configs)}", flush=True)
    interesting.sort(key=lambda r: r["wall"])
    for r in interesting:
        print(r["name"], "nodes=", r["nodes"], "wall=", r["wall"], "obj=", r["obj"],
              "nc=", r["nc"], "nt=", r["nt"], "nd=", r["nd"], "ns=", r["ns"],
              "subj=", r["subj_range"], "req=", r["req_range"], "seed=", r["seed"], flush=True)


if __name__ == "__main__":
    main()
