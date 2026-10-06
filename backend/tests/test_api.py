import os
import tempfile
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp())/"test.db")
from fastapi.testclient import TestClient
from app.main import app, Base, engine, User, LoginSession, hash_password, login_attempts
from sqlalchemy.orm import Session
import pytest
@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    login_attempts.clear()
    with TestClient(app) as c:
        with Session(engine) as db:
            for username,role in [('director','director'),('analista','analyst'),('admin','admin')]:
                db.add(User(username=username,role=role,password_hash=hash_password('UnaClaveSegura2026')))
            db.commit()
        c.headers['X-Byakuyo']='1'
        c.post('/api/auth/login',json={'username':'director','password':'UnaClaveSegura2026'})
        yield c

def item(**extra):
    return dict(department="TI",period="2026-09",amount="100.00",payroll="50.00",operating="60.00",**extra)
def test_financial_dashboard_and_simulation(client):
    assert client.post('/api/budgets',json=item()).status_code==201
    d=client.get('/api/dashboard?period=2026-09').json()
    assert d['kpis']['available']==-10
    assert d['alerts'][0]['severity']=='warning'
    s=client.post('/api/simulations',json=dict(period='2026-09',inflation=10,operating=0,payroll=20)).json()
    assert s['projected']==126
    assert client.post('/api/budgets',json=item()).status_code==409

def test_import_is_atomic_and_validated(client):
    client.post('/api/auth/login',json={'username':'analista','password':'UnaClaveSegura2026'})
    csv='department,period,amount,payroll,operating\nTI,2026-09,100,50,30\nTI,2026-09,100,50,30\n'
    assert client.post('/api/imports/csv',files={'file':('test.csv',csv,'text/csv')}).status_code==422
    assert client.get('/api/budgets').json()==[]
    csv='department,period,amount,payroll,operating\nTI,2026-09,-1,50,30\n'
    assert client.post('/api/imports/csv',files={'file':('test.csv',csv,'text/csv')}).status_code==422

def test_zero_budget_and_future_exclusion(client):
    client.post('/api/budgets',json=dict(department='TI',period='2026-09',amount=0,payroll=1,operating=0))
    client.post('/api/budgets',json=dict(department='TI',period='2026-10',amount=500,payroll=500,operating=0))
    d=client.get('/api/dashboard?period=2026-09').json()
    assert d['kpis']['utilization'] is None
    assert d['alerts'][0]['severity']=='critical'
    assert d['prediction']['amount']==1


def test_guest_never_reads_real_data(client):
    client.post('/api/budgets',json=dict(department='Confidencial',period='2026-09',amount=999,payroll=1,operating=0))
    client.post('/api/auth/logout')
    assert client.get('/api/auth/me').json() is None
    data=client.get('/api/dashboard?period=2026-09').json()
    assert data['demo'] is True
    assert all(b['department']!='Confidencial' for b in data['budgets'])
    assert all(b['department']!='Confidencial' for b in client.get('/api/budgets').json())
    assert client.post('/api/budgets',json=item()).status_code==401
    assert client.post('/api/simulations',json={'period':'2026-09'}).status_code==401

def test_role_permissions_and_session(client):
    assert client.get('/api/users').status_code==403
    client.post('/api/auth/login',json={'username':'analista','password':'UnaClaveSegura2026'})
    assert client.post('/api/budgets',json=item()).status_code==403
    assert client.get('/api/users').status_code==403
    client.post('/api/auth/login',json={'username':'admin','password':'UnaClaveSegura2026'})
    assert client.post('/api/budgets',json=item()).status_code==403
    assert client.post('/api/simulations',json={'period':'2026-09'}).status_code==403
    assert client.get('/api/users').status_code==200
    assert client.post('/api/users',json={'username':'nuevo','password':'ClaveInicial2026','role':'director'}).status_code==201
    assert client.get('/api/dashboard?period=2026-09').json()['demo'] is True
    with Session(engine) as db:
        for s in db.query(LoginSession).all(): s.expires=0
        db.commit()
    assert client.get('/api/auth/me').json() is None
    assert client.get('/api/users').status_code==401

def test_invalid_login_and_csrf(client):
    assert client.post('/api/auth/login',json={'username':'director','password':'incorrecta'}).status_code==401
    assert client.get('/api/auth/me').json()['role']=='director'
    client.headers.pop('X-Byakuyo')
    assert client.post('/api/budgets',json=item()).status_code==403
    assert client.post('/api/auth/logout').status_code==403
    assert client.post('/api/auth/login',json={'username':'director','password':'UnaClaveSegura2026'}).status_code==403


def test_user_creation_normalization_and_errors(client):
    client.post('/api/auth/login',json={'username':'admin','password':'UnaClaveSegura2026'})
    payload={'username':'  Yosh.Test  ','password':'UnaClaveNueva2026','role':'analyst'}
    response=client.post('/api/users',json=payload)
    assert response.status_code==201
    assert response.json()['username']=='yosh.test'
    assert client.post('/api/users',json=payload).status_code==409
    assert client.post('/api/users',json={**payload,'username':'otro','password':'corta'}).status_code==422
    assert client.post('/api/users',json={**payload,'username':'nombre con espacios'}).status_code==422
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login',json={'username':'YOSH.TEST','password':payload['password']}).status_code==200
