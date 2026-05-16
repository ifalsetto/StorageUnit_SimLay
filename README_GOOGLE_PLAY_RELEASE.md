# StorageUnit SimLay — Google Play Release Package

This is the public deploy package for StorageUnit SimLay.

## What is included

- FastAPI backend
- React/Vite frontend
- Android WebView wrapper project
- Google Play metadata drafts
- Store graphics and screenshots
- Windows release scripts
- Backend test suite
- Frontend production build path
- Strict Wix CSV exporter
- Audit JSON exporter

## Architecture

Google Play app = Android client wrapper.
Backend + frontend must be hosted over HTTPS for public users.

```text
Android app → HTTPS frontend → HTTPS FastAPI backend → SQLite/filesystem MVP storage
```

For true public multi-user production, upgrade the backend to PostgreSQL + cloud object storage + authentication/tenant isolation.

## Quick release sequence

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\VERIFY_PLAY_RELEASE_WINDOWS.ps1

.\BUILD_FRONTEND_PRODUCTION_WINDOWS.ps1 -ApiBase "https://your-backend-domain.com"

.\CREATE_ANDROID_UPLOAD_KEY_WINDOWS.ps1

.\BUILD_RELEASE_AAB_WINDOWS.ps1 -AppUrl "https://your-frontend-domain.com" -VersionName "1.0.0" -VersionCode 1
```

## Output for Play Console

```text
mobile\android\app\build\outputs\bundle\release\app-release.aab
```

## Important
Do not upload an app that points to localhost. The Play Store build must use HTTPS production URLs.
