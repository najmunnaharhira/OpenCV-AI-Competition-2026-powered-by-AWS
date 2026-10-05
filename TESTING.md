# InspectAgent: testing instructions

Code: https://github.com/najmunnaharhira/OpenCV-AI-Competition-2026-powered-by-AWS

## 1. Use the live demo (recommended)

1. Open the demo URL listed in the submission's "Try it out" links.
2. Pick a part from the drop-down. Each entry shows the capture problem (blur, dark, bright, glare, none)
   and the ground-truth defect.
3. Press **Inspect**. The page shows the decision, the agent trace and the evidence images.
4. Things to try:

    - A part with capture **blur**: the trace shows the Laplacian sharpness below 120, the agent
      recaptures with refocus, then aligns, detects and decides.
    - A part with truth **faint_spot**: no defect at the production threshold, but the residual peak
      triggers `inspect_closeup`, which finds the spot and rejects the part.
    - A part with truth **missing_hole**: auto-reject is blocked by a guardrail. The agent requests
      human approval to quarantine the lot. Press **Approve** or **Decline** to record the decision.
    - Switch the planner to **Claude on Bedrock** to see the same tools driven by Claude.

## 2. Run locally (no AWS account needed)

Requires Python 3.12 (3.10+ works).

```bash
git clone https://github.com/najmunnaharhira/OpenCV-AI-Competition-2026-powered-by-AWS
cd OpenCV-AI-Competition-2026-powered-by-AWS
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                     # 12 tests, about 10 s
python -m eval.run_eval --n 200 --seed 11  # agent vs. static baseline table
uvicorn inspectagent.api:app               # then open http://127.0.0.1:8000
```

`GET /healthz` reports the OpenCV version (5.0.0) and the CPU architecture.

## 3. Run the Claude planner on Amazon Bedrock

Enable Claude model access in the Bedrock console, then:

```bash
export AWS_REGION=us-east-1 BEDROCK_MODEL_ID=anthropic.claude-opus-5-5
python -m eval.run_eval --n 40 --planner claude
```

If Bedrock is unreachable or the model refuses, the loop falls back to the rule planner and the
trace records a `planner_error` event.

## 4. Deploy your own copy to AWS (Graviton)

```bash
cd deploy
sam build --use-container
sam deploy --guided        # Architecture=arm64 by default
```

The `DemoUrl` stack output is the endpoint. Traces and evidence go to S3, and approval requests go to
DynamoDB with an SNS notification.

## 5. Expected results (seed 11, 200 synthetic parts)

| metric | static baseline | agent |
|---|---|---|
| pass/fail accuracy | 0.720 | 0.990 |
| false accept rate | 0.160 | 0.020 |
| false reject rate | 0.400 | 0.000 |
