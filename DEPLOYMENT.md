# PeterSuh-Q3 DSM package source

This repository serves a Synology Package Center feed from public GitHub SPK releases.
The SPK files stay on GitHub. The service selects the newest compatible version
by the SPK's `INFO` package ID, version, architecture, and DSM version.

## NAS deployment

Copy `app.py`, `landing.html`, `catalog.html`, `tools/`, `data/`, `Dockerfile`, and
`compose.yaml` to a shared folder on the NAS. In that directory run
`docker compose up -d --build`.
The container listens on the NAS loopback interface at port 8765. Its health
endpoint is `http://127.0.0.1:8765/health`. The Compose file also maps port
8766 to loopback for local feed checks; neither port is exposed directly to
the Internet.

Set a DSM reverse proxy source of `https://nas.dante90.mmv.kr:443` and a
destination of `http://127.0.0.1:8765`. Assign a certificate valid for
`nas.dante90.mmv.kr`, and make port 443 reachable from the Internet.

The feed endpoint is `/` with DSM query parameters, for example:

`/?arch=epyc7002&major=7&minor=4&build=72806&language=enu`

The root URL without DSM parameters shows setup instructions. `/catalog`
lists SPK assets with their GitHub download counts; `/catalog.json` provides
the same catalog as JSON. The service refreshes releases and asset download
counts every six hours using the public GitHub API and reads new SPK metadata
with HTTP Range requests. NVIDIA package IDs are allowlisted, but their versions
are discovered automatically from SPK metadata so a newer release revision is
not blocked by a stale version pin. Counts are per GitHub release asset, not
unique users or completed installations. The example `Samplepackage` is
deliberately excluded from the DSM feed. Its release remains visible in the catalog.

## Release refresh triggers

The six-hour refresh remains the recovery/fallback path. An authenticated
`POST /webhook/github` endpoint can also queue a refresh immediately. The
endpoint verifies GitHub's `X-Hub-Signature-256` HMAC, limits the payload to
64 KiB, and accepts only repositories in the feed's tracked repository list.
The worker coalesces bursts so concurrent release events do not start parallel
GitHub scans.

GitHub does not provide a dedicated webhook event for adding or replacing an
asset on an already-published release. Configure a GitHub webhook on each
tracked repository for the `release` event to cover release publication/edit
events. For asset uploads, use the wrapper below: it runs `gh release upload`
and calls the signed refresh callback as soon as the upload succeeds.

```sh
export PACKAGE_SOURCE_WEBHOOK_URL=https://nas.dante90.mmv.kr/webhook/github
export PACKAGE_SOURCE_WEBHOOK_SECRET='<same secret configured on the NAS>'
python3 -m tools.upload_release_assets \
  --repo PeterSuh-Q3/syno_nvidia_driver \
  --tag nvidia \
  /path/to/syno-nvidia-driver-kver5-595-proprietary-595.99.02-4.spk
```

To install the webhook receiver on the NAS, create a random secret locally and
put it in the deployment directory's `.env` file as
`GITHUB_WEBHOOK_SECRET=<random-secret>` (keep that file untracked and private).
Recreate the container with `docker compose up -d --build`. Then, from an
authorized GitHub CLI session, set `PACKAGE_SOURCE_WEBHOOK_URL` and
`PACKAGE_SOURCE_WEBHOOK_SECRET` to the same values and run
`python3 -m tools.configure_github_webhooks`. This creates or updates the
`release` webhook for each repository in `tools/sync_releases.py`; it is safe
to run again. For assets uploaded through GitHub's web UI or another tool, run
`python3 tools/notify_release_assets.py --repo OWNER/REPO --tag TAG` afterward.
The callback returns HTTP 202 when a refresh has been queued.

The initial catalog was generated from all 115 public repositories on the
PeterSuh-Q3 GitHub account on 2026-10-10. It found 134 SPK assets in nine
repositories. The refresh list is defined in `tools/sync_releases.py`.
