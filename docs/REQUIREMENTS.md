# Submission requirements checklist

| Requirement | Where | Status |
|---|---|---|
| Technical report (problem, users, architecture, OpenCV 5, AWS, evaluation, limitations, responsible use) | `docs/REPORT.md`, `docs/REPORT.pdf` | Done; AWS numbers added after deploy |
| Judge-accessible code repository | this GitHub repo | Done |
| Pinned dependencies | `requirements.txt`, `requirements-dev.txt` | Done |
| Build, deploy and test instructions | `README.md`, `TESTING.md`, `TESTING.pdf` | Done |
| Architecture diagram (OpenCV 5, AWS, agent components) | `docs/diagrams/architecture.png` (+ `.svg`) | Done |
| Working web endpoint or live demo | Lambda Function URL from `deploy/template.yaml` | **Needs AWS deploy** |
| Video of 5 minutes or less (team, app working, architecture, results) | 4:41 narrated draft built by `video/`; script in `docs/VIDEO_SCRIPT.md` | **Upload to YouTube (unlisted)** |
| Evaluation evidence including failure cases | `eval/results/*.json`, report section 7, `docs/evidence/06-failure-case` | Done (synthetic); real images to add |

## Agentic Vision award

| Evidence | Where | Status |
|---|---|---|
| Agent workflow diagram (perception, decision, action) | `docs/diagrams/agent_workflow.png` | Done |
| Trace showing OpenCV 5 output changes a later decision | `docs/evidence/01` to `06`, report section 5, live UI trace | Done (rule planner); Claude planner trace **after deploy** |
| Task success | report section 7 (accuracy, false accept/reject, policy match) | Done |
| Failure handling | guardrail block (`04`), planner fallback (`05`), budget escalation, tests | Done |
| Observability | per-step JSON logs (CloudWatch), traces and evidence in S3, X-Ray | Done in code; visible **after deploy** |
| Appropriate human control | `request_human_approval`, DynamoDB + SNS, approve/decline in UI | Done |

## Best Use of COOL award (optional)

| Evidence | Where | Status |
|---|---|---|
| COOL version and AWS instance or deployment configuration | `docs/COOL.md` | **Needs Graviton + COOL** |
| Reproducible method, inputs, baselines, results | `bench/bench_ops.py`, `docs/COOL.md` | Method done; results pending |
| Evidence COOL runs the core workload | build info captured by the benchmark | Pending |
