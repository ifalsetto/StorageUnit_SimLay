from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
from pathlib import Path
from urllib.parse import quote

import httpx

from falsetech_node import FalseTechClient, LocalState, Settings, utc_now, write_report

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
SKIP_SUFFIXES = {'.db', '.sqlite', '.sqlite3', '.exe', '.msi'}
SKIP_KINDS = {'Script', 'Database', 'Installer'}


def upload_file(settings: Settings, client: FalseTechClient, state: LocalState, path: Path, digest: str) -> dict:
    artifact = client.rpc('falsetech_artifact_by_hash', {'p_content_hash': digest})
    if not artifact or not artifact.get('artifact_id'):
        return {'status': 'not_registered', 'path': str(path)}
    if artifact.get('canonical_uri'):
        return {'status': 'already_uploaded', 'path': str(path), 'uri': artifact['canonical_uri']}
    if path.suffix.lower() in SKIP_SUFFIXES or artifact.get('artifact_kind') in SKIP_KINDS:
        return {'status': 'metadata_only', 'path': str(path)}
    if not path.exists():
        return {'status': 'missing_local', 'path': str(path)}
    size = path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        return {'status': 'too_large', 'path': str(path), 'size_bytes': size}

    workspace_id = artifact['workspace_id']
    project_key = artifact.get('project_key') or 'general'
    canonical_name = artifact.get('canonical_name') or path.name
    object_key = f"{workspace_id}/{project_key}/{digest[:2]}/{digest}/{canonical_name}"
    encoded_key = '/'.join(quote(part, safe='') for part in object_key.split('/'))
    content_type = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    headers = {
        'apikey': settings.publishable_key,
        'Authorization': f"Bearer {client.access_token}",
        'Content-Type': content_type,
        'x-upsert': 'true',
    }
    with path.open('rb') as handle:
        response = httpx.post(
            f"{settings.supabase_url}/storage/v1/object/falsetech-files/{encoded_key}",
            headers=headers,
            content=handle,
            timeout=120,
        )
    if response.status_code >= 400:
        raise RuntimeError(f"storage upload failed ({response.status_code}): {response.text[:400]}")

    uri = f"storage://falsetech-files/{object_key}"
    client.rpc('falsetech_artifact_set_uri', {
        'p_device_id': client.ensure_device(),
        'p_artifact_id': artifact['artifact_id'],
        'p_canonical_uri': uri,
    })
    return {'status': 'uploaded', 'path': str(path), 'uri': uri, 'size_bytes': size}


def sync_storage(settings: Settings, state: LocalState, client: FalseTechClient, limit: int = 250) -> dict:
    client.login()
    rows = state.conn.execute(
        "SELECT path,content_hash FROM files WHERE content_hash IS NOT NULL ORDER BY last_seen_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    counts = {'uploaded': 0, 'already_uploaded': 0, 'metadata_only': 0, 'missing_local': 0, 'too_large': 0, 'not_registered': 0, 'errors': 0}
    details = []
    for row in rows:
        try:
            result = upload_file(settings, client, state, Path(row['path']), row['content_hash'])
            counts[result['status']] = counts.get(result['status'], 0) + 1
            if result['status'] not in {'already_uploaded'}:
                details.append(result)
        except Exception as exc:
            counts['errors'] += 1
            details.append({'status': 'error', 'path': row['path'], 'error': str(exc)})
    return {'counts': counts, 'details': details[:100], 'timestamp': utc_now()}


def main() -> int:
    parser = argparse.ArgumentParser(description='Upload registered FalseTech artifacts to private object storage')
    parser.add_argument('--config', default=r'C:\FalseTech\System\FalseTech-Node.json')
    parser.add_argument('--limit', type=int, default=250)
    args = parser.parse_args()

    settings = Settings(Path(args.config))
    state = LocalState(settings.db_path)
    client = FalseTechClient(settings, state)
    report = sync_storage(settings, state, client, max(1, min(args.limit, 2000)))
    report_path = write_report(settings, 'FalseTech-Storage-Sync', report)
    print(json.dumps(report, indent=2))
    print(f'Report: {report_path}')
    return 0 if report['counts']['errors'] == 0 else 2


if __name__ == '__main__':
    raise SystemExit(main())
