from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

import httpx
import keyring

from falsetech_node import Settings


def save_session(email: str, data: dict) -> bool:
    refresh = data.get('refresh_token')
    if refresh:
        keyring.set_password('FalseTech-Node', email, refresh)
        return True
    return False


def login(settings: Settings, password: str) -> tuple[bool, str]:
    response = httpx.post(
        f"{settings.supabase_url}/auth/v1/token?grant_type=password",
        headers={'apikey': settings.publishable_key, 'Content-Type': 'application/json'},
        json={'email': settings.email, 'password': password},
        timeout=30,
    )
    if response.status_code < 400:
        save_session(settings.email, response.json())
        return True, 'Signed in and stored this device session in Windows Credential Manager.'
    try:
        data = response.json()
        message = data.get('error_description') or data.get('msg') or data.get('message') or response.text
    except Exception:
        message = response.text
    return False, message[:300]


def signup(settings: Settings, password: str) -> tuple[bool, str, bool]:
    response = httpx.post(
        f"{settings.supabase_url}/auth/v1/signup",
        headers={'apikey': settings.publishable_key, 'Content-Type': 'application/json'},
        json={'email': settings.email, 'password': password, 'data': {'product': 'FalseTech Continuity'}},
        timeout=30,
    )
    if response.status_code >= 400:
        return False, response.text[:400], False
    data = response.json()
    signed_in = save_session(settings.email, data)
    if signed_in:
        return True, 'FalseTech account created and this device is signed in.', False
    return True, 'FalseTech account created. Confirm the verification email once, then run this setup again to finish device enrollment.', True


def main() -> int:
    parser = argparse.ArgumentParser(description='One-time FalseTech Continuity authentication setup')
    parser.add_argument('--config', default=r'C:\FalseTech\System\FalseTech-Node.json')
    args = parser.parse_args()
    settings = Settings(Path(args.config))
    if not settings.email:
        raise SystemExit('Email is missing from FalseTech-Node.json.')

    password = getpass.getpass(f'FalseTech password for {settings.email}: ')
    if len(password) < 8:
        print('Use a password of at least 8 characters.')
        return 2

    ok, message = login(settings, password)
    if ok:
        print(message)
        return 0

    print(f'Existing account sign-in did not succeed: {message}')
    choice = input('Create this FalseTech account now? [Y/n]: ').strip().lower()
    if choice not in {'', 'y', 'yes'}:
        return 3

    ok, message, needs_confirmation = signup(settings, password)
    print(message)
    if not ok:
        return 4
    return 10 if needs_confirmation else 0


if __name__ == '__main__':
    raise SystemExit(main())
