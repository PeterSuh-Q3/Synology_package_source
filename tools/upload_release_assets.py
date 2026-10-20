#!/usr/bin/env python3
"""Upload GitHub release assets, then immediately refresh the package feed."""

import argparse
import subprocess
import sys

from tools.notify_release_assets import main as notify_main


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub repo as OWNER/NAME")
    parser.add_argument("--tag", required=True, help="Release tag")
    parser.add_argument("--clobber", action="store_true", help="replace assets with matching names")
    parser.add_argument("assets", nargs="+", help="Local asset paths to upload")
    args = parser.parse_args()
    command = ["gh", "release", "upload", args.tag, *args.assets, "--repo", args.repo]
    if args.clobber:
        command.append("--clobber")
    uploaded = subprocess.run(command)

    sys.argv = [sys.argv[0], "--repo", args.repo, "--tag", args.tag]
    for asset in args.assets:
        sys.argv.extend(["--asset", os.path.basename(asset)])
    notified = notify_main()
    return uploaded.returncode or notified


if __name__ == "__main__":
    raise SystemExit(main())
