# CarLink RU v6 — TEYES TPRO 2

**Status: DEVELOPMENT / NOT INSTALLABLE.** This repository does not yet contain a
verified combined CarPlay + AirPlay APK.

Target: Android 10 (API 29), UIS7862, 768×1024; one APK, Russian UI,
wireless CarPlay and real AirPlay receiver switchable within the app.

## Source projects

- [F-e-n-y-x/CarLink](https://github.com/F-e-n-y-x/CarLink) (AGPL-3.0)
- [F-e-n-y-x/airplay-dlna-receiver](https://github.com/F-e-n-y-x/airplay-dlna-receiver) (GPL-3.0)

Do not distribute a binary without corresponding complete source and license texts.

## Integration blockers (not optional)

1. Convert the AirPlay **application** into an Android library and migrate its
   Hilt application/manifest declarations to the CarLink host application.
2. Integrate the AirPlay foreground service, JNI/UxPlay code, codec rendering,
   mDNS discovery, and embedded AirPlay screen in the CarLink navigation UI.
3. Implement explicit resource ownership: stop CarPlay session before activating
   AirPlay; stop AirPlay before starting wireless CarPlay. Verify Wi-Fi routes and mDNS.
4. Localized Russian UI for both modes, including error messages, at 768×1024.
5. CarLink upstream excludes CarPlay accessory authentication assets from source.
   Without a properly authorized identity, source builds cannot authenticate CarPlay.
   Do not commit private keys or circumvent device authentication.
6. CI checks: build, manifest, native ABIs, instrumentation/device verification.
   **A successful Gradle build alone is not evidence that AirPlay works.**

## CI

The `Source audit` workflow fetches both upstream source trees and creates a
reproducible report of their build prerequisites and integration blockers.
It intentionally does **not** create or label a merged APK. The workflow is a
starting checkpoint, not the requested finished application.

## Definition of done

Release `CarLink-RU-v6.apk` only after:
- One Android package, with actual AirPlay JNI library and receiver service,
  correctly registered in the merged manifest
- CarPlay authenticated with authorized accessory identity and tested over Wi-Fi
- iPhone Screen Mirroring detected by mDNS and played with video and audio
- Switch in both directions without app crash or stale network service
- Test executed on actual TEYES TPRO 2 Android 10 (UIS7862)
- Artifact checked with `apksigner`, `aapt`, and `unzip`, with SHA-256 recorded

No successful claims before these tests.
