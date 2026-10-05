"""Benchmark the core OpenCV workload of one inspection.

Run the same script on the same Graviton instance twice: once with the stock
opencv-python-headless wheel (baseline) and once with COOL (Cloud-Optimized
OpenCV Library from AWS Marketplace) on PYTHONPATH, then compare the JSON.

    python -m bench.bench_ops --label stock --iters 200
    PYTHONPATH=/opt/cool/python python -m bench.bench_ops --label cool --iters 200
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import time

import cv2

from inspectagent import vision
from inspectagent.camera import Part, SimCamera


def timed(fn, iters):
    for _ in range(5):
        fn()
    xs = []
    for _ in range(iters):
        t = time.perf_counter()
        fn()
        xs.append((time.perf_counter() - t) * 1000)
    xs.sort()
    return {"p50_ms": round(statistics.median(xs), 3), "p95_ms": round(xs[int(0.95 * len(xs)) - 1], 3)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="stock")
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--threads", type=int, default=0, help="cv2.setNumThreads; 0 = OpenCV default")
    a = ap.parse_args()
    if a.threads:
        cv2.setNumThreads(a.threads)
    cam = SimCamera()
    img = cam.capture(Part("bench", angle=4.0, shift=(10, -6),
                           defects=[{"kind": "scratch", "p0": (200, 300), "p1": (320, 310)}]))
    aligned, valid, _ = vision.align_to_reference(img, cam.ref)
    ops = {
        "assess_quality": lambda: vision.assess_quality(img),
        "align_to_reference": lambda: vision.align_to_reference(img, cam.ref),
        "residual": lambda: vision.residual(aligned, cam.ref, valid),
        "detect_defects": lambda: vision.detect_defects(aligned, cam.ref, 1.0, valid),
        "full_inspection": lambda: vision.detect_defects(
            *vision.align_to_reference(img, cam.ref)[:1], cam.ref, 1.0),
    }
    res = {"label": a.label, "opencv": cv2.__version__, "machine": platform.machine(),
           "cpus": os.cpu_count(), "threads": cv2.getNumThreads(),
           "build_simd": [l.strip() for l in cv2.getBuildInformation().splitlines()
                          if "CPU/HW features" in l or "Baseline" in l or "Dispatched" in l],
           "results": {k: timed(f, a.iters) for k, f in ops.items()}}
    full = res["results"]["full_inspection"]["p50_ms"]
    res["images_per_second_single_core_est"] = round(1000 / full, 1)
    os.makedirs("bench/results", exist_ok=True)
    with open(f"bench/results/{a.label}-{platform.machine()}.json", "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
