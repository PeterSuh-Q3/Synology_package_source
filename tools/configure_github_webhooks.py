#!/usr/bin/env python3
"""Idempotently register release webhooks for every repository in the feed."""

import json
import os
import subprocess
import sys

from tools.sync_releases import REPOS


OWNER = "PeterSuh-Q3"


def gh_api(path, method=None, body=None):
    command = ["gh", "api", path]
    if method:
        command.extend(["--method", method])
    if body is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(command, input=json.dumps(body) if body is not None else None,
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"gh api failed: {path}")
    return json.loads(result.stdout) if result.stdout.strip() else None


def main():
    endpoint = os.environ.get("PACKAGE_SOURCE_WEBHOOK_URL", "")
    secret = os.environ.get("PACKAGE_SOURCE_WEBHOOK_SECRET", "")
    if not endpoint or not secret:
        print("Set PACKAGE_SOURCE_WEBHOOK_URL and PACKAGE_SOURCE_WEBHOOK_SECRET.", file=sys.stderr)
        return 2
    target_config = {"url": endpoint, "content_type": "json", "secret": secret, "insecure_ssl": "0"}
    payload = {"name": "web", "active": True, "events": ["release"], "config": target_config}
    for repo in REPOS:
        path = f"repos/{OWNER}/{repo}/hooks"
        hooks = gh_api(path)
        existing = next((hook for hook in hooks if hook.get("config", {}).get("url") == endpoint), None)
        if existing:
            hook_id = existing["id"]
            gh_api(f"repos/{OWNER}/{repo}/hooks/{hook_id}", "PATCH", payload)
            print(f"updated release webhook: {OWNER}/{repo}")
        else:
            gh_api(path, "POST", payload)
            print(f"created release webhook: {OWNER}/{repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
