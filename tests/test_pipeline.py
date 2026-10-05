import os

import numpy as np
import pytest

from inspectagent import vision
from inspectagent.agent import RulePlanner, execute, run, Session
from inspectagent.camera import Part, SimCamera, make_dataset

CAM = SimCamera()


def test_opencv_major_version_is_5():
    import cv2
    assert cv2.__version__.startswith("5.")


def test_quality_flags_blur_and_exposure():
    blurry = CAM.capture(Part("b", blur=3.5))
    dark = CAM.capture(Part("d", gain=0.3))
    assert "blurry" in vision.assess_quality(blurry)["issues"]
    assert "underexposed" in vision.assess_quality(dark)["issues"]
    assert vision.assess_quality(CAM.capture(Part("ok")))["ok"]


def test_alignment_recovers_pose():
    img = CAM.capture(Part("p", angle=5.0, shift=(12, -9)))
    warped, valid, info = vision.align_to_reference(img, CAM.ref)
    assert info["ok"] and abs(abs(info["rotation_deg"]) - 5.0) < 0.5


def test_clean_part_has_no_defects_and_scratch_is_found():
    for part, expect in [(Part("c", angle=3), 0),
                         (Part("s", angle=-2, defects=[{"kind": "scratch", "p0": (200, 300), "p1": (320, 310)}]), 1)]:
        w, m, _ = vision.align_to_reference(CAM.capture(part), CAM.ref)
        assert (vision.detect_defects(w, CAM.ref, 1.0, m)["count"] > 0) == bool(expect)


def test_agent_recaptures_blurry_image_and_the_trace_shows_why():
    s = run(Part("b", blur=3.5), CAM)
    tools = [t["tool"] for t in s.trace]
    assert tools[:2] == ["capture_image", "capture_image"]
    assert s.trace[1]["args"]["refocus"] is True and "Laplacian" in s.trace[1]["why"]
    assert s.outcome["decision"] == "pass"


def test_faint_defect_triggers_closeup_then_reject():
    s = run(Part("f", defects=[{"kind": "faint_spot", "x": 300, "y": 370}]), CAM)
    assert "inspect_closeup" in [t["tool"] for t in s.trace]
    assert s.outcome["decision"] == "reject"


def test_critical_defect_needs_human_and_guardrail_blocks_auto_reject():
    part = Part("m", defects=[{"kind": "missing_hole", "hole": 4}])
    s = run(part, CAM)
    assert s.outcome == {**s.outcome, "decision": "human_review", "proposed_action": "quarantine_lot"}
    s2 = Session(part=part, camera=CAM)
    for tool, args in [("capture_image", {"refocus": False, "exposure": 1.0, "polarizer": False}),
                       ("align_to_reference", {}), ("detect_defects", {"sensitivity": 1.0})]:
        execute(s2, tool, args)
    assert "guardrail" in execute(s2, "reject_part", {"rationale": "x"})["error"]


def test_pass_is_blocked_without_a_check():
    s = Session(part=Part("x"), camera=CAM)
    assert "guardrail" in execute(s, "pass_part", {"rationale": "looks fine"})["error"]


def test_planner_failure_falls_back_to_rules():
    class Broken:
        name = "broken"
        def next(self, s, last):
            raise RuntimeError("no credentials")
    s = run(Part("ok"), CAM, Broken())
    assert s.trace[0]["event"] == "planner_error" and s.outcome["decision"] == "pass"


def test_agent_beats_static_baseline_on_small_split():
    from eval.run_eval import static_baseline, expected
    parts = make_dataset(30, seed=5)
    agent = sum((run(p, CAM).outcome["decision"] == "pass") == (expected(p) == "pass") for p in parts)
    base = sum((static_baseline(p, CAM) == "pass") == (expected(p) == "pass") for p in parts)
    assert agent >= 28 and agent > base


def test_api_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_STORE", str(tmp_path))
    import importlib
    from inspectagent import store
    importlib.reload(store)
    from fastapi.testclient import TestClient
    from inspectagent import api
    importlib.reload(api)
    c = TestClient(api.app)
    assert c.get("/healthz").json()["opencv"].startswith("5.")
    crit = next(s["part_id"] for s in c.get("/scenarios").json() if "missing_hole" in s["ground_truth"])
    r = c.post(f"/inspect/{crit}").json()
    assert r["outcome"]["decision"] == "human_review"
    assert any(a["session_id"] == r["session_id"] for a in c.get("/approvals").json())
    assert c.post(f"/approvals/{r['session_id']}", json={"approved": True}).json()["status"] == "approved"


def test_claude_planner_message_flow_with_fake_client():
    """Exercises the Bedrock planner's tool_use/tool_result bookkeeping without AWS."""
    from types import SimpleNamespace as NS
    from inspectagent.agent import ClaudePlanner
    script = iter([
        [("capture_image", {"refocus": False, "exposure": 1.0, "polarizer": False})],
        [("capture_image", {"refocus": True, "exposure": 1.0, "polarizer": False})],
        [("align_to_reference", {}), ("detect_defects", {"sensitivity": 1.0})],   # parallel calls
        [("pass_part", {"rationale": "clean"})],
    ])
    seen = []

    class FakeMessages:
        def create(self, **kw):
            seen.append(kw["messages"][-1])
            calls = next(script)
            content = [NS(type="text", text="plan")] + [
                NS(type="tool_use", name=n, input=a, id=f"t{len(seen)}_{i}") for i, (n, a) in enumerate(calls)]
            return NS(stop_reason="tool_use", content=content)

    p = ClaudePlanner.__new__(ClaudePlanner)
    p.client, p.model, p.effort, p.pending = NS(messages=FakeMessages()), "fake", "medium", []
    p.messages = [{"role": "user", "content": "go"}]
    s = run(Part("b", blur=3.5), CAM, p)
    assert s.outcome["decision"] == "pass"
    third = seen[3]["content"]   # results of the two parallel calls arrive in one user message
    assert [b["tool_use_id"] for b in third] == ["t3_0", "t3_1"]
