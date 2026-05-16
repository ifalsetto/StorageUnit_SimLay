# Google Play Data Safety Draft — StorageUnit SimLay

Use this as a starting point. Confirm final answers against your deployed backend and business policy before submitting.

## Data types likely collected
- Photos and videos: user-provided storage-unit media
- Files and docs: generated CSV/audit exports and uploaded screenshots
- App activity: inventory entries, evidence records, export actions
- Diagnostics: crash/error logs if enabled by hosting provider

## Purpose
- App functionality
- Analytics/diagnostics only if you add analytics
- Fraud/security/debugging only if you enable related logging

## Data sharing
- Do not mark data as sold.
- Mark service-provider processing only for backend hosting, AI vision provider, file storage, and optional market connectors.

## Encryption
- Use HTTPS in production.
- Do not configure Android release builds to use HTTP.

## Deletion
Before public release, implement and document a user deletion path for uploaded media, inventory records, and exports.
