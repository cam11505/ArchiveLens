# v1.3 Issue #48 Retina, filesystem, and interaction qualification

Immutable baseline: `v1.2.2` / `bb0197b0291707287517ba8bdfc3a10ce1ad1149`.
Prerequisite main: `073a74446dd3a02cf030d2e214dd5292484c98b7` (PR #68).

## Automatic evidence

The pinned `macos-15` arm64 runner exercises production Qt, viewer, folder/PDF
providers, worker, and reading-state code. The dedicated workflow saves exact
commit/OS and JUnit evidence. PR app packaging and Windows/Ubuntu checks remain
required.

- Real offscreen Qt scale factors 1/2/3 preserve raster Actual Size: transform
  scale times device pixel ratio equals one physical pixel per raster pixel.
- Synthetic 1/2/1.5/1 display-change events preserve mode, rotation, and spread
  geometry for fit page/width/height, Actual Size, and custom zoom.
- PDF 400x300 → 800x600 → 400x300 worker requests produce the requested resolution
  rather than stale cached pixels, remain bounded and opaque white, and do not
  modify source bytes. PDF's baseline render ratio/100% policy is preserved.
- PDF thumbnails retain the 144-pixel bound.
- Synthetic trackpad begin/update/end, combined angle/pixel deltas and pixel-only
  deltas exercise the existing wheel behavior. One update changes zoom once;
  unmodified scrolling does not become page navigation or zoom.
- Unicode/nested paths, lexical aliases, resume state, deleted files, recursive
  symlink loops and direct cyclic symlink failures are covered.
- Real temporary APFS and case-sensitive APFS disk images exercise case behavior
  and folder identities. After actual detach, the source is inaccessible or an
  empty mountpoint (rejected by the reader as empty content), with no stale pages.
  These images are test fixtures, not a release packaging deliverable.

The narrow fix translates path-resolution failures into ContentAccessError and
handles source identification before resetting the reader. Cyclic links and
unsupported missing folder requests show the existing error UI rather than
escaping the UI callback or partially resetting the reader.

## Deferred physical QA

Status: **deferred by user on 2026-09-27** because no physical Mac is currently
available. The user requested continued development and future hardware validation.
A hosted runner and synthetic events cannot supply physical display/trackpad
evidence; these checks have not passed. This explicit scope decision removes the
physical-QA blocker for #48/#49 after PR #69 is merged. Official signing,
notarization, staple and exact-commit automated release gates remain mandatory.

| Check | Required evidence | Status |
| --- | --- | --- |
| Built-in Retina → external display → Retina | Mac model, macOS, resolutions/scales; raster pixel clarity, fit/Actual Size/custom zoom, current page/rotation preserved | deferred |
| PDF single/double page and thumbnails on both displays | sharpness, opaque background, no stale-size frames, bounded work | deferred |
| Existing trackpad pan/scroll/modified zoom | natural scrolling, phase/momentum behavior, one action per input, no duplicate page navigation | deferred |
| Fullscreen enter/exit on both displays | page/fit/zoom/rotation/reading state retained | deferred |
| Physical removable volume unplug/replug | safe failure and expected history/resume on reconnect | deferred |

Record artifact commit, hardware/display/volume details, steps, observed results,
and screenshots when applicable. APFS images cover filesystem detach semantics;
they do not establish physical USB disconnect behavior.

Qt's [wheel event contract](https://doc.qt.io/qt-6/qwheelevent.html) distinguishes
angle/pixel deltas and allows zero deltas at scroll begin/end. This qualification
does not add a new gesture system or configurable input.
