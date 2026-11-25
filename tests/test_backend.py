"""Backend / integration tests for HateShield Flask routes.

Run with:  python -m pytest tests/ -v
Uses an in-memory SQLite DB, so the real database.db is never touched.
"""
import os
import sys

os.environ['DATABASE_URL'] = 'sqlite://'   # must be set before config is imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from models import db, User, Prediction


@pytest.fixture()
def app():
    from config import Config
    Config.SQLALCHEMY_ENGINE_OPTIONS = {
        'poolclass': StaticPool, 'connect_args': {'check_same_thread': False}}
    application = create_app()
    application.config.update(TESTING=True)
    with application.app_context():
        db.drop_all()
        db.create_all()
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, username='alice', email='a@x.com', pw='secret1', confirm=None):
    return client.post('/auth/register', data={
        'username': username, 'email': email, 'password': pw,
        'confirm_password': pw if confirm is None else confirm})


def login(client, username='alice', pw='secret1'):
    return client.post('/auth/login', data={'username': username, 'password': pw})


@pytest.fixture()
def auth_client(client):
    register(client)
    login(client)
    return client


# ── Public pages ──────────────────────────────────────────────────────────────
@pytest.mark.parametrize('url', ['/home', '/about', '/auth/login', '/auth/register'])
def test_public_pages_ok(client, url):
    assert client.get(url).status_code == 200


def test_index_redirects_home(client):
    r = client.get('/')
    assert r.status_code == 302 and r.headers['Location'].endswith('/home')


@pytest.mark.parametrize('url', ['/dashboard', '/history', '/compare', '/batch',
                                 '/report/download', '/report/single/1', '/auth/logout'])
def test_protected_routes_redirect_to_login(client, url):
    r = client.get(url)
    assert r.status_code == 302 and '/auth/login' in r.headers['Location']


# ── Registration ──────────────────────────────────────────────────────────────
def test_register_success(client, app):
    r = register(client)
    assert r.status_code == 302 and '/auth/login' in r.headers['Location']
    with app.app_context():
        u = User.query.filter_by(username='alice').first()
        assert u is not None and u.password_hash != 'secret1'


def test_register_validation(client):
    assert b'do not match' in register(client, confirm='other').data
    assert b'at least 6' in register(client, pw='123').data
    assert b'required' in register(client, username='').data


def test_register_duplicates(client):
    register(client)
    assert b'Username already taken' in register(client, email='b@x.com').data
    assert b'Email already registered' in register(client, username='bob').data


# ── Login / logout ────────────────────────────────────────────────────────────
def test_login_success_and_logout(client):
    register(client)
    r = login(client)
    assert r.status_code == 302 and r.headers['Location'].endswith('/dashboard')
    assert client.get('/dashboard').status_code == 200
    assert client.get('/auth/logout').status_code == 302
    assert client.get('/dashboard').status_code == 302


def test_login_wrong_password_and_unknown_user(client):
    register(client)
    assert b'Invalid username or password' in login(client, pw='wrong').data
    assert b'Invalid username or password' in login(client, username='nobody').data


def test_login_redirects_when_already_authenticated(auth_client):
    assert auth_client.get('/auth/login').status_code == 302
    assert auth_client.get('/auth/register').status_code == 302


# ── Prediction integration ────────────────────────────────────────────────────
@pytest.mark.parametrize('model', ['lr', 'lstm', 'muril'])
def test_dashboard_predict_each_model(auth_client, app, model):
    r = auth_client.post('/dashboard', data={
        'input_text': 'You are a disgusting worthless idiot', 'model_type': model})
    assert r.status_code == 200
    with app.app_context():
        p = Prediction.query.one()
        assert p.prediction in ('HOF', 'NOT') and 0 <= p.confidence <= 1


def test_dashboard_input_validation(auth_client, app):
    assert b'enter some text' in auth_client.post('/dashboard', data={'input_text': '  '}).data
    assert b'too long' in auth_client.post('/dashboard', data={'input_text': 'a' * 2001}).data
    with app.app_context():
        assert Prediction.query.count() == 0


def test_unknown_model_type_does_not_crash(auth_client):
    r = auth_client.post('/dashboard', data={'input_text': 'hello', 'model_type': 'bogus'})
    assert r.status_code == 200


def test_hindi_input(auth_client):
    r = auth_client.post('/dashboard', data={'input_text': 'तुम बहुत बेवकूफ हो'})
    assert r.status_code == 200


def test_compare(auth_client):
    r = auth_client.post('/compare', data={'input_text': 'Have a wonderful day'})
    assert r.status_code == 200
    assert b'Logistic' in r.data or b'BiLSTM' in r.data


def test_history_and_isolation(client, app):
    register(client)
    login(client)
    client.post('/dashboard', data={'input_text': 'alice secret text'})
    assert b'alice secret text' in client.get('/history').data
    client.get('/auth/logout')
    register(client, 'bob', 'b@x.com')
    login(client, 'bob')
    assert b'alice secret text' not in client.get('/history').data
    assert client.get('/report/single/1').status_code == 404   # other user's prediction


def test_batch_textarea_and_csv(auth_client):
    r = auth_client.post('/batch', data={'paste_text': 'good day\nyou idiot', 'model_type': 'lr'})
    assert r.status_code == 200 and b'you idiot' in r.data
    import io
    csv_data = b'text\nhello friend\nshut up loser\n'
    r = auth_client.post('/batch', data={
        'csv_file': (io.BytesIO(csv_data), 't.csv'), 'model_type': 'lr'},
        content_type='multipart/form-data')
    assert r.status_code == 200 and b'shut up loser' in r.data
    assert b'No texts found' in auth_client.post('/batch', data={'paste_text': ''}).data


def test_batch_rejects_non_utf8_csv_gracefully(auth_client):
    import io
    r = auth_client.post('/batch', data={
        'csv_file': (io.BytesIO(b'\xff\xfe\x00bad'), 'bad.csv')},
        content_type='multipart/form-data')
    assert r.status_code < 500


# ── Reports ───────────────────────────────────────────────────────────────────
def test_pdf_reports(auth_client):
    auth_client.post('/dashboard', data={'input_text': 'you are trash'})
    r = auth_client.get('/report/download')
    assert r.status_code == 200 and r.mimetype == 'application/pdf' and r.data[:4] == b'%PDF'
    r = auth_client.get('/report/single/1')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
