# Plan: Add Real-Time Video Stream Analysis via GPT-4.1 Vision

## Overview

The current project polls an overlays.uno scoreboard URL every 10 seconds and uses an LLM to generate handball commentary based on score/time changes. The plan is to extend this by also capturing frames from a live video stream and sending them to GPT-4.1 Vision, so the model can describe *what it sees* on the court — goals, saves, fast breaks, fouls — and combine that with the scoreboard data for richer, more grounded commentary.

---

## Proposed Architecture

```
Video Stream (camera / RTSP / HLS)
        │
        ▼
  Frame Extractor (OpenCV / FFmpeg)   ←── every 10 seconds (matches POLL_INTERVAL)
        │
        ├──► Azure OpenAI GPT-4.1 Vision  ──► "What's happening visually?"
        │                                              │
        └──► scraper.py (scoreboard)       ──► "Score changed: 3→4"
                                                       │
                                               analyzer.py combines both
                                                       │
                                               GPT-4.1 generates commentary
                                                       │
                                            Live Dashboard (port 8080)
```

---

## New Components

| Component | File | Purpose |
|---|---|---|
| Frame extractor | `video_capture.py` | Captures a frame from the video stream URL using OpenCV/FFmpeg and returns it as a base64-encoded JPEG |
| Vision analyzer | `vision_analyzer.py` | Sends the frame to Azure OpenAI GPT-4.1 Vision and returns a natural language description of the action |
| Combined analyzer | `analyzer.py` (modified) | Merges the visual description from `vision_analyzer.py` with the scoreboard change from `scraper.py` into a single richer prompt |
| Config | `.env.example` (modified) | Adds `VIDEO_STREAM_URL` and `VISION_ENABLED=true/false` variables |
| ARM template | `azuredeploy.json` (modified) | Adds `videoStreamUrl` parameter and updates model `allowedValues` to include `gpt-4.1` as default |

---

## New Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VIDEO_STREAM_URL` | *(empty)* | RTSP, HLS, or HTTP URL of the live video stream |
| `VISION_ENABLED` | `false` | Set to `true` to enable frame capture and vision analysis |
| `VISION_DETAIL` | `low` | OpenAI image detail mode: `low` (faster, cheaper) or `high` (more accurate) |
| `VISION_FRAME_INTERVAL` | `10` | Seconds between frame captures (defaults to match `POLL_INTERVAL`) |

---

## Azure OpenAI Changes

- Change the recommended/default model from `gpt-4o-mini` to **`gpt-4.1`** in `azuredeploy.json`
- Add `gpt-4.1` and `gpt-4.1-mini` to `allowedValues`
- The vision API call uses the same Azure OpenAI endpoint — no new Azure resource needed
- Image frames are sent as base64-encoded data URLs in the `image_url` message content block

---

## Cost Estimate (per game hour)

Based on 10-second poll interval (360 calls/hour), GPT-4.1 Vision pricing on Azure:

| Mode | Image tokens/call | Cost/hour | Cost/game (~60 min) |
|---|---|---|---|
| `low` detail | ~1,000 | ~$0.58 | ~$0.58 |
| `high` detail | ~2,500 | ~$2.50–$4.00 | ~$2.50–$4.00 |

**Recommendation:** Use `low` detail — sufficient for action recognition in handball, much cheaper.

---

## Implementation Steps (for follow-up PRs)

1. **PR 2 – `video_capture.py`**: Implement frame extraction from RTSP/HLS using OpenCV (`cv2.VideoCapture`) or FFmpeg subprocess. Return a base64 JPEG string.
2. **PR 3 – `vision_analyzer.py`**: Implement the Azure OpenAI vision call using the `image_url` content block. Accept a base64 frame and return a text description.
3. **PR 4 – `analyzer.py` update**: Merge visual description into the existing prompt. If `VISION_ENABLED=false` or `VIDEO_STREAM_URL` is empty, fall back to text-only mode (no breaking change).
4. **PR 5 – Config & ARM template update**: Add new env vars to `.env.example`, update `azuredeploy.json` with `videoStreamUrl` parameter and updated model list.
5. **PR 6 – Tests**: Add `tests/test_video_capture.py` and `tests/test_vision_analyzer.py` with mocked OpenCV and OpenAI calls.

---

## Dependencies to Add (`requirements.txt`)

```
opencv-python-headless>=4.8.0
```

> FFmpeg must be available in the container PATH for HLS stream support. The `Dockerfile` will need a `RUN apt-get install -y ffmpeg` step.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Video stream URL not always available | `VISION_ENABLED` flag — gracefully falls back to text-only |
| Frame extraction latency adds to poll cycle | Run frame capture in a separate thread |
| High-detail mode cost spike | Default to `low`, document the tradeoff |
| RTSP streams blocked by firewall | Support HLS (HTTP-based) as primary format |
