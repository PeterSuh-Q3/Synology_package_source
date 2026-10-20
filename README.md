# PeterSuh-Q3 Synology Package Source

Community package feed for Synology DSM. Register this address in Package Center to browse compatible PeterSuh-Q3 packages and receive package version updates there:

**Package source:** <https://nas.dante90.mmv.kr/>

The root URL opens a setup guide in a browser. Package Center requests the same URL with NAS model, CPU architecture, and DSM version parameters; the feed returns the newest compatible package build. SPK files are downloaded from the package publishers' public GitHub releases.

## Add the source in DSM

1. Open **Package Center**.
2. Open **Settings → Package Sources** and click **Add**.
3. Enter **PeterSuh-Q3** as the name and `https://nas.dante90.mmv.kr/` as the location.
4. Confirm, then open the **Community** page to browse packages for the NAS.

Synology's [Package Center guide](https://kb.synology.com/en-us/DSM/help/DSM/PkgManApp/configure?version=7) describes adding third-party package sources.

## Catalog and source

- [Package download counts](https://nas.dante90.mmv.kr/catalog)
- [SPK catalog data (JSON)](https://nas.dante90.mmv.kr/catalog.json)
- [Source code and deployment instructions](https://github.com/PeterSuh-Q3/Synology_package_source)

The service filters package metadata by architecture and DSM version. A package is shown only when its SPK metadata indicates compatibility. Some SPKs do not include package icons; the feed uses embedded icons when available.
Download counts are GitHub release asset totals, refreshed by a six-hour fallback sync and release webhooks. They count downloads per SPK file, not unique users or completed installations. The NVIDIA package-ID allowlist keeps retired package IDs out of the feed while newer versions of approved IDs are discovered automatically. For assets added to an already-published release, the upload process calls the signed refresh callback because GitHub has no dedicated asset-upload webhook event.

## Run the feed

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Synology NAS Docker and reverse proxy setup, webhook configuration, and the post-upload callback needed when adding assets to an already-published GitHub release. The service is a small Python HTTP server with no third-party Python dependencies.
