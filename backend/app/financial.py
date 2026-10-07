"""Importación de partidas anuales con contrato explícito; no importador universal."""
import csv
import hashlib
import io
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime
from fastapi import Form, File, UploadFile, HTTPException
from sqlalchemy import Integer, String, Numeric, JSON, ForeignKey, CheckConstraint, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError

MONTHS = {name.lower():i+1 for i,name in enumerate(['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])}
COLUMNS = {'ID_Registro','Anio','Mes','Categoria','Subcategoria','Concepto','Presupuesto_Estimado','Gasto_Real','Diferencia_Varianza','Porcentaje_Ejecucion','Estado'}
def money(value):
    try: result=Decimal(value.strip())
    except (InvalidOperation,AttributeError): raise ValueError('Importe no válido; usa punto decimal sin separadores de miles')
    if not result.is_finite() or result<0 or result>Decimal('99999999999999.99') or result!=result.quantize(Decimal('.01')):
        raise ValueError('Importe fuera de rango o con más de dos decimales')
    return result

def parse_file(content, repair=False):
    try: text=content.decode('utf-8-sig')
    except UnicodeError: raise ValueError('El CSV debe estar codificado en UTF-8')
    reader=csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or len(reader.fieldnames)!=len(COLUMNS) or set(reader.fieldnames)!=COLUMNS:
        raise ValueError('Columnas esperadas: '+', '.join(sorted(COLUMNS)))
    parsed=[]; warnings=[]; keys=set()
    for line,row in enumerate(reader,2):
        if line>10001: raise ValueError('Máximo 10000 partidas')
        raw=dict(row)
        try:
            if None in row or any(v is None for v in row.values()): raise ValueError('Cantidad de columnas incorrecta')
            row={k:v.strip() for k,v in row.items()}
            if row['Mes'].lower() not in MONTHS and row['Concepto'].lower() in MONTHS:
                if not repair: raise ValueError('Columnas de texto desplazadas. Confirma su reparación en la pantalla de importación')
                row['Mes'],row['Categoria'],row['Subcategoria'],row['Concepto']=row['Concepto'],row['Mes'],row['Categoria'],row['Subcategoria']
                warnings.append(f"Fila {line}, ID {row['ID_Registro']}: se reordenaron mes, categoría, subcategoría y concepto")
            month=MONTHS.get(row['Mes'].lower())
            if not month: raise ValueError('Mes desconocido')
            year=int(row['Anio'])
            if not 1900<=year<=9999: raise ValueError('Año fuera de rango')
            for key,limit in [('ID_Registro',100),('Categoria',150),('Subcategoria',150),('Concepto',300)]:
                if not row[key] or len(row[key])>limit: raise ValueError(f'{key}: longitud incorrecta')
            state=row['Estado'].lower()
            if state not in ('pendiente','completado'): raise ValueError('Estado debe ser Pendiente o Completado')
            budget=money(row['Presupuesto_Estimado']);actual=money(row['Gasto_Real'])
            if state=='pendiente' and actual!=0: raise ValueError('Una partida pendiente con resultado no cero necesita revisión')
            try:
                variance=Decimal(row['Diferencia_Varianza'])
                execution=Decimal(row['Porcentaje_Ejecucion'].removesuffix('%'))
            except InvalidOperation: raise ValueError('Varianza o porcentaje inválido')
            if not variance.is_finite() or not execution.is_finite(): raise ValueError('Varianza o porcentaje no finito')
            if variance!=budget-actual: raise ValueError('La varianza no coincide con presupuesto menos resultado')
            if budget and abs(execution-actual*100/budget)>Decimal('.015'): raise ValueError('El porcentaje no coincide con los importes')
            key=(year,row['ID_Registro'])
            if key in keys: raise ValueError('ID/año duplicado dentro del archivo')
            keys.add(key)
            parsed.append(dict(source_id=row['ID_Registro'],year=year,month=month,category=row['Categoria'],subcategory=row['Subcategoria'],concept=row['Concepto'],nature='income' if row['Categoria'].lower()=='ingresos' else 'expense',budget=budget,actual=actual if state=='completado' else None,status=state,original=raw))
        except (ValueError,InvalidOperation) as e: raise ValueError(f'Fila {line}: {e}')
    if not parsed: raise ValueError('El archivo no contiene partidas')
    return parsed,warnings

def forecast_expenses(records, category=None):
    # Numeric tuples, not CSV position or alphabetic month names.
    periods=sorted({(r.year,r.month) for r in records})
    latest=periods[-1] if periods else None
    target=None
    if latest and latest!=(9999,12):
        year,month=latest
        target=(year+1,1) if month==12 else (year,month+1)
    monthly={}
    for r in records:
        if r.nature=='expense' and (not category or r.category==category):
            monthly.setdefault((r.year,r.month),[]).append(r)
    completed=[(p,sum((r.actual for r in group),Decimal(0))) for p,group in sorted(monthly.items()) if all(r.actual is not None for r in group)][-3:]
    def label(period):return f'{period[0]:04}-{period[1]:02}' if period else None
    return dict(amount=float((sum((amount for _,amount in completed),Decimal(0))/len(completed)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)) if completed and target else None,
                months=len(completed),reference_period=label(latest),next_period=label(target),
                periods_used=[label(p) for p,_ in completed],periods_available=[label(p) for p in periods],
                method='Proyección estadística: media de hasta 3 meses de egresos completados, ordenados por año y mes. Los meses pendientes se excluyen; cobertura mensual variable. No es IA validada.')

def install_financial(app, Base, engine, DB, CurrentUser, Analyst, Financial):
    class ImportBatch(Base):
        __tablename__='financial_imports'
        id: Mapped[int]=mapped_column(primary_key=True)
        sha256: Mapped[str]=mapped_column(String(64),unique=True)
        filename: Mapped[str]=mapped_column(String(255))
        currency: Mapped[str]=mapped_column(String(3))
        username: Mapped[str]=mapped_column(String(100))
        warnings: Mapped[list]=mapped_column(JSON)
    class Entry(Base):
        __tablename__='financial_entries'
        __table_args__=(UniqueConstraint('year','source_id','currency'),
            CheckConstraint('month BETWEEN 1 AND 12'),CheckConstraint('year BETWEEN 1900 AND 9999'),
            CheckConstraint('budget >= 0'),CheckConstraint('actual IS NULL OR actual >= 0'),
            CheckConstraint("nature IN ('income','expense')"),
            CheckConstraint("(status='pendiente' AND actual IS NULL) OR (status='completado' AND actual IS NOT NULL)"))
        id: Mapped[int]=mapped_column(primary_key=True)
        batch_id: Mapped[int]=mapped_column(ForeignKey("financial_imports.id"))
        source_id: Mapped[str]=mapped_column(String(100))
        year: Mapped[int]=mapped_column(Integer)
        month: Mapped[int]=mapped_column(Integer)
        category: Mapped[str]=mapped_column(String(150))
        subcategory: Mapped[str]=mapped_column(String(150))
        concept: Mapped[str]=mapped_column(String(300))
        nature: Mapped[str]=mapped_column(String(10))
        currency: Mapped[str]=mapped_column(String(3))
        budget: Mapped[Decimal]=mapped_column(Numeric(16,2))
        actual: Mapped[Decimal|None]=mapped_column(Numeric(16,2),nullable=True)
        status: Mapped[str]=mapped_column(String(15))
        original: Mapped[dict]=mapped_column(JSON)
    def select_entries(db,user):
        if user and user.role in ('director','analyst'): return db.scalars(select(Entry).order_by(Entry.year,Entry.month,Entry.id)).all()
        # Deliberately synthetic guest records, never read the financial DB for guests.
        return [Entry(id=i,source_id=str(i),year=2026,month=1,category=c,subcategory='Demostración',concept='Datos de ejemplo',nature=n,currency='MXN',budget=Decimal(b),actual=Decimal(a),status='completado') for i,c,n,b,a in [(1,'Ingresos','income',280000,285600),(2,'Gastos Operativos','expense',158000,158490),(3,'Tecnología','expense',10000,10000)]]
    def serialize(r):
        return dict(id=r.id,source_id=r.source_id,period=f'{r.year:04}-{r.month:02}',category=r.category,subcategory=r.subcategory,concept=r.concept,nature=r.nature,currency=r.currency,budget=float(r.budget),actual=float(r.actual) if r.actual is not None else None,status=r.status,variance=float(r.budget-r.actual) if r.actual is not None else None,execution=float(r.actual*100/r.budget) if r.budget and r.actual is not None else None)
    async def read_file(file):
        content=await file.read(2*1024*1024+1)
        if len(content)>2*1024*1024: raise HTTPException(413,'Máximo 2 MB')
        return content
    def parse_or_error(content,repair):
        try:return parse_file(content,repair)
        except ValueError as e:raise HTTPException(422,str(e))
    @app.post('/api/financial/imports/preview')
    async def preview(user: Analyst,file: UploadFile=File(...),repair_shifted:bool=Form(False)):
        parsed,warnings=parse_or_error(await read_file(file),repair_shifted)
        return dict(count=len(parsed),warnings=warnings,sample=[dict(source_id=r['source_id'],period=f"{r['year']:04}-{r['month']:02}",category=r['category'],concept=r['concept'],status=r['status']) for r in parsed[:5]],pending=sum(r['actual'] is None for r in parsed))
    @app.post('/api/financial/imports/csv',status_code=201)
    async def import_csv(db: DB,user: Analyst,file:UploadFile=File(...),currency:str=Form(...),repair_shifted:bool=Form(False)):
        currency=currency.strip().upper()
        if not re.fullmatch('[A-Z]{3}',currency):raise HTTPException(422,'Indica el código de moneda de tres letras, por ejemplo MXN')
        content=await read_file(file);parsed,warnings=parse_or_error(content,repair_shifted)
        digest=hashlib.sha256(content).hexdigest()
        if db.scalar(select(ImportBatch).where(ImportBatch.sha256==digest)):raise HTTPException(409,'Este archivo ya fue importado')
        keys={(r.year,r.source_id,r.currency) for r in db.scalars(select(Entry)).all()}
        if any((r['year'],r['source_id'],currency) in keys for r in parsed):raise HTTPException(409,'Ya existen partidas con el mismo ID, año y moneda; no se importó ninguna fila')
        try:
            batch=ImportBatch(sha256=digest,filename=(file.filename or 'archivo.csv')[:255],currency=currency,username=user.username,warnings=warnings)
            db.add(batch);db.flush()
            db.add_all([Entry(batch_id=batch.id,currency=currency,**r) for r in parsed]);db.commit()
        except IntegrityError:
            db.rollback();raise HTTPException(409,'Conflicto con otra importación; no se guardaron filas parciales')
        periods=sorted({f"{r['year']:04}-{r['month']:02}" for r in parsed})
        return dict(imported=len(parsed),warnings=warnings,periods=periods,currency=currency)
    @app.get('/api/financial/entries')
    def entries(db: DB,user: CurrentUser):return [serialize(r) for r in select_entries(db,user)]
    @app.get('/api/financial/dashboard')
    def dashboard(db: DB,user: CurrentUser,period:str,currency:str='MXN',category:str|None=None):
        try:dt=datetime.strptime(period,'%Y-%m')
        except ValueError:raise HTTPException(422,'Periodo YYYY-MM requerido')
        currency_history=[r for r in select_entries(db,user) if r.currency==currency]
        history=[r for r in currency_history if not category or r.category==category]
        selected=[r for r in history if r.year==dt.year and r.month==dt.month]
        def totals(nature):
            items=[r for r in selected if r.nature==nature];pending=sum(r.actual is None for r in items)
            return dict(budget=float(sum((r.budget for r in items),Decimal(0))),actual=float(sum((r.actual for r in items),Decimal(0))) if items and not pending else None,known=float(sum((r.actual for r in items if r.actual is not None),Decimal(0))),pending=pending)
        income=totals('income');expense=totals('expense');alerts=[]
        for r in selected:
            if r.actual is None:continue
            unfavorable=r.actual<r.budget if r.nature=='income' else r.actual>r.budget
            if unfavorable:alerts.append(dict(department=r.concept,severity='warning',message='Ingreso por debajo del presupuesto' if r.nature=='income' else 'Gasto sobre presupuesto',deviation=float(r.actual-r.budget)))
        prediction=forecast_expenses(currency_history,category)
        return dict(demo=not(user and user.role in ('director','analyst')),currency=currency,income=income,expense=expense,balance=income['actual']-expense['actual'] if income['actual'] is not None and expense['actual'] is not None else None,entries=[serialize(r) for r in selected],alerts=alerts,prediction=prediction)
    @app.post('/api/financial/simulations')
    def simulate(db: DB,user: Financial,data:dict):
        try:
            period=str(data['period']);currency=str(data['currency']);category=data.get('department')
            rates={k:Decimal(str(data.get(k,0))) for k in ('payroll','operating','inflation')}
            limits={'payroll':(-30,30),'operating':(-50,50),'inflation':(-10,30)}
            for k,v in rates.items():
                if not v.is_finite() or not limits[k][0]<=v<=limits[k][1]:raise ValueError('Porcentaje fuera de rango')
        except (KeyError,ValueError,InvalidOperation):raise HTTPException(422,'Parámetros de simulación inválidos')
        selected=[r for r in select_entries(db,user) if f'{r.year:04}-{r.month:02}'==period and r.currency==currency and r.nature=='expense' and (not category or r.category==category)]
        if not selected:raise HTTPException(404,'No hay egresos para ese periodo y moneda')
        if any(r.actual is None for r in selected):raise HTTPException(422,'El periodo tiene egresos pendientes; no se simulan como gasto cero')
        payroll=sum((r.actual for r in selected if r.subcategory.lower()=='nómina'),Decimal(0));operating=sum((r.actual for r in selected if r.subcategory.lower()!='nómina'),Decimal(0))
        projected=payroll*(1+rates['payroll']/100)+operating*(1+rates['operating']/100)*(1+rates['inflation']/100)
        return dict(baseline=float(payroll+operating),projected=float(projected.quantize(Decimal('.01'))),difference=float((projected-payroll-operating).quantize(Decimal('.01'))),formula='Nómina × (1 + ajuste salarial) + demás egresos × (1 + ajuste operativo) × (1 + inflación)')
