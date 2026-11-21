"""Google account linking must never grant a new user administrator access."""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auth
import auth_security_store
import database


@pytest.fixture
def system(tmp_path, monkeypatch):
    test_pg = os.getenv('INTELLIWATCH_TEST_DATABASE_URL')
    if test_pg:
        parsed = urlparse(test_pg)
        if parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.path != '/intelliwatch_test':
            pytest.fail('PostgreSQL tests require a local intelliwatch_test database.')
        monkeypatch.setattr(database, '_USE_POSTGRES', True)
        monkeypatch.setattr(database, 'DATABASE_URL', test_pg)
        connection = database.get_connection()
        database._exec(connection, 'DROP SCHEMA public CASCADE')
        database._exec(connection, 'CREATE SCHEMA public')
        connection.commit()
        connection.close()
    else:
        monkeypatch.setattr(database, 'DATABASE_PATH', tmp_path / 'users.db')
    monkeypatch.setattr(auth_security_store, 'DATABASE_PATH', tmp_path / 'users.db')
    monkeypatch.setenv('INTELLIWATCH_SECRET_KEY', 'a' * 64)
    monkeypatch.setenv('FIREBASE_PROJECT_ID', 'test-project')
    database.initialize_database()
    auth_security_store.initialize_security_storage()
    admin_id = database.create_user('admin', 'Admin', auth.hash_password('correct-password-123'), 'ADMIN')
    operator_id = database.create_user('operator', 'Operator', auth.hash_password('correct-password-123'), 'OPERATOR')
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'test')])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .sign(key, hashes.SHA256()))
    pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self):
            import json
            return json.dumps({'test-key': pem}).encode()
    monkeypatch.setattr('urllib.request.urlopen', lambda *args, **kwargs: Response())
    def token(uid='google-admin', provider='google.com', verified=True, **claims):
        payload = {'iss': 'https://securetoken.google.com/test-project', 'aud': 'test-project',
                   'sub': uid, 'user_id': uid, 'iat': now, 'exp': now + timedelta(hours=1),
                   'email': f'{uid}@example.com', 'email_verified': verified,
                   'firebase': {'sign_in_provider': provider}}
        payload.update(claims)
        return jwt.encode(payload, key, algorithm='RS256', headers={'kid': 'test-key'})
    app = FastAPI()
    app.include_router(auth.auth_router)
    return TestClient(app), token, admin_id, operator_id


def login(client, token, role='ADMIN', **credentials):
    return client.post('/auth/firebase-login', json={'id_token': token, 'requested_role': role, **credentials})


def test_admin_link_and_subsequent_signin(system):
    client, token, admin_id, _ = system
    first = login(client, token())
    assert first.status_code == 403 and first.json()['detail']['code'] == 'ADMIN_LINK_REQUIRED'
    result = login(client, token(), admin_username='admin', admin_password='correct-password-123')
    assert result.status_code == 200
    assert result.json()['role'] == result.json()['account_role'] == 'ADMIN'
    assert result.json()['user_id'] == admin_id
    me = client.get('/auth/me', headers={'Authorization': 'Bearer ' + result.json()['access_token']})
    assert me.status_code == 200 and me.json()['role'] == 'ADMIN'
    assert login(client, token()).json()['role'] == 'ADMIN'


def test_nonadmin_and_wrong_credentials_cannot_link(system):
    client, token, _, _ = system
    assert login(client, token(), admin_username='operator', admin_password='correct-password-123').status_code == 401
    assert login(client, token(), admin_username='admin', admin_password='bad-password').status_code == 401
    assert database.get_firebase_identity_user('google-admin') is None


def test_only_verified_google_identity_can_link(system):
    client, token, _, _ = system
    for bad in (token(verified=False), token(provider='phone'), token(uid='')):
        response = login(client, bad, admin_username='admin', admin_password='correct-password-123')
        assert response.status_code in (401, 403)
    assert database.get_firebase_identity_user('google-admin') is None


def test_link_cannot_be_reassigned_and_inactive_admin_is_denied(system):
    client, token, admin_id, _ = system
    first = login(client, token(), admin_username='admin', admin_password='correct-password-123')
    assert first.status_code == 200
    assert login(client, token(uid='other-google'), admin_username='admin', admin_password='correct-password-123').status_code == 409
    conn = database.get_connection()
    database._exec(conn, 'UPDATE users SET is_active = 0 WHERE id = %s', (admin_id,))
    conn.commit(); conn.close()
    assert login(client, token()).status_code == 403
    assert client.get('/auth/me', headers={'Authorization': 'Bearer ' + first.json()['access_token']}).status_code == 401


def test_nonadmin_signin_matches_stored_role(system):
    client, token, _, _ = system
    assert login(client, token(uid='new-operator'), 'OPERATOR').json()['role'] == 'OPERATOR'
    assert login(client, token(uid='new-engineer'), 'MAINTENANCE_ENGINEER').json()['role'] == 'MAINTENANCE_ENGINEER'
    assert login(client, token(uid='new-operator'), 'MAINTENANCE_ENGINEER').status_code == 403


def test_repeated_admin_link_failures_are_rate_limited(system):
    client, token, _, _ = system
    for _ in range(5):
        assert login(client, token(), admin_username='admin', admin_password='incorrect').status_code == 401
    assert login(client, token(), admin_username='admin', admin_password='correct-password-123').status_code == 429


def test_token_must_expire_and_have_valid_signature(system):
    client, token, _, _ = system
    assert login(client, token(exp=datetime.now(timezone.utc) - timedelta(seconds=1))).status_code == 401
    assert login(client, 'invalid').status_code == 401
    payload = jwt.decode(token(), options={'verify_signature': False})
    forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(payload, forged_key, algorithm='RS256', headers={'kid': 'test-key'})
    assert login(client, forged).status_code == 401


def test_password_change_requires_relink(system):
    client, token, admin_id, _ = system
    assert login(client, token(), admin_username='admin', admin_password='correct-password-123').status_code == 200
    conn = database.get_connection()
    database._exec(conn, 'UPDATE users SET password_hash = %s WHERE id = %s',
                   (auth.hash_password('new-password-456'), admin_id))
    conn.commit(); conn.close()
    assert login(client, token()).json()['detail']['code'] == 'ADMIN_LINK_REQUIRED'
    assert login(client, token(), admin_username='admin', admin_password='new-password-456').status_code == 200


def test_security_token_storage_uses_configured_database(system):
    _, _, admin_id, _ = system
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    token_id = auth_security_store.store_token('test-invite', 'ADMIN_INVITE', expires, created_by_user_id=admin_id)
    assert token_id > 0
    assert auth_security_store.consume_token('test-invite', 'ADMIN_INVITE')['created_by_user_id'] == admin_id
    assert auth_security_store.consume_token('test-invite', 'ADMIN_INVITE') is None
