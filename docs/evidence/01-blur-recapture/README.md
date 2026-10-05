# Blurry capture: OpenCV sharpness drives a refocus

The first image fails the Laplacian sharpness gate, so the agent recaptures with refocus before inspecting.

Ground truth: `no defect`  
Outcome: **pass**  (no defects; peak residual 3.0)

| step | tool | arguments | OpenCV 5 output | why this step |
|---|---|---|---|---|
| 1 | `capture_image` | `{"refocus": false, "exposure": 1.0, "polarizer": false}` | sharpness=83.7 mean=128.7 glare=0.0 issues=['blurry'] | start with default camera settings |
| 2 | `capture_image` | `{"refocus": true, "exposure": 1.0, "polarizer": false}` | sharpness=261.1 mean=128.7 glare=0.0 issues=none | blurry: Laplacian variance 83.7 < 120.0 -> refocus |
| 3 | `align_to_reference` | `{}` | inliers=381 ecc=0.9999 rotation=3.0 deg | image quality ok -> register to reference |
| 4 | `detect_defects` | `{"sensitivity": 1.0}` | threshold=30.0 peak_residual=3.0 regions=0 [] | aligned -> production defect check |
| 5 | `pass_part` | `{"rationale": "no defects; peak residual 3.0"}` | {"ok": true} | clean |

![annotated.jpg](annotated.jpg) ![capture_1.jpg](capture_1.jpg) ![capture_2.jpg](capture_2.jpg)
