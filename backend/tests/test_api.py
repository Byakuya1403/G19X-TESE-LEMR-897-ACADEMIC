import os
import tempfile
from pathlib import Path
os.environ["DATABASE_URL"] = "sqlite:///" + str(Path(tempfile.mkdtemp())/"test.db")
from fastapi.testclient import TestClient
from app.main import app, Base, engine
import pytest
@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as c: yield c

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
