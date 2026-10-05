## Inspiration

Most automated visual inspection is one-shot: take one photo, run one fixed pipeline, output pass or fail. On a real line, that one photo is often the problem. A part arrives slightly rotated, the lens drifts out of focus, the lighting changes, or a reflection hides the surface. One-shot systems then either let defects escape or reject good parts, and people stop trusting them.

A human inspector does something different. When the view is bad, they adjust the light and look again. When something looks odd, they lean in for a closer look. When the problem is serious, they call a supervisor before stopping production. I wanted to build a system that behaves that way, with OpenCV 5 measurements deciding each next step.

## What it does

InspectAgent runs a perception, decision and action loop for every part:

1. **Capture and judge the image.** OpenCV 5 measures sharpness (variance of the Laplacian), exposure and glare.
2. **Fix a bad capture.** If the image is too dark or too bright, the agent rescales exposure. If there is glare, it enables a polarizer. If it is blurry, it refocuses. Then it captures again, one fix at a time.
3. **Register to a golden reference.** ORB features, a RANSAC similarity fit and ECC refinement align the part to sub-pixel accuracy.
4. **Find defects.** A misalignment-tolerant residual against the reference, followed by morphology and connected components, finds scratches, stains, spots and missing features.
5. **Look closer when unsure.** If nothing crosses the production threshold but the residual is close, the agent zooms into that area and re-checks at higher sensitivity.
6. **Act.** It passes the part, rejects it, or, for critical defects such as a missing hole, requests human approval to quarantine the lot.

The planner that chooses each tool call is either a deterministic rule policy or **Claude on Amazon Bedrock**, which receives the OpenCV measurements (and the close-up image) and picks the next tool. Both go through the same executor, which enforces guardrails: a part cannot pass without a defect check on a good image, a critical defect cannot be auto-rejected without a human, captures and steps have budgets, and planner errors fall back to the rule policy. Every step is logged with the OpenCV evidence behind it.

## How we built it

This is a solo project, so everything below was built by me.

- **OpenCV 5.0** (`opencv-python-headless==5.0.0.93`) for all image analysis.
- **AWS Lambda on Graviton (arm64)**, packaged as a container and served through a Function URL with FastAPI and Mangum.
- **Amazon Bedrock** (Claude) as the agent planner, using tool use.
- **Amazon S3** for traces and evidence images, **DynamoDB** for the approval queue, **SNS** to notify the approver, and **CloudWatch** and **X-Ray** for observability, all defined in one **AWS SAM** template.
- A reproducible synthetic inspection cell that generates parts with ground-truth defects and capture problems, and a camera the agent can control, so every result can be re-run by judges.
- A web UI that replays the agent's steps one by one, with the evidence images and approve or decline buttons.

The sharpness gate uses the variance of the Laplacian:

$$ S = \operatorname{Var}\left(\nabla^2 I\right), \qquad \text{blurry if } S < 120 $$

The residual only counts a pixel as different when it falls outside the local range of the reference $T$, which tolerates about 2 px of misregistration:

$$ R(x) = \max\big(I(x) - \max_{N(x)} T,\; \min_{N(x)} T - I(x),\; 0\big) $$

## Challenges we ran into

- **False defects along part edges.** A full homography extrapolated badly at the plate edges and produced fake "scratches". I switched to a 4-DoF similarity fit with ECC refinement, a validity mask for out-of-frame pixels and a min/max-envelope residual. That brought false rejects to zero.
- **Dark images looked blurry.** Underexposure lowers the Laplacian variance, so the agent kept refocusing an image that only needed more exposure. The agent now fixes exposure first, then glare, then focus, and escalates instead of retrying a remedy that already failed.
- **Faint defects.** Low-contrast spots fell just below the production threshold. Lowering the threshold everywhere would add false alarms, so I made the agent take a targeted close-up only when the residual is near the threshold.
- **Keeping an LLM planner safe.** I put the guardrails in the executor, not in the prompt, so they hold whichever planner is driving.

## Accomplishments that we're proud of

On 200 reproducible test parts, compared with the same OpenCV detector run once on a single photo:

| metric | one-shot pipeline | InspectAgent |
|---|---|---|
| pass/fail accuracy | 72.0% | **99.0%** |
| defective parts passed (false accept) | 16.0% | **2.0%** |
| good parts rejected (false reject) | 40.0% | **0.0%** |
| decision matches policy | 60.5% | **97.0%** |

- On images with glare, accuracy went from 50% to 100%. On blurry images, it went from 50% to 97.5%.
- Every decision comes with a trace showing which OpenCV measurement caused which action, for example a sharpness of 84 (below 120) triggering a refocus.
- Critical actions always go to a human, and a test shows the executor blocking a planner that tries to skip that step.
- The whole entry is reproducible: pinned dependencies, 12 automated tests, one evaluation command, and one SAM template for AWS.

## What we learned

The biggest gains did not come from a better detector. They came from letting the system notice a bad observation and take a better one. Measuring image quality explicitly, and making each action depend on that measurement, turned a brittle pipeline into one that recovers on its own and knows when to ask a person.

I also learned that the safety rules belong in code, not in a prompt. With the rules in the executor, the same guarantees hold whether a simple rule policy or an LLM is choosing the next step.

## What's next for InspectAgent: Agentic Visual Inspection with OpenCV 5 + AWS

- **Real images.** The current numbers come from a synthetic inspection cell. Real parts have texture, variation and lighting that make the problem harder, so evaluating on real defect images is the first step.
- **Fix the known misses.** 2 of 100 defective parts were missed because a very faint spot stayed below even the close-up threshold, and 4 stains were labelled as minor spots. A learned defect classifier could help with both.
- **More part types and a real camera.** The golden-reference method needs one reference per part type. A real camera driver can plug into the same interface.
- **COOL on Graviton.** Measure the OpenCV workload on AWS Graviton with and without the Cloud-Optimized OpenCV Library.
