# Optional: Best Use of COOL award

**Status: not run yet.** This needs a Graviton EC2 instance and a COOL subscription from AWS Marketplace.
No COOL numbers are claimed anywhere in this submission until this page has real results.

## Claimed core workload

The OpenCV part of each inspection: `assess_quality`, `align_to_reference` (ORB, RANSAC, ECC, warp) and
`detect_defects` (blur, residual, morphology, connected components). `bench/bench_ops.py` times each
operation and the full inspection.

## Procedure

1. Launch a Graviton instance (for example c7g.xlarge, Amazon Linux 2023) and subscribe to COOL in AWS Marketplace.
2. Record the COOL version and the instance details (type, vCPUs, AMI or container image).
3. Baseline with the stock wheel:
   ```bash
   pip install -r requirements.txt
   python -m bench.bench_ops --label stock --iters 300 --threads 1
   python -m bench.bench_ops --label stock --iters 300
   ```
4. Run the same commands with the COOL build first on `PYTHONPATH` (or in the COOL container), using
   `--label cool`.
5. **Evidence that COOL runs the workload:** each result JSON records `cv2.__version__` and the build
   information lines. Also save the full `python -c "import cv2; print(cv2.getBuildInformation())"` output
   for both runs.
6. Optional x86 vs. arm comparison: run `stock` on a c7i.xlarge and deploy the SAM stack with
   `Architecture=x86_64` and `arm64`, then compare p50 latency and cost per 1,000 inspections.

## Results

| op (p50 ms) | stock arm64 | COOL arm64 | stock x86 |
|---|---|---|---|
| assess_quality | | | |
| align_to_reference | | | |
| detect_defects | | | |
| full_inspection | | | |
| images/s per core (est.) | | | |

Reference point from the development machine (x86_64, stock OpenCV 5.0.0): full inspection p50 is about 56 ms,
or about 18 images/s on one core.
