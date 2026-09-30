# Midjourney API Reference (midjourney-api.com)

Source: https://docs.midjourney-api.com/api-reference/endpoint/create and
https://docs.midjourney-api.com/api-reference/endpoint/jobstatus

## Base URL & authentication

- **Base URL:** `https://api.midjourney-api.com`
- **Auth header:** `API-KEY: <your-key>` (obtain from https://midjourney-api.com/dashboard)
- **Content type:** `Content-Type: application/json` on every POST
- New accounts receive a default key and 10 trial quota.

## Endpoint 1 — Create a generation

`POST /midjourney/v1/submit-jobs`

### Request body

| Field     | Type            | Required | Default | Description |
| --------- | --------------- | -------- | ------- | ----------- |
| `prompt`  | string          | yes      | —       | Text prompt. Append Midjourney args: `--ar 16:9`, `--niji 6`, `--style raw`, `--s 250`, etc. |
| `mode`    | enum `<string>` | no       | `fast`  | `fast` or `relaxed`. |
| `hookUrl` | string          | no       | —       | Callback URL notified when the task finishes. |
| `timeout` | integer         | no       | `600`   | Task timeout in **seconds**, range 300–1200. |

cURL:

```bash
curl --request POST \
  --url https://api.midjourney-api.com/midjourney/v1/submit-jobs \
  --header 'API-KEY: <api-key>' \
  --header 'Content-Type: application/json' \
  --data '{
    "prompt": "a boy play with a girl --niji 7",
    "mode": "fast",
    "hookUrl": "https://api.example.com/webhook",
    "timeout": 600
  }'
```

### Response (200)

```json
{
  "status": 0,
  "message": "success",
  "data": { "taskId": "TzmJP821WQM5jHOx7nR7r" }
}
```

Top-level `status` codes:

| Code  | Meaning |
| ----- | ------- |
| `0`   | success |
| `1001`| quota not enough |
| `1002`| concurrency limit, max 30 |

## Endpoint 2 — Job status / poll result

`POST /midjourney/v1/job-status`

### Request body

| Field     | Type       | Required | Description |
| --------- | ---------- | -------- | ----------- |
| `taskIds` | string[]   | yes      | One or more task ids returned by submit-jobs. |

cURL:

```bash
curl --request POST \
  --url https://api.midjourney-api.com/midjourney/v1/job-status \
  --header 'API-KEY: <api-key>' \
  --header 'Content-Type: application/json' \
  --data '{ "taskIds": ["TzmJP821WQM5jHOx7nR7r"] }'
```

### Response (200)

```json
{
  "status": 0,
  "message": "success",
  "data": [
    {
      "taskId": "JRTcg7frYrVn4PsnsboH6",
      "status": 1,
      "jobId": "089b3f2e-b120-4c30-8c1e-6bb02851f661",
      "image": "https://cdn.midjourney.com/089b3f2e-.../grid_0.png",
      "images": [
        "https://cdn.midjourney.com/089b3f2e-.../0_0.png",
        "https://cdn.midjourney.com/089b3f2e-.../0_1.png",
        "https://cdn.midjourney.com/089b3f2e-.../0_2.png",
        "https://cdn.midjourney.com/089b3f2e-.../0_3.png"
      ],
      "imgUrls": [
        "https://c1.tujiangjiang.com/..._0_0.png, https://c2.tujiangjiang.com/.../0_0.png"
      ],
      "prompt": "a dog play with a boy --niji 6 --ar 9:16",
      "mjPrompt": "a dog play with a boy --niji 6 --ar 9:16",
      "createdAt": 1766915367000,
      "meta": { "width": 816, "height": 1456 }
    }
  ]
}
```

### Per-task `status` field

| Code | Meaning |
| ---- | ------- |
| `0`  | in progress |
| `1`  | completed successfully |
| `2`  | failed (see `failReason`) |

### Result fields

| Field       | Type       | Notes |
| ----------- | ---------- | ----- |
| `taskId`    | string     | Echo of the polled id. |
| `status`    | integer    | 0/1/2 as above. |
| `jobId`     | string     | Internal Midjourney job id (present when finished). |
| `image`     | string     | URL of the 2×2 grid image. |
| `images`    | string[]   | URLs of individually upscaled variants (0_0 … 0_3). |
| `imgUrls`   | string[]   | Alternate CDN mirror URLs (comma-separated strings). |
| `prompt`    | string     | The prompt you submitted. |
| `mjPrompt`  | string     | The prompt actually executed by Midjourney. |
| `createdAt` | integer    | Unix epoch **milliseconds**. |
| `meta`      | object     | `{ "width": int, "height": int }`. |
| `failReason`| string     | Present only when `status` is 2. |

## Error handling cheat-sheet

- Top-level submit `status` `1001` → account quota exhausted; top up at the dashboard.
- Top-level submit `status` `1002` → too many concurrent tasks (max 30); slow down or wait.
- Per-task `status` `2` → inspect `failReason` (often an invalid `--style` / `--cref` / personalize code); correct the prompt and resubmit.
- HTTP `400` → malformed request body; verify JSON and required `prompt`.

## Notes

- Generation is asynchronous: `submit-jobs` only returns a `taskId`. Always call `job-status` to get the image.
- `imgUrls` entries are comma-separated strings (one string may contain several URLs); the CLI prefers `images` for clean per-file downloads.
- Upscale / variation / blend / inpaint endpoints are listed as "updating" in the upstream docs and are not covered here.
