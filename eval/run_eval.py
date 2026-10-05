"""Reproducible evaluation: agentic loop vs. a static one-shot OpenCV pipeline.

    python -m eval.run_eval --n 200 --seed 11                # rule planner (offline)
    python -m eval.run_eval --n 40 --planner claude          # Claude on Bedrock (needs AWS creds)

Writes eval/results/<planner>-<seed>.json and prints a markdown table.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import time

from inspectagent import vision
from inspectagent.agent import ClaudePlanner, RulePlanner, _is_critical, run
from inspectagent.camera import SimCamera, make_dataset

EXPECTED = {"scratch": "reject", "faint_spot": "reject",
            "stain": "human_review", "missing_hole": "human_review"}


def expected(part) -> str:
    return EXPECTED[part.defects[0]["kind"]] if part.defects else "pass"


def static_baseline(part, cam: SimCamera) -> str:
    """One capture at default settings, one detection pass, no adaptation."""
    img = cam.capture(part)
    aligned, valid, info = vision.align_to_reference(img, cam.ref)
    if aligned is None:
        return "human_review"
    regions = vision.detect_defects(aligned, cam.ref, 1.0, valid)["regions"]
    if not regions:
        return "pass"
    return "human_review" if _is_critical(regions) else "reject"


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    defective = [r for r in rows if r["expected"] != "pass"]
    clean = [r for r in rows if r["expected"] == "pass"]
    out = {
        "parts": n,
        "accuracy_pass_vs_fail": sum((r["got"] == "pass") == (r["expected"] == "pass") for r in rows) / n,
        "false_accept_rate": sum(r["got"] == "pass" for r in defective) / max(1, len(defective)),
        "false_reject_rate": sum(r["got"] != "pass" for r in clean) / max(1, len(clean)),
        "policy_match": sum(r["got"] == r["expected"] for r in rows) / n,
        "escalation_rate": sum(r["got"] == "human_review" for r in rows) / n,
        "mean_latency_ms": statistics.mean(r["ms"] for r in rows),
    }
    if "steps" in rows[0]:
        out["mean_steps"] = statistics.mean(r["steps"] for r in rows)
        out["mean_captures"] = statistics.mean(r["captures"] for r in rows)
        out["closeups"] = sum(r["closeup"] for r in rows)
        out["guardrail_blocks"] = sum(r["guardrail_blocks"] for r in rows)
        out["planner_fallbacks"] = sum(r["fallbacks"] for r in rows)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--planner", choices=["rules", "claude"], default="rules")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "results"))
    a = ap.parse_args()
    cam = SimCamera()
    parts = make_dataset(a.n, a.seed)

    base, agent, failures = [], [], []
    for p in parts:
        nuisance = ("blur" if p.blur else "dark" if p.gain < 1 else "bright" if p.gain > 1
                    else "glare" if p.glare else "none")
        t = time.perf_counter()
        got = static_baseline(p, cam)
        base.append({"part": p.part_id, "expected": expected(p), "got": got, "nuisance": nuisance,
                     "ms": (time.perf_counter() - t) * 1000})

        planner = ClaudePlanner() if a.planner == "claude" else RulePlanner()
        t = time.perf_counter()
        s = run(p, cam, planner)
        row = {"part": p.part_id, "expected": expected(p), "got": s.outcome["decision"], "nuisance": nuisance,
               "ms": (time.perf_counter() - t) * 1000, "steps": len(s.trace), "captures": s.captures,
               "closeup": any(e.get("tool") == "inspect_closeup" for e in s.trace),
               "guardrail_blocks": sum("guardrail" in str(e.get("result", {}).get("error", "")) for e in s.trace),
               "fallbacks": sum(e.get("event") == "planner_error" for e in s.trace)}
        agent.append(row)
        if (row["got"] == "pass") != (row["expected"] == "pass"):
            failures.append({"part": p.part_id, "defects": p.defects, "trace": s.trace})

    res = {"config": vars(a), "baseline": summarise(base), "agent": summarise(agent),
           "by_nuisance": {}, "failures": failures[:10]}
    for nz in sorted({r["nuisance"] for r in agent}):
        b = [r for r in base if r["nuisance"] == nz]
        g = [r for r in agent if r["nuisance"] == nz]
        res["by_nuisance"][nz] = {"baseline_acc": summarise(b)["accuracy_pass_vs_fail"],
                                  "agent_acc": summarise(g)["accuracy_pass_vs_fail"], "n": len(g)}
    res["confusion_agent"] = {f"{k[0]}->{k[1]}": v for k, v in
                              collections.Counter((r["expected"], r["got"]) for r in agent).items()}
    os.makedirs(a.out, exist_ok=True)
    path = os.path.join(a.out, f"{a.planner}-seed{a.seed}-n{a.n}.json")
    with open(path, "w") as f:
        json.dump(res, f, indent=2, default=str)

    keys = list(res["baseline"].keys())
    print(f"| metric | static baseline | agent ({a.planner}) |\n|---|---|---|")
    for k in res["agent"]:
        bv = res["baseline"].get(k, "")
        fmt = (lambda v: f"{v:.3f}" if isinstance(v, float) else str(v))
        print(f"| {k} | {fmt(bv) if k in keys else '-'} | {fmt(res['agent'][k])} |")
    print("\n| capture nuisance | n | baseline acc | agent acc |\n|---|---|---|---|")
    for nz, v in res["by_nuisance"].items():
        print(f"| {nz} | {v['n']} | {v['baseline_acc']:.3f} | {v['agent_acc']:.3f} |")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
