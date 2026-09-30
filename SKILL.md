---
name: midjourney-api
description: AI 绘画 / 文生图 / 图像生成 / 图片生成 / 文本生成图像（通过 HTTP API 调用 midjourney-api.com，非 Discord、无需 Discord 账号、不使用 /imagine 命令）。调用 Midjourney 生图 API 根据文字 prompt 生成图片。Use when the user wants to 生成图片、AI 绘画、文生图、text-to-image、draw/imagine/render an image with Midjourney、提交生图任务、轮询异步任务结果、下载生成的图片 URL，或需要 Midjourney 风格的 AI art。覆盖 submit-jobs（创建任务）与 job-status（轮询结果）两个端点，并附带一条龙的 CLI（提交→等待→下载）。关键词：Midjourney、MJ、AI 作画、AI绘、生图、出图、图生图、以文生图、stable diffusion 替代、图像创作、HTTP API。
license: MIT
---

# Midjourney API（文生图 · 通过 HTTP API 调用）

## 概述（中文）

本技能通过 **HTTP API** 调用 `api.midjourney-api.com` 来生成图片，**不依赖 Discord 机器人、不需要 Discord 账号、不使用 `/imagine` 命令**。整个流程完全由脚本 `scripts/midjourney.py` 完成：提交 prompt → 拿到 `taskId` → 轮询直到完成 → 下载图片 URL 到本地。

使用前提：需要一个 `MIDJOURNEY_API_KEY`（在 https://midjourney-api.com/dashboard 申请），通过环境变量传入即可，无需任何 Discord 相关配置。

## Overview (English)

This skill lets the agent drive the Midjourney REST API hosted at `https://api.midjourney-api.com`. Image generation is **asynchronous**: you submit a prompt, receive a `taskId`, then poll that task until it finishes and returns image URLs. A bundled CLI (`scripts/midjourney.py`) handles the whole submit to poll to download loop so the agent does not have to reimplement HTTP plus polling.

## Quick start

1. Ensure the API key is available. The CLI reads it from the `MIDJOURNEY_API_KEY` environment variable (or `MJ_API_KEY` as a fallback). If it is missing, the script exits with a clear error.
2. Generate an image with a one-shot command:

```bash
python3 ~/.codebuddy/skills/midjourney-api/scripts/midjourney.py generate \
  --prompt "a serene lake at sunset --ar 16:9" \
  --out ./midjourney_out
```

That submits the job, polls every 10s (up to 20min by default), and downloads the grid plus individual images into `./midjourney_out`.

## API reference (the essentials)

> Load `references/api_reference.md` for the full field-by-field spec, response schemas, and error codes.

**Base URL:** `https://api.midjourney-api.com`
**Auth:** every request sends header `API-KEY: <your-key>` and `Content-Type: application/json`.

### 1. Create a generation — `POST /midjourney/v1/submit-jobs`

Body fields:

| Field     | Type            | Required | Notes |
| --------- | --------------- | -------- | ----- |
| `prompt`  | string          | yes      | Free-text Midjourney prompt; append params like `--ar 16:9`, `--niji 6`, `--style raw`. |
| `mode`    | enum            | no       | `fast` (default) or `relaxed`. |
| `hookUrl` | string          | no       | Webhook URL for async callback notification. |
| `timeout` | integer (seconds) | no    | 300 to 1200, default 600. |

Response (success):

```json
{ "status": 0, "message": "success", "data": { "taskId": "TzmJP821WQM5jHOx7nR7r" } }
```

Top-level `status` codes: `0` success, `1001` quota not enough, `1002` concurrency limit (max 30).

### 2. Poll the result — `POST /midjourney/v1/job-status`

Body: `{ "taskIds": ["<taskId>"] }` (array; you may query several at once).

Per-task `status`: `0` in progress, `1` completed, `2` failed (check `failReason`).

Completed task returns:

```json
{
  "taskId": "TzmJP821WQM5jHOx7nR7r",
  "status": 1,
  "jobId": "089b3f2e-...",
  "image": "https://cdn.midjourney.com/.../grid_0.png",
  "images": ["https://cdn.midjourney.com/.../0_0.png", "..."],
  "imgUrls": ["https://c1.tujiangjiang.com/...", "..."],
  "prompt": "a dog play with a boy --niji 6 --ar 9:16",
  "mjPrompt": "a dog play with a boy --niji 6 --ar 9:16",
  "createdAt": 1766915367000,
  "meta": { "width": 816, "height": 1456 }
}
```

`image` is the 2x2 grid; `images` is the list of individually upscaled variants.

## Workflow

**Recommended (most cases):** use the `generate` command — it submits, polls, and downloads in one step.

**Manual / piecewise workflow** when you need control (e.g. submit many prompts, then poll later):

1. **Submit** — run `submit` to get the `taskId`(s):
   ```bash
   python3 ~/.codebuddy/skills/midjourney-api/scripts/midjourney.py submit --prompt "a cyberpunk cat --niji 6"
   ```
2. **Poll** — either `status` (raw JSON, good for a quick check) or `poll` (waits and downloads):
   ```bash
   python3 ~/.codebuddy/skills/midjourney-api/scripts/midjourney.py poll --task-id TzmJP821WQM5jHOx7nR7r --out ./out
   ```
3. **Deliver** — report the downloaded local paths and/or the `image`/`images` URLs to the user.

## Decision guidance

- **Simple one-image request?** — use `generate` with `--out`.
- **User supplied their own task id or wants to check progress?** — use `status` or `poll`.
- **Batch of prompts?** — loop `submit` to collect task ids, then `poll` each (or `status` with multiple ids).
- **Generation failed (`status: 2`)?** — read `failReason`, fix the prompt (common: invalid `--style`/`--cref` codes), resubmit.
- **Quota / concurrency errors?** — `status: 1001` means top up quota; `1002` means wait or reduce parallel jobs.

## Notes and limits

- Max concurrency is 30 simultaneous tasks; default `timeout` is 600s (range 300 to 1200).
- The API is async by design — never treat `submit-jobs` as returning the image; always poll.
- Endpoint coverage here is limited to the documented `submit-jobs` and `job-status` endpoints. Upscale/variation/blend actions are listed as "updating" in the upstream docs and are **not** implemented in this skill.
- Never print or log the `API-KEY` value.
