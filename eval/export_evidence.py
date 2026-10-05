"""Export judge evidence: annotated agent traces, evidence images and a guardrail demo.

    python -m eval.export_evidence        # writes docs/evidence/
"""
from __future__ import annotations

import json
import os

from inspectagent.agent import RulePlanner, run
from inspectagent.camera import Part, SimCamera, make_dataset

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "evidence")
CAM = SimCamera()


def key_metric(t: dict) -> str:
    r = t.get("result", {})
    if "error" in r:
        return f"ERROR: {r['error']}"
    if "quality" in r:
        q = r["quality"]
        return (f"sharpness={q['sharpness']} mean={q['mean_intensity']} glare={q['glare_fraction']} "
                f"issues={q['issues'] or 'none'}")
    if "inliers" in r:
        return f"inliers={r['inliers']} ecc={r.get('ecc')} rotation={r.get('rotation_deg')} deg"
    if "regions" in r:
        kinds = [x["kind"] for x in r["regions"]]
        return f"threshold={r['threshold']} peak_residual={r['peak_residual']} regions={r['count']} {kinds}"
    return json.dumps(r)


def write_case(name: str, title: str, s, note: str) -> None:
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    for k, v in s.artifacts.items():
        with open(os.path.join(d, k), "wb") as f:
            f.write(v)
    with open(os.path.join(d, "trace.json"), "w") as f:
        json.dump({"part_id": s.part.part_id, "ground_truth": s.part.defects, "outcome": s.outcome,
                   "trace": s.trace}, f, indent=2, default=str)
    rows = ["| step | tool | arguments | OpenCV 5 output | why this step |", "|---|---|---|---|---|"]
    for t in s.trace:
        if "tool" not in t:
            rows.append(f"| {t['step']} | *{t['event']}* | | {t.get('error', '')} | fallback: {t.get('fallback')} |")
            continue
        rows.append(f"| {t['step']} | `{t['tool']}` | `{json.dumps(t['args'])}` | {key_metric(t)} | {t['why']} |")
    imgs = " ".join(f"![{k}]({k})" for k in sorted(s.artifacts))
    with open(os.path.join(d, "README.md"), "w") as f:
        f.write(f"# {title}\n\n{note}\n\nGround truth: `{s.part.defects or 'no defect'}`  \n"
                f"Outcome: **{s.outcome['decision']}** {s.outcome.get('proposed_action', '')} "
                f"({s.outcome.get('rationale', '')})\n\n" + "\n".join(rows) + f"\n\n{imgs}\n")


class OverconfidentPlanner(RulePlanner):
    """Simulates a planner (e.g. an LLM) that tries to auto-reject a critical defect."""
    name = "overconfident"

    def next(self, s, last):
        tool, args, why = super().next(s, last)
        if tool == "request_human_approval" and args["proposed_action"] == "quarantine_lot" and not getattr(self, "tried", False):
            self.tried = True
            return "reject_part", {"rationale": "just scrap it"}, "planner skips the human"
        return tool, args, why


def main() -> None:
    cases = [
        ("01-blur-recapture", "Blurry capture: OpenCV sharpness drives a refocus",
         run(Part("DEMO-BLUR", blur=3.5, angle=3.0, shift=(8, -5)), CAM),
         "The first image fails the Laplacian sharpness gate, so the agent recaptures with refocus before inspecting."),
        ("02-glare-and-faint-defect", "Glare plus a faint defect: polarizer, then a close-up",
         run(Part("DEMO-FAINT", glare=True, angle=-2.0, seed=321,
                  defects=[{"kind": "faint_spot", "x": 300, "y": 370}]), CAM),
         "Saturated pixels trigger the polarizer. The defect is below the production threshold, but the residual peak "
         "is close to it, so the agent takes a close-up at higher sensitivity and finds it."),
        ("03-critical-needs-human", "Missing hole: critical defect goes to a human",
         run(Part("DEMO-CRIT", gain=0.3, angle=4.0, defects=[{"kind": "missing_hole", "hole": 1}]), CAM),
         "Exposure is fixed first. The missing feature is critical, so the agent asks a human to approve a lot quarantine."),
        ("04-guardrail-blocks-planner", "Guardrail: a planner tries to skip the human",
         run(Part("DEMO-GUARD", defects=[{"kind": "missing_hole", "hole": 4}]), CAM, OverconfidentPlanner()),
         "The planner tries to auto-reject a critical defect. The executor refuses, and the planner must escalate."),
        ("05-planner-failure-fallback", "Failure handling: the LLM planner is unavailable",
         run(Part("DEMO-FALLBACK", blur=3.5), CAM, type("Down", (), {"name": "claude-bedrock",
             "next": lambda self, s, l: (_ for _ in ()).throw(RuntimeError("Bedrock unreachable"))})()),
         "The Claude planner raises an error, the loop logs it and continues with the rule planner."),
    ]
    fails = {p.part_id: p for p in make_dataset(200, 11)}
    cases.append(("06-failure-case", "Known failure: faint spot missed",
                  run(fails["P199"], CAM),
                  "From the seed-11 evaluation. The defect stays below even the close-up threshold, so the part passes. "
                  "This is one of the 2 false accepts out of 100 defective parts."))
    for name, title, s, note in cases:
        write_case(name, title, s, note)
        print(name, s.outcome["decision"], len(s.trace), "steps")


if __name__ == "__main__":
    main()
