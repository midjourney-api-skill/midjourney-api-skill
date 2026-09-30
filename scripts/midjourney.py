#!/usr/bin/env python3
"""
Midjourney API CLI helper.

Wraps the midjourney-api.com REST API:
  - submit-jobs : create a text-to-image generation task (async)
  - job-status  : poll a task until it finishes and retrieve image URLs

Usage requires an API key exported as the MIDJOURNEY_API_KEY environment variable
(or MJ_API_KEY as a fallback).

Examples
--------
  # One-shot: generate, wait, and download the result images
  python3 midjourney.py generate --prompt "a serene lake at sunset --ar 16:9" --out ./out

  # Submit only and get a task id back
  python3 midjourney.py submit --prompt "a cyberpunk cat --niji 6"

  # Poll an existing task id until it completes
  python3 midjourney.py poll --task-id TzmJP821WQM5jHOx7nR7r --out ./out

  # Inspect raw status for one or more task ids
  python3 midjourney.py status --task-ids TzmJP821WQM5jHOx7nR7r
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://api.midjourney-api.com"
SUBMIT_ENDPOINT = "/midjourney/v1/submit-jobs"

# The API sits behind Cloudflare; a plain urllib User-Agent gets HTTP 403 / error 1010.
# Send a browser-like UA + headers on every request and image download.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
STATUS_ENDPOINT = "/midjourney/v1/job-status"

# Task status codes returned inside the job-status data array.
STATUS_IN_PROGRESS = 0
STATUS_COMPLETED = 1
STATUS_FAILED = 2


# --------------------------------------------------------------------------- #
# Core HTTP helpers
# --------------------------------------------------------------------------- #
def get_api_key():
    key = os.environ.get("MIDJOURNEY_API_KEY") or os.environ.get("MJ_API_KEY")
    if not key:
        sys.exit(
            "Error: API key not found. Export MIDJOURNEY_API_KEY "
            "(or MJ_API_KEY) before running this script."
        )
    return key


def _post(path, payload, api_key):
    """POST JSON to the API and always return (http_status, parsed_body)."""
    url = BASE_URL + path
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("API-KEY", api_key)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", _BROWSER_UA)
    req.add_header("Accept", "application/json")
    req.add_header("Origin", "https://midjourney-api.com")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return e.code, parsed
    except Exception as e:  # network / timeout errors
        return None, {"error": str(e)}


def submit(prompt, mode="fast", timeout=600, hook_url=None):
    payload = {"prompt": prompt, "mode": mode, "timeout": timeout}
    if hook_url:
        payload["hookUrl"] = hook_url
    return _post(SUBMIT_ENDPOINT, payload, get_api_key())


def query_status(task_ids):
    return _post(STATUS_ENDPOINT, {"taskIds": list(task_ids)}, get_api_key())


# --------------------------------------------------------------------------- #
# Polling + download
# --------------------------------------------------------------------------- #
def wait_for_task(task_id, poll_interval=10, max_wait=1200):
    """Poll job-status until the task completes, fails, or max_wait elapses."""
    waited = 0
    while waited <= max_wait:
        code, resp = query_status([task_id])
        if code != 200:
            print(f"  ! job-status returned HTTP {code}: {resp}", file=sys.stderr)
        else:
            for task in resp.get("data") or []:
                if task.get("taskId") == task_id:
                    st = task.get("status")
                    if st == STATUS_COMPLETED:
                        return task
                    if st == STATUS_FAILED:
                        return task
                    # STATUS_IN_PROGRESS or unknown -> keep waiting
        time.sleep(poll_interval)
        waited += poll_interval
        print(f"  ... still working ({waited}s elapsed)", file=sys.stderr)
    return None


def collect_images(task, out_dir):
    """Download the grid + individual images for a completed task.

    Primary CDN URLs (``images`` / ``image``) are tried first. If a download
    fails (e.g. Cloudflare blocks the datacenter IP with HTTP 403), it falls
    back to the mirror URLs in ``imgUrls``. Downloads smaller than 5 KB are
    treated as error pages and rejected.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    task_id = task.get("taskId", "task")
    saved = []

    images = task.get("images") or []
    mirror = []
    for entry in task.get("imgUrls") or []:
        for u in str(entry).split(","):
            u = u.strip()
            if u:
                mirror.append(u)

    def _grab(url, name):
        dest = out_dir / name
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _BROWSER_UA})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            if len(data) < 5000:
                raise IOError(f"only {len(data)} bytes, likely an error page")
            dest.write_bytes(data)
            saved.append(str(dest))
            print(f"  saved -> {dest}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"  ! failed to download {url}: {e}", file=sys.stderr)
            return False

    grid = task.get("image")
    if grid:
        _grab(grid, f"{task_id}_grid.png")

    for i, url in enumerate(images):
        if _grab(url, f"{task_id}_{i}.png"):
            continue
        if i < len(mirror):
            _grab(mirror[i], f"{task_id}_{i}.png")

    return saved


# --------------------------------------------------------------------------- #
# CLI commands
# --------------------------------------------------------------------------- #
def cmd_generate(args):
    code, resp = submit(
        args.prompt, mode=args.mode, timeout=args.timeout, hook_url=args.hook_url
    )
    if code != 200:
        print(json.dumps({"ok": False, "http_status": code, "response": resp}, ensure_ascii=False, indent=2))
        sys.exit(1)

    top_status = resp.get("status")
    if top_status not in (0, None):
        # 1001 quota not enough, 1002 concurrency limit
        print(json.dumps({"ok": False, "api_status": top_status, "response": resp}, ensure_ascii=False, indent=2))
        sys.exit(1)

    task_id = (resp.get("data") or {}).get("taskId")
    if not task_id:
        print(json.dumps({"ok": False, "error": "no taskId in submit response", "response": resp}, ensure_ascii=False, indent=2))
        sys.exit(1)

    print(f"Submitted task: {task_id}", file=sys.stderr)
    task = wait_for_task(task_id, poll_interval=args.poll_interval, max_wait=args.max_wait)
    if task is None:
        print(json.dumps({"ok": False, "error": "timeout waiting for task", "taskId": task_id}, ensure_ascii=False, indent=2))
        sys.exit(1)

    result = {"ok": True, "taskId": task_id, "status": task.get("status")}
    if task.get("status") == STATUS_FAILED:
        result["error"] = task.get("failReason")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)

    saved = collect_images(task, args.out) if args.out else []
    result["prompt"] = task.get("prompt")
    result["images"] = task.get("images")
    result["image"] = task.get("image")
    result["downloaded"] = saved
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_submit(args):
    code, resp = submit(
        args.prompt, mode=args.mode, timeout=args.timeout, hook_url=args.hook_url
    )
    print(json.dumps({"http_status": code, "response": resp}, ensure_ascii=False, indent=2))


