# Technical report outline (target 6-8 pages)

1. **Problem and users.** Manual/one-shot automated inspection fails when the capture is poor (blur,
   exposure, glare, pose) or the defect is faint. Users: line QA engineers, small manufacturers without
   bespoke vision cells. Impact: fewer escaped defects, fewer false rejects, humans only on critical calls.
2. **System overview.** Architecture diagram (docs/architecture.md). Why a serverless arm64 deployment.
3. **OpenCV 5 implementation.** Quality gate (variance of Laplacian, intensity statistics, saturation);
   registration (ORB, RANSAC similarity, ECC refinement, validity mask); misalignment-tolerant residual
   (morphological min/max envelope of the reference) and gain matching; connected components + shape
   heuristic; close-up re-inspection. Version string from `/healthz`.
4. **Agent design.** Tools, planner options (rules, Claude on Bedrock), executor guardrails, step and
   capture budgets, fallback on planner failure, trace schema. One annotated trace where OpenCV output
   changes the next tool call (e.g. Laplacian 84 -> refocus -> pass).
5. **AWS deployment.** SAM template, Lambda Function URL, S3 evidence, DynamoDB approvals, SNS, Bedrock,
   X-Ray; cost per 1,000 inspections (measure).
6. **Evaluation.** Dataset and split; metrics (pass/fail accuracy, false accept, false reject, policy
   match, escalation rate, captures/steps, latency); agent vs static baseline; per-nuisance breakdown;
   rule vs Claude planner; real-data results.
7. **Failure cases and limitations.** Faint defect after heavy underexposure; synthetic data is easier
   than real parts; golden-reference method needs a reference per part type and fixed geometry; the
   shape-based defect classifier is heuristic.
8. **Responsible use.** Human approval for line-level actions; no personal data in images; audit trail;
   public URL disabled after judging; failure modes default to escalation, never silent pass.
9. **(Optional) COOL results.** COOL version, instance type, method, stock vs COOL tables.
