from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

import httpx

from falsetech_node import FalseTechClient, LocalState, Settings, utc_now, write_report


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def storage_key(uri: str) -> str:
    prefix = 'storage://falsetech-files/'
    if not uri.startswith(prefix):
        raise ValueError('unsupported storage URI')
    return uri[len(prefix):]


def safe_destination(root: Path, project_key: str | None, canonical_name: str, expected_hash: str | None) -> Path:
    project_dir = root / (project_key or 'General')
    project_dir.mkdir(parents=True, exist_ok=True)
    destination = project_dir / canonical_name
    if not destination.exists() or not expected_hash:
        return destination
    if sha256_file(destination) == expected_hash:
        return destination
    return destination.with_name(f"{destination.stem}-conflict-{expected_hash[:8]}{destination.suffix}")


def download(settings: Settings, client: FalseTechClient, artifact: dict) -> dict:
    uri = artifact.get('canonical_uri') or ''
    key = storage_key(uri)
    destination = safe_destination(
        settings.root / 'Shared',
        artifact.get('project_key'),
        artifact['canonical_name'],
        artifact.get('content_hash'),
    )
    if destination.exists() and artifact.get('content_hash') and sha256_file(destination) == artifact['content_hash']:
        return {'status': 'already_current', 'path': str(destination)}

    headers = {
        'apikey': settings.publishable_key,
        'Authorization': f"Bearer {client.access_token}",
    }
    encoded_key = '/'.join(quote(part, safe='') for part in key.split('/'))
    response = httpx.get(
        f"{settings.supabase_url}/storage/v1/object/authenticated/falsetech-files/{encoded_key}",
        headers=headers,
        timeout=120,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"storage download failed ({response.status_code}): {response.text[:300]}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_suffix(destination.suffix + '.download')
    temp.write_bytes(response.content)
    if artifact.get('content_hash') and sha256_file(temp) != artifact['content_hash']:
        temp.unlink(missing_ok=True)
        raise RuntimeError('download hash verification failed')
    temp.replace(destination)
    return {'status': 'downloaded', 'path': str(destination), 'source_device': artifact.get('source_device')}


def fetch_once(settings: Settings, state: LocalState, client: FalseTechClient, limit: int) -> dict:
    client.login()
    after = state.get('storage_fetch_after', '1970-01-01T00:00:00+00:00')
    artifacts = client.rpc('falsetech_artifacts_since', {'p_after': after, 'p_limit': limit}) or []
    counts = {'downloaded': 0, 'already_current': 0, 'errors': 0}
    details = []
    cursor = after
    for artifact in artifacts:
        try:
            result = download(settings, client, artifact)
            counts[result['status']] = counts.get(result['status'], 0) + 1
            details.append(result)
            cursor = artifact['updated_at']
            state.set('storage_fetch_after', cursor)
        except Exception as exc:
            counts['errors'] += 1
            details.append({'status': 'error', 'canonical_name': artifact.get('canonical_name'), 'error': str(exc)})
            break
    return {'counts': counts, 'details': details[:100], 'cursor': cursor, 'timestamp': utc_now()}


def main() -> int:
    parser = argparse.ArgumentParser(description='Fetch shared FalseTech files from private object storage')
    parser.add_argument('--config', default=r'C:\FalseTech\System\FalseTech-Node.json')
    parser.add_argument('--limit', type=int, default=500)
    args = parser.parse_args()

    settings = Settings(Path(args.config))
    state = LocalState(settings.db_path)
    client = FalseTechClient(settings, state)
    report = fetch_once(settings, state, client, max(1, min(args.limit, 2000)))
    report_path = write_report(settings, 'FalseTech-Storage-Fetch', report)
    print(json.dumps(report, indent=2))
    print(f'Report: {report_path}')
    return 0 if report['counts']['errors'] == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
