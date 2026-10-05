"""OpenCV 5 perception tools.

Every function takes/returns plain numpy images and JSON-serialisable dicts so
the agent (rule-based or LLM) can call them as tools and log their outputs.
"""
from __future__ import annotations

import cv2
import numpy as np

# Thresholds are tuned on the synthetic validation split (see eval/run_eval.py).
BLUR_MIN = 120.0          # variance of Laplacian below this => image too blurry
DARK_MAX = 60.0           # mean intensity below this => under-exposed
BRIGHT_MIN = 170.0        # mean intensity above this => over-exposed
GLARE_FRAC_MAX = 0.02     # fraction of saturated pixels allowed
ALIGN_MIN_INLIERS = 25    # homography inliers needed to trust alignment
DEFECT_MIN_AREA = 25      # px; smaller blobs are treated as noise


def to_gray(img: np.ndarray) -> np.ndarray:
    return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def assess_quality(img: np.ndarray) -> dict:
    """Image quality gate: sharpness, exposure and glare."""
    g = to_gray(img)
    sharp = float(cv2.Laplacian(g, cv2.CV_64F).var())
    mean = float(g.mean())
    glare = float((g >= 250).mean())
    issues = []
    if sharp < BLUR_MIN:
        issues.append("blurry")
    if mean < DARK_MAX:
        issues.append("underexposed")
    elif mean > BRIGHT_MIN:
        issues.append("overexposed")
    if glare > GLARE_FRAC_MAX:
        issues.append("glare")
    return {"sharpness": round(sharp, 1), "mean_intensity": round(mean, 1),
            "glare_fraction": round(glare, 4), "issues": issues, "ok": not issues}


def enhance(img: np.ndarray, clip_limit: float = 2.0) -> np.ndarray:
    """Local contrast normalisation (CLAHE) on the luminance channel."""
    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    if img.ndim == 2:
        return clahe.apply(img)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    lab[..., 0] = clahe.apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def align_to_reference(img: np.ndarray, ref: np.ndarray):
    """ORB features + RANSAC similarity + ECC refinement to warp `img` onto `ref`.

    Returns (warped, valid_mask, info). `valid_mask` marks reference pixels the
    camera actually saw, so out-of-frame areas are never reported as defects.
    """
    g, r = to_gray(img), to_gray(ref)
    orb = cv2.ORB_create(nfeatures=2000)
    k1, d1 = orb.detectAndCompute(g, None)
    k2, d2 = orb.detectAndCompute(r, None)
    if d1 is None or d2 is None or len(k1) < 8 or len(k2) < 8:
        return None, None, {"ok": False, "inliers": 0, "reason": "too_few_features"}
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(d1, d2)
    matches = sorted(matches, key=lambda m: m.distance)[:500]
    if len(matches) < 8:
        return None, None, {"ok": False, "inliers": 0, "reason": "too_few_matches"}
    src = np.float32([k1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([k2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    # Parts are rigid and the camera is fixed, so a 4-DoF similarity is enough
    # and far more stable than a full homography; ECC then refines to sub-pixel.
    A, mask = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC,
                                          ransacReprojThreshold=3.0)
    inliers = int(mask.sum()) if mask is not None else 0
    if A is None or inliers < ALIGN_MIN_INLIERS:
        return None, None, {"ok": False, "inliers": inliers, "reason": "weak_alignment"}
    size = (ref.shape[1], ref.shape[0])
    ecc = None
    try:
        warp = A.astype(np.float32)
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-5)
        g_ref = cv2.GaussianBlur(r, (5, 5), 0).astype(np.float32)
        g_img = cv2.GaussianBlur(g, (5, 5), 0).astype(np.float32)
        # ECC maps ref->img coordinates, so refine the inverse and invert back.
        inv = cv2.invertAffineTransform(warp)
        ecc, inv = cv2.findTransformECC(g_ref, g_img, inv, cv2.MOTION_EUCLIDEAN, crit, None, 5)
        A = cv2.invertAffineTransform(inv)
    except cv2.error:
        pass  # keep the feature-based estimate
    warped = cv2.warpAffine(img, A, size, borderMode=cv2.BORDER_REPLICATE)
    valid = cv2.warpAffine(np.full(g.shape, 255, np.uint8), A, size)
    valid = cv2.erode(valid, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15)))
    angle = float(np.degrees(np.arctan2(A[1, 0], A[0, 0])))
    return warped, valid, {"ok": True, "inliers": inliers,
                           "ecc": None if ecc is None else round(float(ecc), 4),
                           "rotation_deg": round(angle, 2),
                           "coverage": round(float((valid > 0).mean()), 3)}


