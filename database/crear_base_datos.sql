-- PLATAFORMA DE PRESUPUESTO v0.5 | PostgreSQL 16+
-- psql -U finanzas -d postgres -v ON_ERROR_STOP=1 -f crear_base_datos.sql
-- En pgAdmin: crear finanzas y ejecutar solo BEGIN..COMMIT.
-- IF NOT EXISTS conserva tablas y datos; no aplica migraciones a tablas existentes.
-- public.budgets conserva el formato anterior; public.financial_entries contiene el nuevo CSV.
\set ON_ERROR_STOP on
SELECT 'CREATE DATABASE finanzas ENCODING ''UTF8'' TEMPLATE template0'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname='finanzas')
\gexec
\connect finanzas
BEGIN;

CREATE TABLE IF NOT EXISTS budgets (
	id SERIAL NOT NULL, 
	department VARCHAR(100) NOT NULL, 
	period VARCHAR(7) NOT NULL, 
	amount NUMERIC(16, 2) NOT NULL, 
	payroll NUMERIC(16, 2) NOT NULL, 
	operating NUMERIC(16, 2) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (department, period)
)

;

CREATE TABLE IF NOT EXISTS financial_imports (
	id SERIAL NOT NULL, 
	sha256 VARCHAR(64) NOT NULL, 
	filename VARCHAR(255) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	username VARCHAR(100) NOT NULL, 
	warnings JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (sha256)
)

;

CREATE TABLE IF NOT EXISTS users (
	id SERIAL NOT NULL, 
	username VARCHAR(100) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
)

;

CREATE TABLE IF NOT EXISTS financial_entries (
	id SERIAL NOT NULL, 
	batch_id INTEGER NOT NULL, 
	source_id VARCHAR(100) NOT NULL, 
	year INTEGER NOT NULL, 
	month INTEGER NOT NULL, 
	category VARCHAR(150) NOT NULL, 
	subcategory VARCHAR(150) NOT NULL, 
	concept VARCHAR(300) NOT NULL, 
	nature VARCHAR(10) NOT NULL, 
	currency VARCHAR(3) NOT NULL, 
	budget NUMERIC(16, 2) NOT NULL, 
	actual NUMERIC(16, 2), 
	status VARCHAR(15) NOT NULL, 
	original JSON NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (year, source_id, currency), 
	CHECK (month BETWEEN 1 AND 12), 
	CHECK (year BETWEEN 1900 AND 9999), 
	CHECK (budget >= 0), 
	CHECK (actual IS NULL OR actual >= 0), 
	CHECK (nature IN ('income','expense')), 
	CHECK ((status='pendiente' AND actual IS NULL) OR (status='completado' AND actual IS NOT NULL)), 
	FOREIGN KEY(batch_id) REFERENCES financial_imports (id)
)

;

CREATE TABLE IF NOT EXISTS login_sessions (
	token_hash VARCHAR(64) NOT NULL, 
	user_id INTEGER NOT NULL, 
	expires FLOAT NOT NULL, 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES users (id)
)

;

CREATE OR REPLACE VIEW public.v_partidas_presupuesto AS
SELECT id,year AS anio,month AS mes,currency AS moneda,
       source_id AS id_origen,category AS categoria,subcategory AS subcategoria,
       concept AS concepto,nature AS naturaleza,budget AS presupuesto_estimado,
       actual AS resultado_real,status AS estado,
       budget-actual AS diferencia_varianza,
       ROUND(actual*100/NULLIF(budget,0),2) AS porcentaje_ejecucion
FROM public.financial_entries;
CREATE OR REPLACE VIEW public.v_resumen_partidas AS
SELECT year AS anio,month AS mes,currency AS moneda,nature AS naturaleza,
       SUM(budget) AS presupuesto_total,
       COUNT(*) FILTER (WHERE actual IS NULL) AS partidas_pendientes,
       CASE WHEN COUNT(*) FILTER (WHERE actual IS NULL)=0 THEN SUM(actual) END AS resultado_total,
       SUM(actual) AS resultado_conocido_parcial
FROM public.financial_entries GROUP BY year,month,currency,nature;
COMMIT;
-- Primera cuenta: docker compose exec backend python -m app.create_user administrador admin
-- No hay cuentas ni datos precargados. Instalar por empresa: no hay aislamiento multiempresa.
-- No se interpreta el formato de movimientos contables; este CSV es de partidas agregadas.
-- Pendiente con Gasto_Real=0 se almacena como NULL. Completado con 0 es cero conocido.
-- Los porcentajes se recalculan; presupuestos con denominador cero devuelven NULL.
-- Categoria Ingresos = ingreso; otras categorias = egreso. Confirmar al importar.
-- Moneda elegida al cargar el archivo; departamento no se deduce de categoría.
-- La aplicación crea las tablas al arrancar; las vistas se crean ejecutando este SQL.