def cmd_status(args):
    code, resp = query_status(args.task_ids)
    print(json.dumps({"http_status": code, "response": resp}, ensure_ascii=False, indent=2))


def cmd_poll(args):
    task = wait_for_task(args.task_id, poll_interval=args.poll_interval, max_wait=args.max_wait)
    if task is None:
        print(json.dumps({"ok": False, "error": "timeout waiting for task", "taskId": args.task_id}, ensure_ascii=False, indent=2))
        sys.exit(1)
    result = {"ok": True, "taskId": args.task_id, "status": task.get("status")}
    if task.get("status") == STATUS_FAILED:
        result["error"] = task.get("failReason")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(1)
    saved = collect_images(task, args.out) if args.out else []
    result["prompt"] = task.get("prompt")
    result["images"] = task.get("images")
    result["image"] = task.get("image")
    result["downloaded"] = saved
    print(json.dumps(result, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------- #
# Argument parsing
# --------------------------------------------------------------------------- #
def build_parser():
    p = argparse.ArgumentParser(description="Midjourney API CLI helper")
    sub = p.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="submit, wait, and download result images")
    g.add_argument("--prompt", required=True)
    g.add_argument("--mode", choices=["fast", "relaxed"], default="fast")
    g.add_argument("--timeout", type=int, default=600, help="task timeout in seconds (300-1200)")
    g.add_argument("--hook-url", default=None, help="webhook callback URL")
    g.add_argument("--out", default="./midjourney_out", help="directory to save images")
    g.add_argument("--poll-interval", type=int, default=10, help="seconds between polls")
    g.add_argument("--max-wait", type=int, default=1200, help="max seconds to wait for completion")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("submit", help="submit a job and print the task id")
    s.add_argument("--prompt", required=True)
    s.add_argument("--mode", choices=["fast", "relaxed"], default="fast")
    s.add_argument("--timeout", type=int, default=600)
    s.add_argument("--hook-url", default=None)
    s.set_defaults(func=cmd_submit)

    st = sub.add_parser("status", help="query raw status for one or more task ids")
    st.add_argument("--task-ids", nargs="+", required=True)
    st.set_defaults(func=cmd_status)

    pl = sub.add_parser("poll", help="wait for a task id and download images")
    pl.add_argument("--task-id", required=True)
    pl.add_argument("--out", default="./midjourney_out")
    pl.add_argument("--poll-interval", type=int, default=10)
    pl.add_argument("--max-wait", type=int, default=1200)
    pl.set_defaults(func=cmd_poll)

    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