def residual(img: np.ndarray, ref: np.ndarray, valid: np.ndarray | None = None) -> np.ndarray:
    """Misalignment-tolerant difference map between an aligned image and the reference."""
    g = cv2.GaussianBlur(to_gray(img), (5, 5), 0)
    r = cv2.GaussianBlur(to_gray(ref), (5, 5), 0)
    # Linear gain/offset match inside the visible area compensates exposure.
    m = valid if valid is not None else np.full(g.shape, 255, np.uint8)
    gm, gs = cv2.meanStdDev(g, mask=m)
    rm, rs = cv2.meanStdDev(r, mask=m)
    alpha = float(rs[0, 0] / max(gs[0, 0], 1e-3))
    g = cv2.convertScaleAbs(g, alpha=alpha, beta=float(rm[0, 0] - gm[0, 0] * alpha))
    # A pixel only counts as different if it is brighter than the local max or
    # darker than the local min of the reference (tolerates ~2 px misregistration).
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    diff = cv2.max(cv2.subtract(g, cv2.dilate(r, k)), cv2.subtract(cv2.erode(r, k), g))
    if valid is not None:
        diff = cv2.bitwise_and(diff, diff, mask=valid)
    return diff


def detect_defects(img: np.ndarray, ref: np.ndarray, sensitivity: float = 1.0,
                   valid: np.ndarray | None = None, roi: list[int] | None = None) -> dict:
    """Golden-reference defect detection on an aligned image.

    Returns candidate regions with area, bbox and a contrast score. A higher
    `sensitivity` lowers the threshold; `roi` [x, y, w, h] restricts the search
    (used for close-up re-inspection).
    """
    diff = residual(img, ref, valid)
    if roi is not None:
        x, y, w, h = roi
        keep = np.zeros_like(diff)
        keep[max(0, y):y + h, max(0, x):x + w] = 255
        diff = cv2.bitwise_and(diff, keep)
    thr = max(8.0, 30.0 / max(sensitivity, 1e-3))
    _, mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask)
    regions = []
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area < DEFECT_MIN_AREA:
            continue
        score = float(diff[y:y + h, x:x + w].mean())
        regions.append({"bbox": [x, y, w, h], "area": area, "contrast": round(score, 1),
                        "kind": _classify(w, h, area)})
    regions.sort(key=lambda d: d["area"], reverse=True)
    # Peak residual inside the part (ignores a thin border affected by warping).
    peak = float(diff[8:-8, 8:-8].max()) if diff.shape[0] > 16 else float(diff.max())
    return {"threshold": thr, "peak_residual": round(peak, 1),
            "regions": regions, "count": len(regions),
            "total_area": int(sum(d["area"] for d in regions))}


def _classify(w: int, h: int, area: int) -> str:
    """Cheap shape heuristic: elongated blobs are scratches."""
    elong = max(w, h) / max(1, min(w, h))
    fill = area / max(1, w * h)
    if elong > 4 or fill < 0.25:
        return "scratch"
    if area > 600:
        return "stain_or_missing_feature"
    return "spot"


def zoom_region(img: np.ndarray, bbox: list[int], pad: int = 16, scale: int = 3) -> np.ndarray:
    x, y, w, h = bbox
    H, W = img.shape[:2]
    x0, y0 = max(0, x - pad), max(0, y - pad)
    x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
    crop = img[y0:y1, x0:x1]
    return cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def annotate(img: np.ndarray, regions: list[dict]) -> np.ndarray:
    out = img.copy() if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    for d in regions:
        x, y, w, h = d["bbox"]
        cv2.rectangle(out, (x, y), (x + w, y + h), (0, 0, 255), 2)
        cv2.putText(out, d["kind"], (x, max(12, y - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.45, (0, 0, 255), 1, cv2.LINE_AA)
    return out
