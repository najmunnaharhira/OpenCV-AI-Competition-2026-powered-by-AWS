# Plan: OpenCV AI Competition 2026 entry

Deadline: **Oct 26 2026, 11:59 pm PT** (Oct 27, 12:59 pm GMT+6). Today: Oct 5.

## Idea options

1. **InspectAgent: agentic visual inspection (recommended, already scaffolded).** OpenCV 5 judges each
   image and the agent changes camera settings, zooms in, rejects, or asks a human to quarantine a lot.
   Hits the Agentic Vision rule directly (vision output changes the next tool call) and the
   "active perception for autonomous inspection" suggested area. COOL on Graviton is an add-on.
2. **Site safety monitor.** PPE/zone-intrusion detection on video with an agent that escalates, requests
   a second camera angle, or opens an incident. Higher demo appeal, but needs a DNN model and real video.
3. **Crop/leaf health scout.** Agent plans which field photos to re-take or zoom based on OpenCV
   colour/texture analysis. Strong impact story, weaker controllable demo.

## Requirement checklist

See [REQUIREMENTS.md](REQUIREMENTS.md) for every requirement, where it is met, and what is still open.

## Timeline

| Dates | Work |
|---|---|
| Oct 5-7 | Pick idea, create repo, push scaffold. AWS account + Bedrock model access. |
| Oct 7-14 | Grant check-in if you received a grant. Deploy SAM stack; run Claude planner eval on 40 parts. |
| Oct 8-15 | Real-data evaluation: add an MVTec AD category (e.g. `metal_nut`, non-commercial licence) or own photos; tune thresholds on a validation split. |
| Oct 13-18 | Optional COOL: Graviton EC2 benchmark stock vs COOL, arm64 vs x86 Lambda latency/cost. |
| Oct 18-22 | Write report, export diagrams, collect failure cases and traces. |
| Oct 22-24 | Record and edit the video; dry-run the live demo URL. |
| Oct 25 | Buffer. Submit early on Oct 25-26. |

## Open questions for you

- AWS account available? Region preference? Did you receive the compute grant?
- Team name and members for the report and video.
