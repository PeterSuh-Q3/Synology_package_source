# PeterSuh-Q3 DSM package source

This repository serves a Synology Package Center feed from public GitHub SPK releases.
The SPK files stay on GitHub. The service selects the newest compatible version
by the SPK's `INFO` package ID, version, architecture, and DSM version.

## NAS deployment

Copy `app.py`, `landing.html`, `tools/`, `data/`, `Dockerfile`, and
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

The root URL without DSM parameters shows setup instructions. `/catalog.json`
lists all discovered SPK assets. The service refreshes releases every six
hours using the public GitHub API and reads new SPK metadata with HTTP Range
requests. The example `Samplepackage` is deliberately excluded from the DSM
feed. Its release remains visible in `/catalog.json`.

The initial catalog was generated from all 115 public repositories on the
PeterSuh-Q3 GitHub account on 2026-10-10. It found 134 SPK assets in nine
repositories. The refresh list is defined in `tools/sync_releases.py`.
