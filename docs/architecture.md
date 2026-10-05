# Architecture

Rendered diagrams: [architecture.png](diagrams/architecture.png), [agent_workflow.png](diagrams/agent_workflow.png). The mermaid versions below render on GitHub.

## System (OpenCV 5 + AWS)

```mermaid
flowchart LR
  subgraph Cell["Inspection cell (simulated camera today; real camera or S3 upload later)"]
    CAM[Camera with settings: focus, exposure, polarizer]
  end
  subgraph AWS["AWS account"]
    URL[Lambda Function URL] --> FN
    subgraph FN["Lambda container, arm64 / Graviton"]
      API[FastAPI + Mangum]
      AG[Agent executor + guardrails]
      CV[OpenCV 5 tools<br/>quality, ORB+RANSAC+ECC align,<br/>tolerant residual, close-up]
      API --> AG --> CV
    end
    AG <-->|tool use| BR[Amazon Bedrock<br/>Claude planner]
    AG -->|trace JSON + evidence JPEGs| S3[(S3)]
    AG -->|approval request| DDB[(DynamoDB approvals)]
    DDB -.-> SNS[SNS email to approver]
    FN -.-> XR[X-Ray + CloudWatch Logs]
  end
  Judge[Judge / operator browser] --> URL
  CV <-->|capture with new settings| CAM
```

## Agent loop (perception, decision, action)

```mermaid
flowchart TD
  A[capture_image] --> Q{OpenCV quality gate<br/>Laplacian var, mean, saturation}
  Q -- underexposed / overexposed --> E[scale exposure to mean 128] --> A
  Q -- glare --> P[enable polarizer] --> A
  Q -- blurry --> F[refocus] --> A
  Q -- remedy already tried or capture budget spent --> H1[request_human_approval<br/>manual_inspection]
  Q -- ok --> AL[align_to_reference]
  AL -- fails --> H1
  AL --> D[detect_defects sensitivity 1.0]
  D -- none, peak residual >= threshold/2 --> C[inspect_closeup sensitivity 2.0]
  D -- none, low residual --> PASS[pass_part]
  C -- none --> PASS
  C -- found --> S
  D -- found --> S{severity}
  S -- minor --> R[reject_part]
  S -- critical: missing feature, stain, area > 1500 px --> H2[request_human_approval<br/>quarantine_lot]
```

Guardrails enforced by the executor regardless of planner: no pass without a defect check on a
good-quality image; no auto-reject of a critical defect; at most 4 captures and 12 steps; planner
errors or refusals fall back to the rule planner and are logged.

## COOL path (optional, Best Use of COOL award)

Run `bench/bench_ops.py` on a Graviton EC2 instance with the stock wheel and with COOL from AWS
Marketplace, then serve the COOL build in the Lambda/ECS arm64 image. The claimed core workload is
the OpenCV part of each inspection (`align_to_reference` + `detect_defects`).
