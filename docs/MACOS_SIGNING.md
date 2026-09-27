# macOS official signing and DMG gate (#49)

Baseline: `v1.2.2` / `bb0197b0291707287517ba8bdfc3a10ce1ad1149`.
Prerequisites #46–#48 are complete; PR #69 merged at
`061a3d830b1231ded9a4da27e10f07ab24acb380`. Physical Mac QA remains explicitly
**deferred** by the user, not passed.

## Status and limits

The credential-free development path and official fail-closed implementation are
separate. #49 is **not complete** until a real Developer ID candidate passes all
signing/notarization/staple/Gatekeeper/loadability checks. As of 2026-09-27 the user
is unsure whether paid Apple Developer membership and a Developer ID Application
certificate exist. Repository-level GitHub secrets were empty; this does not
establish the state of organization/environment secrets or the user's Apple account.

No v1.3 tag or GitHub Release is created by this workflow. #50 common release-set
integration and #51 final exact-commit RC remain later gates.

## Development path (no Apple credentials)

Build and verify with `build_macos_app.py --development` and
`verify_macos_app.py --allow-development --run`, as documented in MACOS_PACKAGING.md.
The existing macOS app CI additionally runs:

```text
python scripts/macos_release.py development-dmg \
  --expected-commit <exact commit> \
  --report outputs/macos-dmg-development/report.json
```

The probe creates `ArchiveLens-development-not-for-release.dmg` under `outputs`,
not the official artifact directory. It verifies the read-only image, fixed top-level
contents (`ArchiveLens.app`, `/Applications` install symlink), exact app metadata,
native arm64 binaries, and a ditto-copy/LaunchServices packaged self-test outside the
checkout. The image is detached on success or validation failure. Only JSON evidence
is uploaded, not this unsigned/ad-hoc DMG.

DMG contents are deterministic in layout. Byte-for-byte reproducibility of HFS+
images, notarization tickets, signatures and timestamps is **not** claimed.

## External setup (owner action, never paste secrets in chat)

Confirm active Apple Developer membership, then obtain a Developer ID Application
certificate with its private key. Export a password-protected PKCS#12 file. Prepare
an Apple ID with an app-specific password and matching Team ID. The workflow uses
`notarytool` keychain profiles, not deprecated `altool`.

Create a protected GitHub environment named `macos-release`, restrict deployment
to reviewed `main`, and configure required reviewers. This protection is an owner
configuration step; a YAML environment name alone does not establish approval rules.
Store these secrets there (never in source, issues, reports or screenshots):

- `MACOS_CERTIFICATE_P12_BASE64`: base64 PKCS#12 certificate and private key;
- `MACOS_CERTIFICATE_PASSWORD`: export password;
- `MACOS_SIGNING_IDENTITY`: exact `Developer ID Application: … (TEAMID)` identity;
- `APPLE_TEAM_ID`: matching 10-character team identifier;
- `APPLE_ID`: notarization account;
- `APPLE_APP_SPECIFIC_PASSWORD`: app-specific password, not the account password.

Do not dispatch the official candidate workflow until the owner confirms account,
certificate and environment setup. The Python entry point and workflow preflight
both reject missing credentials; there is no unsigned fallback or success-only stub.

## Official candidate flow

Manually dispatch `macOS official candidate (credentials required)` from main with
`expected_commit` equal to the exact reviewed main SHA. The job uses read-only
repository permission and does not publish or tag.

1. Reject a different/dirty checkout and missing/mismatched credentials.
2. Audit dependencies, stage exact backend/licenses, generate bundled SPDX SBOM.
3. Create a temporary keychain, import the certificate, validate the requested
   signing identity and notarization credentials. Restore the original search list
   and delete the keychain/private file at teardown, including failure paths.
4. Build an official candidate with `channel=release`, `development=false`.
5. Sign nested Mach-O files/framework bundles inside-out with Developer ID,
   hardened runtime and secure timestamp. `--deep` is used only to verify, not sign.
6. Check all native signatures, Team ID, authority, timestamp and entitlements,
   then run the packaged self-test without credential environment variables.
7. Submit an app ZIP with `notarytool --wait`; require `Accepted`. Staple and validate
   the app, then assess execution using `spctl`.
8. Create/sign `ArchiveLens-<version>-macos-arm64.dmg`, notarize it separately,
   require `Accepted`, staple and validate it, and assess its primary signature.
9. Mount the actual final image read-only, revalidate the contained signed/stapled
   app and run the copied app self-test. Detach and calculate the final SHA-256.
10. Only after every gate succeeds, upload the candidate DMG and redacted report.

An independent official verifier is available on macOS arm64:

```text
python scripts/macos_release.py verify \
  --dmg ArchiveLens-<version>-macos-arm64.dmg \
  --team-id <expected team> --expected-commit <exact commit> \
  --report outputs/macos-official/independent-verification.json
```

The structure-only #46 CLI refuses official verification; it cannot accidentally
approve an unsigned app based on metadata alone.

## Entitlements and secret handling

The reviewed initial entitlement set is empty: no JIT, unsigned executable memory,
DYLD environment, library-validation bypass, debugging or sandbox exception.
ArchiveLens does not ship QtQml/QtQuick/QtWebEngine; all bundled native code is
re-signed by the same team. This is a **candidate policy**, not proof of signed
runtime compatibility. In particular, exercise UnRAR callbacks, codecs and PDF
under the real hardened runtime. A measured loadability failure requires a narrow
reviewed change and renewed tests, never automatically disabling a protection.

Credential-bearing tool arguments and stdout/stderr are captured, not printed or
persisted. Failure messages contain only fixed stage names. Only request IDs,
source commit, artifact name/hash and non-sensitive test result fields enter the
final report. Apple notarization logs are deliberately not uploaded automatically.
System tools necessarily receive secrets locally; this is intended for a dedicated
ephemeral hosted runner, not a shared untrusted machine. Force-cancel may bypass
Python teardown; ephemeral runner destruction is the final cleanup boundary.

## Remaining evidence before closing #49

- Exact-commit credential-free CI, mounted DMG content/copy/launch checks.
- Real Developer ID nested-code/hardened-runtime and packaged backend self-test.
- Apple `Accepted` requests for app and DMG, validated staples, `spctl` assessments.
- Downloaded final DMG hash and independent verification from the same source SHA.
- Owner-confirmed protected environment; no secret exposure in logs/artifacts.

References: [Apple notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
[Apple notarization requirements](https://developer.apple.com/documentation/security/resolving-common-notarization-issues),
[Apple library validation](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation).
