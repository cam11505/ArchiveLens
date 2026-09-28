# macOS arm64 development builds

On 2026-09-27 the user chose to defer Apple paid enrollment and official
signing/notarization, and continue development-build testing. This does not approve
an unsigned official v1.3 release. #49 remains open; physical Mac QA remains deferred.

## Download and identify

Open the successful `v1.3 macOS arm64 application bundle` Actions run for the exact
reviewed PR/main commit. Download the artifact named
`ArchiveLens-macos-arm64-development-dmg` and extract its ZIP wrapper.
GitHub login may be required for artifact downloads. This is CI evidence, not a
GitHub Release, and artifact retention is limited by repository/Actions settings.

The package contains:

- `ArchiveLens-<version>-macos-arm64-development.dmg`;
- `SHA256SUMS.txt` (hash of the DMG bytes, not the artifact ZIP wrapper);
- `development-manifest.json` with version, exact tested source commit, arm64,
  development channel, hash and `release_eligible=false`;
- initial and independent mounted-DMG verification reports.

The current app version remains **1.2.2** while v1.3 development is in progress;
the version is not advanced simply to label an unofficial build. Identify the
development build by its exact commit, not its version alone. For PR-triggered
runs, Actions tests a merge ref: its SHA can differ from the branch head. Use the
manifest's tested `source_commit`, and compare the merge/head trees when needed.

## Verify download integrity (Windows is sufficient)

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\ArchiveLens-1.2.2-macos-arm64-development.dmg'
Get-Content -LiteralPath '.\SHA256SUMS.txt'
```

Compare the two DMG hashes (case-insensitive). Hash equality checks download
integrity; it does not establish Developer ID trust or notarization.

## Independently verify on macOS arm64

With the matching source checkout and its pinned developer dependencies installed:

```text
python scripts/macos_release.py verify-development \
  --dmg <extracted-directory>/ArchiveLens-1.2.2-macos-arm64-development.dmg \
  --expected-commit <manifest source_commit> \
  --report outputs/development-independent-check.json
```

This requires no Apple credential. It rejects renamed official-looking files,
wrong commit/channel/architecture, missing inventory or changed bytes, then mounts
the actual DMG read-only, checks its contained app/SBOM/baseline/native architecture,
copies the app to an isolated writable directory and launches the packaged self-test
through LaunchServices. It detaches on success or validation failure. The output
report must be a new path, so old success evidence cannot be silently reused.

No installed Python is needed to run the bundled app itself; Python/dependencies
are needed only for this source-based verification command.

## Future physical testing

The DMG contains `ArchiveLens.app` and an `/Applications` install link. Use a test
Mac/environment when available; this app is unsigned/ad-hoc and not notarized.
macOS may block opening it. Do not disable Gatekeeper globally or treat a security
warning as evidence of official approval. Record any blocked launch rather than
claiming physical tests passed.

Record tested commit, Mac model/macOS, launch/install results, cold/warm Finder
archive/PDF opens, password/codec tests, Retina/external-screen/trackpad behavior,
and source immutability. Existing physical checklist:
[MACOS_RETINA_PATHS.md](MACOS_RETINA_PATHS.md).

## Development versus official gates

- Development app/DMG and source/Windows regression may continue without payment.
- Developer ID, hardened-runtime official qualification, notarization/staple and
  official Gatekeeper verification remain deferred, not passed.
- PR #70 and PR #71 are merged; #50 credential-free integration passed at
  `e03405cddd7ab338d00ed0da215b828cdc6d2fea`. Its official acceptance stays open.
- On 2026-09-28 the user authorized #51 development regression/documentation only;
  see [the regression record](V1.3_DEVELOPMENT_QA.md). It is not an official RC gate.
- #51 official RC, `v1.3.0` tag and official release remain blocked until the user
  resumes the official track and all mandatory gates pass.
