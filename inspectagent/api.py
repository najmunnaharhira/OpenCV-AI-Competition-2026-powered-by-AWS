"""HTTP endpoint for judges: run inspections, view traces, approve escalations.

Local:   uvicorn inspectagent.api:app --reload
AWS:     Lambda (arm64 / Graviton) container behind a Function URL, via Mangum.
"""
from __future__ import annotations

import base64
import logging
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from mangum import Mangum
from pydantic import BaseModel

from . import store
from .agent import ClaudePlanner, RulePlanner, run
from .camera import SimCamera, make_dataset

logging.getLogger("inspectagent").setLevel(os.environ.get("LOG_LEVEL", "INFO"))
app = FastAPI(title="InspectAgent", version="0.1.0")
CAMERA = SimCamera()
PARTS = {p.part_id: p for p in make_dataset(40, seed=int(os.environ.get("DEMO_SEED", "11")))}
STATIC = os.path.join(os.path.dirname(__file__), "static", "index.html")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    with open(STATIC) as f:
        return f.read()


@app.get("/scenarios")
def scenarios() -> list[dict]:
    def nuisance(p):
        return ("blur" if p.blur else "dark" if p.gain < 1 else "bright" if p.gain > 1
                else "glare" if p.glare else "none")
    return [{"part_id": p.part_id, "nuisance": nuisance(p),
             "ground_truth": [d["kind"] for d in p.defects] or ["none"]} for p in PARTS.values()]


@app.post("/inspect/{part_id}")
def inspect(part_id: str, planner: str = "rules") -> dict:
    part = PARTS.get(part_id)
    if part is None:
        raise HTTPException(404, "unknown part")
    if planner == "claude":
        try:
            p = ClaudePlanner()
        except Exception as e:  # SDK missing / no credentials: run, but say so in the trace
            p = RulePlanner()
            planner = f"rules (claude unavailable: {type(e).__name__})"
    else:
        p = RulePlanner()
    s = run(part, CAMERA, p)
    store.save_session(s)
    return {"session_id": s.session_id, "planner": planner, "outcome": s.outcome, "trace": s.trace,
            "evidence": {k: base64.b64encode(v).decode() for k, v in s.artifacts.items()}}


class Decision(BaseModel):
    approved: bool
    reviewer: str = "judge"


@app.get("/approvals")
def approvals(status: str = "pending") -> list[dict]:
    return store.list_approvals(status)


@app.post("/approvals/{session_id}")
def decide(session_id: str, d: Decision) -> dict:
    try:
        return store.resolve_approval(session_id, d.approved, d.reviewer)
    except KeyError:
        raise HTTPException(404, "unknown session")


@app.get("/healthz")
def healthz() -> dict:
    import cv2
    return {"ok": True, "opencv": cv2.__version__, "arch": os.uname().machine}


handler = Mangum(app)
