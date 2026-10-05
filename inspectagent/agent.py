"""Perception -> decision -> action loop.

The executor owns state, guardrails and the trace. A *planner* chooses the next
tool call from the observations so far. Two planners share the same tools:

* RulePlanner   - deterministic policy; offline baseline and LLM fallback.
* ClaudePlanner - Claude on Amazon Bedrock (Messages API via the Mantle client)
                  choosing tools from OpenCV 5 observations.

Every OpenCV result is written to the trace together with the decision it led
to, which is the evidence the Agentic Vision award asks for.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field

import cv2
import numpy as np

from . import vision
from .camera import Part, SimCamera

log = logging.getLogger("inspectagent")

MAX_STEPS = 12
MAX_CAPTURES = 4
TERMINAL = {"pass_part", "reject_part", "request_human_approval"}
CRITICAL_AREA = 1500          # px^2 of defects => quarantine the lot (needs a human)
CRITICAL_KINDS = {"stain_or_missing_feature"}

TOOLS = [
    {"name": "capture_image",
     "description": "Capture a new image of the part with the given camera settings. "
                    "Returns an OpenCV quality report (sharpness, exposure, glare).",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"refocus": {"type": "boolean"},
                                     "exposure": {"type": "number", "description": "gain multiplier, 0.2-4.0"},
                                     "polarizer": {"type": "boolean"}},
                      "required": ["refocus", "exposure", "polarizer"]}},
    {"name": "align_to_reference",
     "description": "Register the latest image to the golden reference (ORB + RANSAC + ECC).",
     "input_schema": {"type": "object", "additionalProperties": False, "properties": {}, "required": []}},
    {"name": "detect_defects",
     "description": "Golden-reference defect detection on the aligned image. sensitivity 1.0 is "
                    "the production setting; 2.0 halves the threshold for a closer look.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"sensitivity": {"type": "number"}}, "required": ["sensitivity"]}},
    {"name": "inspect_closeup",
     "description": "Zoom into a region (or the strongest residual if no bbox) and re-run detection "
                    "at high sensitivity. Returns the result and a close-up image.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"bbox": {"type": "array", "items": {"type": "integer"},
                                              "description": "[x, y, w, h]; empty for strongest residual"}},
                      "required": ["bbox"]}},
    {"name": "pass_part", "description": "Accept the part. Only allowed after a defect check on a good-quality image.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
    {"name": "reject_part", "description": "Reject the part to the scrap bin (minor, isolated defects).",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"rationale": {"type": "string"}}, "required": ["rationale"]}},
    {"name": "request_human_approval",
     "description": "Escalate to a human: required for critical defects (lot quarantine) or when a "
                    "usable image cannot be obtained.",
     "input_schema": {"type": "object", "additionalProperties": False,
                      "properties": {"proposed_action": {"type": "string",
                                                         "enum": ["quarantine_lot", "manual_inspection"]},
                                     "rationale": {"type": "string"}},
                      "required": ["proposed_action", "rationale"]}},
]


@dataclass
class Session:
    part: Part
    camera: SimCamera
    session_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    settings: dict = field(default_factory=lambda: dict(SimCamera.DEFAULT))
    image: np.ndarray | None = None
    aligned: np.ndarray | None = None
    valid: np.ndarray | None = None
    quality: dict | None = None
    detection: dict | None = None
    closeup: dict | None = None
    captures: int = 0
    checked_on_good_image: bool = False
    trace: list = field(default_factory=list)
    outcome: dict | None = None
    artifacts: dict = field(default_factory=dict)   # name -> jpeg bytes


# ---------------------------------------------------------------- executor

def execute(s: Session, tool: str, args: dict) -> dict:
    """Run one tool with guardrails. Returns a JSON-serialisable observation."""
    ref = s.camera.ref
    if tool == "capture_image":
        if s.captures >= MAX_CAPTURES:
            return {"error": f"capture budget exhausted ({MAX_CAPTURES}); escalate to a human"}
        s.settings = {"refocus": bool(args.get("refocus")),
                      "exposure": float(np.clip(args.get("exposure", 1.0), 0.2, 4.0)),
                      "polarizer": bool(args.get("polarizer"))}
        s.image = s.camera.capture(s.part, s.settings)
        s.captures += 1
        s.aligned = s.detection = s.closeup = None
        s.quality = vision.assess_quality(s.image)
        s.artifacts[f"capture_{s.captures}.jpg"] = _jpeg(s.image)
        return {"settings": s.settings, "quality": s.quality, "captures_left": MAX_CAPTURES - s.captures}
    if tool == "align_to_reference":
        if s.image is None:
            return {"error": "no image captured yet"}
        s.aligned, s.valid, info = vision.align_to_reference(s.image, ref)
        return info
    if tool == "detect_defects":
        if s.aligned is None:
            return {"error": "align_to_reference must succeed first"}
        sens = float(np.clip(args.get("sensitivity", 1.0), 0.5, 3.0))
        s.detection = vision.detect_defects(s.aligned, ref, sens, s.valid)
        if s.quality and s.quality["ok"]:
            s.checked_on_good_image = True
        s.artifacts["annotated.jpg"] = _jpeg(vision.annotate(s.aligned, s.detection["regions"]))
        out = dict(s.detection)
        out["regions"] = out["regions"][:5]
        return out
    if tool == "inspect_closeup":
        if s.aligned is None:
            return {"error": "align_to_reference must succeed first"}
        bbox = list(args.get("bbox") or [])
        if len(bbox) != 4:
            bbox = _peak_bbox(s.aligned, ref, s.valid)
        x, y, w, h = bbox
        pad = 24
        roi = [x - pad, y - pad, w + 2 * pad, h + 2 * pad]
        det = vision.detect_defects(s.aligned, ref, 2.0, s.valid, roi=roi)
        s.closeup = {"bbox": bbox, **det}
        s.artifacts["closeup.jpg"] = _jpeg(vision.zoom_region(vision.annotate(s.aligned, det["regions"]), bbox))
        return s.closeup
    if tool == "pass_part":
        if not s.checked_on_good_image:
            return {"error": "guardrail: cannot pass a part without a defect check on a good-quality image"}
        if s.detection and s.detection["count"] or s.closeup and s.closeup["count"]:
            return {"error": "guardrail: defects were detected; reject or escalate"}
        s.outcome = {"decision": "pass", **args}
        return {"ok": True}
    if tool == "reject_part":
        found = (s.detection or {}).get("regions", []) + (s.closeup or {}).get("regions", [])
        if not found:
            return {"error": "guardrail: no defect evidence to justify rejection"}
        if _is_critical(found):
            return {"error": "guardrail: critical defect; request_human_approval(quarantine_lot) is required"}
        s.outcome = {"decision": "reject", **args}
        return {"ok": True}
    if tool == "request_human_approval":
        s.outcome = {"decision": "human_review", "status": "pending", **args}
        return {"ok": True, "status": "pending"}
    return {"error": f"unknown tool {tool}"}


def _is_critical(regions: list[dict]) -> bool:
    return (sum(r["area"] for r in regions) > CRITICAL_AREA
            or any(r["kind"] in CRITICAL_KINDS for r in regions))


def _peak_bbox(img, ref, valid) -> list[int]:
    _, _, _, (x, y) = cv2.minMaxLoc(vision.residual(img, ref, valid))
    return [max(0, x - 24), max(0, y - 24), 48, 48]


def _jpeg(img: np.ndarray) -> bytes:
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()


# ---------------------------------------------------------------- planners

class RulePlanner:
    """Deterministic policy. Each decision cites the OpenCV evidence behind it."""
    name = "rules"

    def next(self, s: Session, last: dict | None) -> tuple[str, dict, str]:
        if s.image is None:
            return "capture_image", dict(SimCamera.DEFAULT), "start with default camera settings"
        if last and "error" in last and "capture budget" in last["error"]:
            return ("request_human_approval", {"proposed_action": "manual_inspection",
                    "rationale": "could not obtain a usable image"}, last["error"])
        q = s.quality
        if not q["ok"] and s.aligned is None:
            if s.captures >= MAX_CAPTURES:
                return ("request_human_approval", {"proposed_action": "manual_inspection",
                        "rationale": f"image still {q['issues']} after {s.captures} captures"},
                        "capture budget exhausted")
            st = dict(s.settings)
            # Exposure first (it also depresses the sharpness score), then glare, then focus.
            order = ["underexposed", "overexposed", "glare", "blurry"]
            issue = min(q["issues"], key=order.index)
            if (issue == "glare" and st["polarizer"]) or (issue == "blurry" and st["refocus"]):
                return ("request_human_approval", {"proposed_action": "manual_inspection",
                        "rationale": f"{issue} persists after its remedy was applied"},
                        "remedy did not help -> escalate instead of looping")
            if issue in ("underexposed", "overexposed"):
                st["exposure"] = round(st["exposure"] * 128.0 / max(q["mean_intensity"], 1.0), 3)
                why = f"{issue}: mean intensity {q['mean_intensity']} -> scale exposure"
            elif issue == "glare":
                st["polarizer"] = True
                why = f"glare: {q['glare_fraction']:.1%} saturated pixels -> enable polarizer"
            else:
                st["refocus"] = True
                why = f"blurry: Laplacian variance {q['sharpness']} < {vision.BLUR_MIN} -> refocus"
            return "capture_image", st, why
        if s.aligned is None:
            if last and last.get("ok") is False:
                return ("request_human_approval", {"proposed_action": "manual_inspection",
                        "rationale": f"alignment failed: {last.get('reason')}"}, "cannot register part")
            return "align_to_reference", {}, "image quality ok -> register to reference"
        if s.detection is None:
            return "detect_defects", {"sensitivity": 1.0}, "aligned -> production defect check"
        d = s.detection
        if d["count"] == 0 and s.closeup is None:
            if d["peak_residual"] >= 0.5 * d["threshold"]:
                return ("inspect_closeup", {"bbox": []},
                        f"no defect but peak residual {d['peak_residual']} >= half threshold "
                        f"{d['threshold']} -> take a closer look")
            return "pass_part", {"rationale": f"no defects; peak residual {d['peak_residual']}"}, "clean"
        found = d["regions"] + (s.closeup or {}).get("regions", [])
        if not found:
            return "pass_part", {"rationale": "close-up found nothing"}, "close-up clean"
        kinds = sorted({r["kind"] for r in found})
        area = sum(r["area"] for r in found)
        if _is_critical(found):
            return ("request_human_approval", {"proposed_action": "quarantine_lot",
                    "rationale": f"critical defect {kinds}, area {area}px"},
                    "critical -> line action needs human approval")
        return "reject_part", {"rationale": f"defects {kinds}, area {area}px"}, "minor defect -> auto reject"


SYSTEM_PROMPT = """You are the controller of an automated visual inspection cell for machined plates.
You can only act through the tools. Every decision must be grounded in the OpenCV measurements the tools return.
Procedure: capture an image; if the quality report lists issues, fix ONE issue per recapture
(underexposed/overexposed -> scale exposure toward mean intensity 128; glare -> polarizer; blurry -> refocus).
When quality is ok, align, then detect defects at sensitivity 1.0. If nothing is found but peak_residual is at least
half of the threshold, call inspect_closeup before deciding. Then end with exactly one of pass_part, reject_part or
request_human_approval. Critical defects (missing features, stains, or large total area) require
request_human_approval with quarantine_lot. If a tool returns an error, adapt your plan; do not repeat the same call."""


class ClaudePlanner:
    """Claude on Amazon Bedrock picks the next tool from OpenCV observations."""
    name = "claude-bedrock"

    def __init__(self, model: str | None = None, region: str | None = None, effort: str | None = None):
        from anthropic import AnthropicBedrockMantle  # imported lazily; optional dependency
        self.client = AnthropicBedrockMantle(aws_region=region or os.environ.get("AWS_REGION", "us-east-1"))
        self.model = model or os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-opus-5-5")
        self.effort = effort or os.environ.get("PLANNER_EFFORT", "medium")
        self.messages: list = [{"role": "user", "content":
                                "A new part is at the inspection station. Inspect it and decide."}]
        self.pending: list = []   # tool calls from the last response not yet executed

    def next(self, s: Session, last: dict | None) -> tuple[str, dict, str]:
        if self.pending:
            return self.pending.pop(0)
        resp = self.client.messages.create(
            model=self.model, max_tokens=16000, system=SYSTEM_PROMPT, tools=TOOLS,
            tool_choice={"type": "auto"}, output_config={"effort": self.effort},
            messages=self.messages)
        if resp.stop_reason == "refusal":
            raise RuntimeError("planner refused")
        # Append the full content (incl. thinking blocks) so history stays append-only.
        self.messages.append({"role": "assistant", "content": resp.content})
        text = " ".join(b.text for b in resp.content if b.type == "text").strip()
        calls = [(b.name, dict(b.input), text or "(no rationale)", b.id)
                 for b in resp.content if b.type == "tool_use"]
        if not calls:
            raise RuntimeError(f"planner stopped without a tool call: {text[:200]}")
        self._ids = [c[3] for c in calls]
        self._results: list = []
        self.pending = [c[:3] for c in calls[1:]]
        return calls[0][:3]

    def observe(self, s: Session, result: dict) -> None:
        block = {"type": "tool_result", "tool_use_id": self._ids[len(self._results)],
                 "content": [{"type": "text", "text": json.dumps(result)}],
                 "is_error": "error" in result}
        if "closeup.jpg" in s.artifacts and result is s.closeup:
            block["content"].append({"type": "image", "source": {
                "type": "base64", "media_type": "image/jpeg",
                "data": base64.b64encode(s.artifacts["closeup.jpg"]).decode()}})
        self._results.append(block)
        if len(self._results) == len(self._ids):   # all results in one user message
            self.messages.append({"role": "user", "content": self._results})


# ---------------------------------------------------------------- loop

def run(part: Part, camera: SimCamera | None = None, planner=None) -> Session:
    s = Session(part=part, camera=camera or SimCamera())
    planner = planner or RulePlanner()
    fallback = None
    last = None
    for step in range(1, MAX_STEPS + 1):
        active = fallback or planner
        t0 = time.perf_counter()
        try:
            tool, args, why = active.next(s, last)
        except Exception as e:  # LLM unavailable / refused -> deterministic fallback
            fallback = RulePlanner()
            s.trace.append({"step": step, "planner": active.name, "event": "planner_error",
                            "error": str(e)[:300], "fallback": "rules"})
            tool, args, why = fallback.next(s, last)
            active = fallback
        plan_ms = (time.perf_counter() - t0) * 1000
        t1 = time.perf_counter()
        result = execute(s, tool, args)
        if hasattr(active, "observe"):
            active.observe(s, result)
        s.trace.append({"step": step, "planner": active.name, "tool": tool, "args": args,
                        "why": why, "result": _summarise(result),
                        "plan_ms": round(plan_ms, 1), "tool_ms": round((time.perf_counter() - t1) * 1000, 1)})
        # One JSON line per step: CloudWatch Logs Insights can filter by session, tool or planner.
        log.info(json.dumps({"session_id": s.session_id, "part_id": part.part_id, **s.trace[-1]}, default=str))
        last = result
        if s.outcome:
            break
    if not s.outcome:
        s.outcome = {"decision": "human_review", "status": "pending", "proposed_action": "manual_inspection",
                     "rationale": f"step budget ({MAX_STEPS}) exhausted"}
    log.info(json.dumps({"session_id": s.session_id, "part_id": part.part_id, "outcome": s.outcome,
                         "steps": len(s.trace), "captures": s.captures}, default=str))
    return s


def _summarise(r: dict) -> dict:
    r = dict(r)
    if "regions" in r:
        r["regions"] = r["regions"][:3]
    return r
