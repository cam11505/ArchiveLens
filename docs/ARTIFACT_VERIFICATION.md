# Shared artifact verification — issue #50 development subset

The shared `scripts/artifact_contract.py` validates Windows portable and macOS
app metadata without approving native execution, signing or notarization.

- Build-info schema 1: exact version/commit, channel/development marker, OS,
  architecture, artifact kind, Python/PySide/Qt versions, native backend
  name/version/architecture/hash, immutable v1.2.2 parity baseline.
- Manifest records: safe relative paths, integer sizes and SHA-256 values.
- Checksum inventory: duplicate/unsafe entries, missing/unexpected files and
  content tampering fail closed. The development DMG inventory explicitly covers
  its named DMG; its separate metadata is checked by the macOS verifier.
- SPDX 2.3/CC0 metadata: version/commit binding, approved component licenses,
  unique components, MIT application and non-FOSS UnRAR classification.
- Upstream metadata: required component coverage, versions, HTTPS source URLs,
  safe archive names and hashes. Reused QtWebEngine sources must match the exact
  distributor-controlled v1.2.1 URL/version/hash; no repeated upload is required.

Windows retains portable ZIP inventory, backend provenance, executable self-test,
installer verification and full release-set source archive/hash checks. macOS
retains bundle layout/Finder declarations, actual backend provenance, Mach-O arm64,
packaged self-test, Finder launch and independent DMG mount/install checks.
macOS retains the prepared backend hash and records the packaged hash after
PyInstaller relocation/ad-hoc signing, then re-seals the outer bundle ad-hoc.
For a signed candidate the backend signed hash is also verified separately.
Development macOS source **metadata** validation is not proof of delivery of a
complete official corresponding-source release set.

Windows/macOS/Ubuntu source tests are independent CI matrix jobs. The native
macOS development app/DMG lane also runs on main pushes after integration.
No Linux package is produced. Existing Windows build-info fields are retained;
previously published artifacts are unchanged and are not retroactively approved
under the new contract.

#49 formal Developer ID/notarization/staple/Gatekeeper evidence remains deferred.
#50 official acceptance is still open and #51 official RC/tag/release remains
blocked. Physical Mac QA remains deferred, not passed. This change does not
publish v1.3.0 or modify the v1.2.2 baseline.
