# Video script (max 5:00)

| Time | Shot | Say |
|---|---|---|
| 0:00-0:20 | Team on camera | Who we are, the problem: one bad photo means a wrong pass or reject. |
| 0:20-0:50 | Architecture diagram | OpenCV 5 in a Graviton Lambda, Claude on Bedrock plans, S3/DynamoDB/SNS. |
| 0:50-2:00 | Live demo URL: blurry part | Trace shows Laplacian 84 < 120, agent refocuses, aligns, detects, passes. |
| 2:00-2:45 | Demo: faint spot | No defect at production threshold, residual near threshold, close-up finds it, reject. |
| 2:45-3:30 | Demo: missing hole | Critical defect, auto-reject blocked by guardrail, human approval request, approve in UI, email arrives. |
| 3:30-4:20 | Results | Agent vs baseline table, per-nuisance chart, failure case, (COOL numbers). |
| 4:20-5:00 | Limits and next steps | Real data, more part types, responsible-use controls. |
