"""Synthetic inspection cell: a reproducible part generator plus a controllable camera.

It stands in for a real line camera so the whole loop (and the evaluation) runs
anywhere with no dataset download. Each part has ground-truth defects and
capture nuisances (blur, bad exposure, glare, pose). The camera takes settings
(refocus, exposure, polariser) so the agent can actively fix a bad capture.
Swap `SimCamera` for a real camera / S3 image source with the same interface.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

SIZE = (480, 640)  # H, W
HOLES = [(120, 140), (120, 500), (360, 140), (360, 500), (240, 320)]


def reference_part() -> np.ndarray:
    """Golden image of a defect-free machined plate."""
    H, W = SIZE
    img = np.full((H, W, 3), 40, np.uint8)
    cv2.rectangle(img, (40, 40), (W - 40, H - 40), (170, 170, 175), -1)
    cv2.rectangle(img, (40, 40), (W - 40, H - 40), (90, 90, 95), 3)
    for (y, x) in HOLES:
        cv2.circle(img, (x, y), 28, (60, 60, 65), -1)
        cv2.circle(img, (x, y), 34, (120, 120, 125), 2)
    cv2.putText(img, "LOT A7-2026", (220, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (50, 50, 55), 2)
    cv2.putText(img, "OPENCV5", (250, 300), cv2.FONT_HERSHEY_DUPLEX, 0.8, (70, 70, 75), 2)
    for i in range(6):  # fiducial ticks give ORB stable corners
        cv2.rectangle(img, (70 + i * 90, 420), (90 + i * 90, 430), (80, 80, 85), -1)
    return img


@dataclass
class Part:
    part_id: str
    defects: list[dict] = field(default_factory=list)   # ground truth
    blur: float = 0.0          # gaussian sigma when not refocused
    gain: float = 1.0          # exposure multiplier at default settings
    glare: bool = False
    angle: float = 0.0
    shift: tuple[int, int] = (0, 0)
    seed: int = 0

    @property
    def defective(self) -> bool:
        return bool(self.defects)


def _draw_defects(img: np.ndarray, defects: list[dict]) -> None:
    for d in defects:
        if d["kind"] == "scratch":
            (x0, y0), (x1, y1) = d["p0"], d["p1"]
            cv2.line(img, (x0, y0), (x1, y1), (225, 225, 230), d.get("width", 3), cv2.LINE_AA)
        elif d["kind"] == "stain":
            x, y, r = d["x"], d["y"], d["r"]
            cv2.circle(img, (x, y), r, (105, 115, 120), -1, cv2.LINE_AA)
        elif d["kind"] == "missing_hole":
            y, x = HOLES[d["hole"]]
            cv2.circle(img, (x, y), 36, (170, 170, 175), -1)
        elif d["kind"] == "faint_spot":
            x, y = d["x"], d["y"]
            cv2.circle(img, (x, y), 7, (146, 146, 151), -1, cv2.LINE_AA)


class SimCamera:
    DEFAULT = {"refocus": False, "exposure": 1.0, "polarizer": False}

    def __init__(self) -> None:
        self.ref = reference_part()

    def capture(self, part: Part, settings: dict | None = None) -> np.ndarray:
        s = {**self.DEFAULT, **(settings or {})}
        rng = np.random.default_rng(part.seed)
        img = self.ref.copy()
        _draw_defects(img, part.defects)
        H, W = SIZE
        # Pose: rotate/shift the part in a padded "world" so no part pixels are
        # lost, then crop the camera's field of view.
        P = 80
        world = cv2.copyMakeBorder(img, P, P, P, P, cv2.BORDER_CONSTANT, value=(40, 40, 40))
        M = cv2.getRotationMatrix2D((W / 2 + P, H / 2 + P), part.angle, 1.0)
        M[:, 2] += part.shift
        img = cv2.warpAffine(world, M, (W + 2 * P, H + 2 * P), borderValue=(40, 40, 40))[P:P + H, P:P + W]
        if part.glare and not s["polarizer"]:
            cx, cy = 180 + part.seed % 250, 160 + part.seed % 150
            spot = np.zeros(img.shape[:2], np.float32)
            cv2.circle(spot, (cx, cy), 70, 1.0, -1)
            spot = cv2.GaussianBlur(spot, (0, 0), 6.0)[..., None]
            img = (img * (1 - spot) + 255 * spot).astype(np.uint8)
        if part.blur > 0 and not s["refocus"]:
            img = cv2.GaussianBlur(img, (0, 0), part.blur)
        img = np.clip(img.astype(np.float32) * part.gain * float(s["exposure"]), 0, 255)
        img += rng.normal(0, 3.0, img.shape)  # sensor noise
        return np.clip(img, 0, 255).astype(np.uint8)


def make_dataset(n: int = 60, seed: int = 7) -> list[Part]:
    """Balanced set mixing clean/defective parts with capture nuisances."""
    rng = np.random.default_rng(seed)
    parts = []
    kinds = ["scratch", "stain", "missing_hole", "faint_spot"]
    for i in range(n):
        defects: list[dict] = []
        if i % 2 == 1:
            k = kinds[(i // 2) % len(kinds)]
            if k == "scratch":
                x, y = int(rng.integers(120, 460)), int(rng.integers(220, 400))
                defects.append({"kind": k, "p0": (x, y), "p1": (x + int(rng.integers(60, 140)), y + int(rng.integers(-30, 30)))})
            elif k == "stain":
                defects.append({"kind": k, "x": int(rng.integers(200, 450)), "y": int(rng.integers(340, 400)), "r": int(rng.integers(12, 26))})
            elif k == "missing_hole":
                defects.append({"kind": k, "hole": int(rng.integers(0, len(HOLES)))})
            else:
                defects.append({"kind": k, "x": int(rng.integers(150, 500)), "y": int(rng.integers(330, 400))})
        nuis = i % 5  # 0 clean capture, 1 blur, 2 dark, 3 glare, 4 bright
        parts.append(Part(
            part_id=f"P{i:03d}", defects=defects,
            blur=3.5 if nuis == 1 else 0.0,
            gain={2: 0.3, 4: 1.6}.get(nuis, 1.0),
            glare=nuis == 3,
            angle=float(rng.uniform(-6, 6)),
            shift=(int(rng.integers(-15, 15)), int(rng.integers(-15, 15))),
            seed=int(rng.integers(0, 10_000)),
        ))
    return parts
