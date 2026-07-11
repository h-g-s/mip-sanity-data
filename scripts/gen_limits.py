#!/usr/bin/env python3
"""Generate limits.tsv: suggested per-instance node/time limits for quick
regression testing, derived from the full-coverage experiment run
(~/experiments/cbc/full_coverage_2026_07_10/stats.csv).

Three categories, based on the 5-minute (300s), 7-core, 347-instance run:

  1. concluded_fast   -- result != "Stopped on time limit" AND elapsed < 60s.
     node_limit  = 3 * nodes_observed
     time_limit  = 60s
     hard_kill   = time_limit + 120s = 180s

  2. concluded_slow   -- result != "Stopped on time limit" AND elapsed >= 60s
     (i.e. genuinely proved optimal/infeasible but took 1-5 minutes).
     node_limit  = 3 * nodes_observed
     time_limit  = ceil(elapsed_observed to next full minute)
     hard_kill   = time_limit + 120s

  3. not_concluded    -- result == "Stopped on time limit" (search did not
     finish in the 300s budget).
     node_limit  = round(nodes_observed * (60 / elapsed_observed))
                   (scales the achieved node rate down to a ~1-minute budget)
     time_limit  = 120s
     hard_kill   = 180s

Writes limits.tsv to the mip-sanity-data repo root.
"""
import csv
import math
from pathlib import Path

STATS_CSV = Path.home() / "experiments" / "cbc" / "full_coverage_2026_07_10" / "stats.csv"
OUT_TSV = Path.home() / "dev" / "mip-sanity-data" / "limits.tsv"


def main():
    rows = list(csv.DictReader(open(STATS_CSV)))
    out_rows = []
    for r in rows:
        name = r["Name"]
        result = r["result"]
        nodes = int(float(r["nodes"]))
        elapsed = float(r["elapsed"])
        not_concluded = (result == "Stopped on time limit")

        if not_concluded:
            category = "not_concluded"
            rate = nodes / elapsed if elapsed > 0 else 0
            node_limit = max(1, round(rate * 60))
            time_limit = 120
            hard_kill = 180
        elif elapsed < 60:
            category = "concluded_fast"
            node_limit = 3 * nodes
            time_limit = 60
            hard_kill = 180
        else:
            category = "concluded_slow"
            node_limit = 3 * nodes
            time_limit = int(math.ceil(elapsed / 60.0) * 60)
            hard_kill = time_limit + 120

        out_rows.append(dict(
            instance=name,
            category=category,
            node_limit=node_limit,
            time_limit_sec=time_limit,
            hard_kill_sec=hard_kill,
            observed_nodes=nodes,
            observed_elapsed_sec=f"{elapsed:.2f}",
            observed_result=result,
        ))

    out_rows.sort(key=lambda r: r["instance"])

    fieldnames = ["instance", "category", "node_limit", "time_limit_sec", "hard_kill_sec",
                  "observed_nodes", "observed_elapsed_sec", "observed_result"]
    with open(OUT_TSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    print(f"Wrote {OUT_TSV} ({len(out_rows)} rows)")
    from collections import Counter
    print(Counter(r["category"] for r in out_rows))


if __name__ == "__main__":
    main()
