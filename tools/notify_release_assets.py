#!/usr/bin/env python3
"""Notify the package feed immediately after uploading release assets.

Required environment variables:
  PACKAGE_SOURCE_WEBHOOK_URL
  PACKAGE_SOURCE_WEBHOOK_SECRET

Example:
  PACKAGE_SOURCE_WEBHOOK_URL=https://nas.example/webhook/github \
  PACKAGE_SOURCE_WEBHOOK_SECRET='...' \
  python3 tools/notify_release_assets.py --repo PeterSuh-Q3/syno_nvidia_driver \
      --tag nvidia --asset syno-nvidia-driver-kver5-595-proprietary-595.99.02-4.spk
"""

import argparse
import hashlib
import hmac
import json
import os
import subprocess
import sys
from datetime import datetime, timezone


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repo as OWNER/NAME")
    parser.add_argument("--tag", required=True, help="Release tag whose assets changed")
    parser.add_argument("--asset", action="append", default=[], help="Uploaded asset name (repeatable)")
    args = parser.parse_args()

    endpoint = os.environ.get("PACKAGE_SOURCE_WEBHOOK_URL", "")
    secret = os.environ.get("PACKAGE_SOURCE_WEBHOOK_SECRET", "")
    if not endpoint or not secret:
        parser.error("PACKAGE_SOURCE_WEBHOOK_URL and PACKAGE_SOURCE_WEBHOOK_SECRET are required")
    if "/" not in args.repo or not args.repo.startswith("PeterSuh-Q3/"):
        parser.error("--repo must be a tracked PeterSuh-Q3/OWNER repository")

    body = json.dumps({
        "action": "assets_uploaded",
        "repository": {"full_name": args.repo},
        "release": {"tag_name": args.tag},
        "asset_names": args.asset,
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    command = [
        "curl", "--silent", "--show-error", "--max-time", "20", "--request", "POST",
        "--header", "Content-Type: application/json",
        "--header", "X-GitHub-Event: release_asset_upload",
        "--header", f"X-Hub-Signature-256: sha256={signature}",
        "--header", "User-Agent: petersuh-package-source-release-notifier",
        "--data-binary", "@-", "--write-out", "\n%{http_code}", endpoint,
    ]
    result = subprocess.run(command, input=body, capture_output=True)
    if result.returncode:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        print(f"package-source webhook failed: {error}", file=sys.stderr)
        return 1
    lines = result.stdout.decode("utf-8", errors="replace").rstrip().splitlines()
    status = lines[-1] if lines else ""
    response_body = "\n".join(lines[:-1])
    print(f"package-source webhook: HTTP {status}: {response_body}")
    return 0 if status == "202" else 1


if __name__ == "__main__":
    raise SystemExit(main())
