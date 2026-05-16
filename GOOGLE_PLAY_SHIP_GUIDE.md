# StorageUnit SimLay — Google Play Ship Guide

## Release status
This package is structured for Google Play release as a hosted web + mobile wrapper system:

- Backend: FastAPI service deployed to a HTTPS cloud host.
- Frontend: React/Vite app deployed to a HTTPS static host.
- Android: native WebView shell that loads the deployed frontend and supports camera/photo/video upload.

The Android project targets API 35 for Google Play submission. Build output for Play must be an Android App Bundle: `app-release.aab`.

## Required before uploading to Google Play
1. Deploy backend to HTTPS.
2. Deploy frontend to HTTPS with `VITE_API_BASE=https://your-backend-domain.com`.
3. Confirm the hosted frontend can create a run, upload photos, add evidence, and export CSV.
4. Create a Google Play developer account.
5. Create upload signing key.
6. Build release AAB with your production frontend URL.
7. Complete Play Console app content forms: privacy policy, data safety, permissions, target audience, content rating.

## Windows release commands
From the project root:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\VERIFY_PLAY_RELEASE_WINDOWS.ps1

.\CREATE_ANDROID_UPLOAD_KEY_WINDOWS.ps1

.\BUILD_RELEASE_AAB_WINDOWS.ps1 -AppUrl "https://your-frontend-domain.com" -VersionName "1.0.0" -VersionCode 1
```

Upload this file to Play Console:

```text
mobile\android\app\build\outputs\bundle\release\app-release.aab
```

## Production API requirements
Set these environment variables on your backend host:

```text
OPENAI_API_KEY=your_openai_key
SIMLAY_CORS_ORIGINS=https://your-frontend-domain.com
```

For public launch, do not ship OpenAI keys inside the Android app or frontend. Keep API keys server-side only.

## Store listing package
Use files in:

```text
store-listing/
privacy/
```

Included:

- App icon 1024x1024
- Feature graphic 1024x500
- Phone screenshots
- Short description
- Full description
- Privacy policy draft
- Data safety draft
- Permission rationale

## Final Play Console checks
- Package name: `com.falsetech.simlay`
- App name: `StorageUnit SimLay`
- Version: `1.0.0`
- Target SDK: `35`
- Upload type: Android App Bundle (`.aab`)
- Permissions used:
  - Internet
  - Camera
  - Photo/video media read access
- Data handled:
  - User-uploaded photos/videos
  - Inventory item notes
  - Evidence URLs/screenshots
  - Generated CSV/audit files

## Known release gate
This package cannot produce a real Play-ready AAB until the production frontend URL is configured and the build is signed using your upload key. That is intentional: Play Store releases must point to your actual deployed service, not localhost.
