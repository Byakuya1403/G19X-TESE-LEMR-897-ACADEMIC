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
        c.headers['X-App']='1'
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
    client.headers.pop('X-App')
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


SAMPLE=Path(__file__).parents[2]/'examples/presupuesto_empresarial_2026.csv'
def financial_login(client):
    client.post('/api/auth/login',json={'username':'analista','password':'UnaClaveSegura2026'})
def import_enterprise(client,content=None,repair=True,currency='MXN'):
    return client.post('/api/financial/imports/csv',files={'file':('presupuesto.csv',content or SAMPLE.read_bytes(),'text/csv')},data={'currency':currency,'repair_shifted':str(repair).lower()})
def test_enterprise_import_repair_and_reconciliation(client):
    financial_login(client)
    assert import_enterprise(client,repair=False).status_code==422
    assert client.get('/api/financial/entries').json()==[]
    preview=client.post('/api/financial/imports/preview',files={'file':('p.csv',SAMPLE.read_bytes())},data={'repair_shifted':'true'}).json()
    assert preview['count']==36 and len(preview['warnings'])==5 and preview['pending']==10
    result=import_enterprise(client)
    assert result.status_code==201, result.text
    assert result.json()['imported']==36
    entries=client.get('/api/financial/entries').json()
    repaired=next(e for e in entries if e['source_id']=='132')
    assert repaired['period']=='2026-01' and repaired['category']=='Tecnología e Infraestructura'
    for month,income,expense in [('01',285600,189120.5),('02',285000,203110)]:
        d=client.get('/api/financial/dashboard',params={'period':'2026-'+month,'currency':'MXN'}).json()
        assert d['income']['actual']==income and d['expense']['actual']==expense
        assert d['balance']==income-expense
    march=client.get('/api/financial/dashboard?period=2026-03&currency=MXN').json()
    assert march['expense']['actual'] is None and march['balance'] is None
    assert march['prediction']['months']==2
    assert march['prediction']['reference_period']=='2026-03'
    assert march['prediction']['next_period']=='2026-04'
    jan=client.get('/api/financial/dashboard?period=2026-01&currency=MXN').json()
    assert jan['prediction']==march['prediction']
    assert march['prediction']['amount']==196115.25
    assert client.post('/api/financial/simulations',json={'period':'2026-03','currency':'MXN'}).status_code==422
    sim=client.post('/api/financial/simulations',json={'period':'2026-01','currency':'MXN'}).json()
    assert sim['baseline']==189120.5 and sim['projected']==189120.5
    assert import_enterprise(client).status_code==409
    assert len(client.get('/api/financial/entries').json())==36
    client.post('/api/auth/logout')
    guest=client.get('/api/financial/entries').json()
    assert all(e['source_id'] not in ('101','132') for e in guest)
    assert client.post('/api/financial/imports/preview',files={'file':('p.csv',SAMPLE.read_bytes())}).status_code==401

def test_enterprise_validation_is_atomic_and_role_enforced(client):
    assert import_enterprise(client).status_code==403
    financial_login(client)
    content=SAMPLE.read_bytes().replace(b'6500.0,6500.0',b'-6500.0,6500.0',1)
    assert import_enterprise(client,content=content).status_code==422
    assert client.get('/api/financial/entries').json()==[]
    assert import_enterprise(client,currency='pesos').status_code==422
    assert import_enterprise(client,currency='USD').status_code==201
    mxn=client.get('/api/financial/dashboard?period=2026-01&currency=MXN').json()
    usd=client.get('/api/financial/dashboard?period=2026-01&currency=USD').json()
    assert mxn['entries']==[] and usd['income']['actual']==285600
    assert client.post('/api/financial/simulations',json={'period':'2026-01','currency':'USD','inflation':1000}).status_code==422


def test_forecast_orders_months_and_changes_year():
    from app.financial import forecast_expenses
    from types import SimpleNamespace
    from decimal import Decimal
    rows=[SimpleNamespace(year=y,month=m,nature='expense',category='Operación',actual=Decimal(v) if v is not None else None) for y,m,v in [(2026,12,None),(2026,1,100),(2026,11,300)]]
    forecast=forecast_expenses(rows)
    assert forecast['reference_period']=='2026-12'
    assert forecast['next_period']=='2027-01'
    assert forecast['periods_available']==['2026-01','2026-11','2026-12']
    assert forecast['periods_used']==['2026-01','2026-11']
    assert forecast['amount']==200
    assert forecast_expenses(list(reversed(rows)))==forecast
    rows.append(SimpleNamespace(year=2027,month=1,nature='expense',category='Operación',actual=Decimal(500)))
    assert forecast_expenses(rows)['next_period']=='2027-02'
    assert forecast_expenses(rows)['amount']==300
    # A category filter cannot move the dataset's horizon to another month.
    assert forecast_expenses(rows,category='Sin datos')['next_period']=='2027-02'
    assert forecast_expenses(rows,category='Sin datos')['amount'] is None
    assert forecast_expenses([])['next_period'] is None
    pending=[SimpleNamespace(year=2026,month=3,nature='expense',category='Operación',actual=None)]
    assert forecast_expenses(pending)['next_period']=='2026-04'
    assert forecast_expenses(pending)['amount'] is None
