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

- [SPK asset catalog](https://nas.dante90.mmv.kr/catalog.json)
- [Source code and deployment instructions](https://github.com/PeterSuh-Q3/Synology_package_source)

The service filters package metadata by architecture and DSM version. A package is shown only when its SPK metadata indicates compatibility. Some SPKs do not include package icons; the feed uses embedded icons when available.

## Run the feed

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Synology NAS Docker and reverse proxy setup. The service is a small Python HTTP server with no third-party Python dependencies.
