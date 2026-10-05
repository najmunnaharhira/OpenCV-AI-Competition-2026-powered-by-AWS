# Submission form fields

Copy each section into the matching field on the submission page.

## Project name (59 of 60 characters)

InspectAgent: Agentic Visual Inspection with OpenCV 5 + AWS

## Elevator pitch

An AI quality inspector that judges every photo with OpenCV 5, fixes bad shots, zooms in when unsure, and asks a human before stopping the line.

## Testing instructions (file upload)

Upload `TESTING.pdf` from this repo. It is the same content as `TESTING.md`.

## Video demo link

Upload the video to YouTube as Unlisted (5 minutes or less) and paste the link here.
The script is in `docs/VIDEO_SCRIPT.md`.

## Built with (20 tags)

python, opencv, opencv-5, numpy, aws, aws-lambda, aws-graviton, amazon-bedrock, claude, amazon-s3, amazon-dynamodb, amazon-sns, aws-sam, aws-x-ray, docker, fastapi, mangum, pytest, html, javascript

## "Try it out" links

- Code: https://github.com/najmunnaharhira/OpenCV-AI-Competition-2026-powered-by-AWS
- Live demo: the `DemoUrl` output of the AWS deployment (add it once the stack is deployed)

## About the project (paste everything below this line)

## Inspiration

Most automated visual inspection is one-shot: take one photo, run one fixed pipeline, output pass or fail. On a real line, that one photo is often the problem. A part arrives slightly rotated, the lens drifts out of focus, the lighting changes, or a reflection hides the surface. One-shot systems then either let defects escape or reject good parts, and people stop trusting them.

A human inspector does something different. When the view is bad, they adjust the light and look again. When something looks odd, they lean in for a closer look. When the problem is serious, they call a supervisor before stopping production. We wanted a system that behaves that way, with OpenCV 5 measurements deciding each next step.

## What it does

InspectAgent runs a perception, decision and action loop for every part:

1. **Capture and judge the image.** OpenCV 5 measures sharpness (variance of the Laplacian), exposure and glare.
2. **Fix a bad capture.** If the image is too dark or too bright, the agent rescales exposure. If there is glare, it enables a polarizer. If it is blurry, it refocuses. Then it captures again, one fix at a time.
3. **Register to a golden reference.** ORB features, a RANSAC similarity fit and ECC refinement align the part to sub-pixel accuracy.
4. **Find defects.** A misalignment-tolerant residual against the reference, followed by morphology and connected components, finds scratches, stains, spots and missing features.
5. **Look closer when unsure.** If nothing crosses the production threshold but the residual is close, the agent zooms into that area and re-checks at higher sensitivity.
6. **Act.** It passes the part, rejects it, or, for critical defects such as a missing hole, requests human approval to quarantine the lot.

The planner that chooses each tool call is either a deterministic rule policy or **Claude on Amazon Bedrock**, which receives the OpenCV measurements (and the close-up image) and picks the next tool. Both go through the same executor, which enforces guardrails. A part cannot pass without a defect check on a good image. A critical defect cannot be auto-rejected without a human. Captures and steps have budgets. Planner errors fall back to the rule policy. Every step is logged with the OpenCV evidence behind it.

## How we built it

- **OpenCV 5.0** (`opencv-python-headless==5.0.0.93`) for all image analysis.
- **AWS Lambda on Graviton (arm64)**, packaged as a container and served through a Function URL with FastAPI and Mangum.
- **Amazon Bedrock** (Claude) as the agent planner, using tool use.
- **Amazon S3** for traces and evidence images, **DynamoDB** for the approval queue, **SNS** to notify the approver, and **X-Ray** for tracing, all defined in one **AWS SAM** template.
- A reproducible synthetic inspection cell that generates parts with ground-truth defects and capture problems, and a camera the agent can control, so every result can be re-run by judges.
- A small web UI that shows the decision, the step-by-step trace, the evidence images and approve or decline buttons.

The sharpness gate uses the variance of the Laplacian:

$$ S = \operatorname{Var}\left(\nabla^2 I\right), \qquad \text{blurry if } S < 120 $$

The residual only counts a pixel as different when it falls outside the local range of the reference, which tolerates about 2 px of misregistration:

$$ R(x) = \max\big(I(x) - \max_{N(x)} T,\; \min_{N(x)} T - I(x),\; 0\big) $$

## Results

On 200 synthetic parts (seed 11), compared with a static one-shot OpenCV pipeline:

| metric | static baseline | InspectAgent |
|---|---|---|
| pass/fail accuracy | 72.0% | 99.0% |
| defective parts passed (false accept) | 16.0% | 2.0% |
| good parts rejected (false reject) | 40.0% | 0.0% |
| decision matches policy | 60.5% | 97.0% |
| mean captures per part | 1.0 | 1.8 |

Under glare the baseline was right 50% of the time and the agent 100%. Under blur the baseline was right 50% of the time and the agent 97.5%.

## Challenges we ran into

- **False defects along part edges.** A full homography extrapolated badly at the plate edges and produced fake "scratches". Switching to a 4-DoF similarity fit with ECC refinement, a validity mask for out-of-frame pixels and a min/max-envelope residual brought false rejects to zero.
- **Dark images looked blurry.** Underexposure lowers the Laplacian variance, so the agent kept refocusing an image that only needed more exposure. We now fix exposure first, then glare, then focus, and escalate instead of retrying a remedy that already failed.
- **Faint defects.** Low-contrast spots fell just below the production threshold. Lowering the threshold everywhere would add false alarms, so the agent takes a targeted close-up only when the residual is near the threshold.
- **Keeping an LLM planner safe.** We kept the guardrails in the executor, not in the prompt, so they hold whichever planner is driving.

## What we learned

The biggest gains did not come from a better detector. They came from letting the system notice a bad observation and take a better one. Measuring image quality explicitly, and making each action depend on that measurement, turned a brittle pipeline into one that recovers on its own and knows when to ask a person.

## Limitations and responsible use

- The headline numbers come from a synthetic cell. Real parts have texture, variation and lighting that make the problem harder. Real-image evaluation is the next step.
- Golden-reference comparison needs a reference image per part type and a fairly fixed camera setup.
- The defect-type classifier is a shape heuristic.
- One known failure: a faint spot on a part first captured heavily underexposed can still be missed (2 of 100 defective parts).
- Line-level actions always need human approval. Every decision is logged with its evidence, failures default to escalation rather than a silent pass, and the images contain no personal data.

## What's next

Evaluation on real defect images, more part types, a real camera driver behind the same interface, and a measured comparison of the OpenCV workload on Graviton with and without COOL.
