# Byakuyo · Plataforma de presupuesto corporativo

Primera base ejecutable del PRD. Python + FastAPI + SQLAlchemy, PostgreSQL y React con Vite. **Entorno de desarrollo local; no es una versión de producción ni el MVP completo.**

## Ejecutar con Docker Desktop

1. Extrae este proyecto en una carpeta.
2. Copia `.env.example` a `.env` y sustituye la contraseña por una cadena alfanumérica larga.
3. Ejecuta `docker compose up --build`.
4. Abre http://localhost:8080. Documentación API: http://localhost:8000/docs.
5. En Importaciones carga `examples/presupuestos.csv`; selecciona septiembre de 2026.

La base PostgreSQL conserva los registros en un volumen. No ejecutar `docker compose down -v` si quieres conservarlos. Los puertos publicados se limitan a localhost.

## Desarrollo sin Docker

Backend (desde backend):
```
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Sin DATABASE_URL se usa SQLite para pruebas locales, no PostgreSQL. Para PostgreSQL configura `DATABASE_URL=postgresql+psycopg://usuario:clave@localhost:5432/byakuyo`.

Frontend (desde frontend, segunda terminal):
```
npm ci
npm run dev
```
Abre http://localhost:5173. Vite redirige /api al backend.

## Implementado

- Registro de presupuesto y gasto agregado por departamento/mes; unicidad departamento y periodo.
- Dashboard y filtros conectados al backend; no hay datos ficticios automáticos.
- KPI: presupuesto, gasto, saldo y utilización. Moneda inicial MXN.
- Importación CSV UTF-8 transaccional, máximo 2 MB y 10000 filas; errores o duplicados rechazan el archivo completo.
- Proyección base: media de hasta tres meses completos para los mismos departamentos, anteriores o iguales al periodo seleccionado.
- What-If: ajustes separados de nómina y operación; inflación afecta solo operación.
- Alertas: consumo >=90% informativo; sobrepresupuesto hasta 10% advertencia; superior a 10% crítico. Presupuesto cero y gasto positivo es crítico; cero/cero no calcula porcentaje.
- Pantalla de estado de Power BI pendiente de configurar.

## Límites y decisiones pendientes

No hay autenticación, autorización, aprobaciones, auditoría, XLSX, escenarios guardados ni IA validada. No cargar datos financieros sensibles todavía ni publicar el servidor en internet. Las cifras agregadas no sustituyen un registro contable de movimientos. La proyección puede mezclar un mes incompleto con meses cerrados; se debe incorporar estado de cierre y evaluación temporal antes de usarla para decisiones.

Los umbrales, fórmulas, moneda, KPI y cortes mensuales son supuestos provisionales. Faltan migraciones Alembic, control de concurrencia de importaciones, CRUD de departamentos y usuarios y manejo de conflictos en inserciones simultáneas. El esquema inicial se crea con create_all únicamente para desarrollo.

## Power BI Embedded

Antes de implementarlo hay que decidir entre **user owns data** (usuarios internos con identidad y permisos Microsoft) y **app owns data** (backend genera tokens). No son intercambiables en permisos/licencias.

Para app owns data: aplicación Microsoft Entra, service principal habilitado, acceso al workspace, reporte publicado y capacidad para producción. Secretos y token de Entra solo en backend. La emisión de embed tokens debe exigir autenticación y permisos; añadir RLS si el acceso se limita por departamento. React usará powerbi-client-react después de configurar ese contrato. Los reportes leen PostgreSQL mediante un modelo semántico; definir Import/DirectQuery y gateway/red según el alojamiento. No existe PBIX ni integración activa en este paquete.

Documentación oficial:
- https://learn.microsoft.com/en-us/power-bi/developer/embedded/embed-service-principal
- https://learn.microsoft.com/en-us/power-bi/guidance/powerbi-implementation-planning-usage-scenario-embed-for-your-customers

## Próxima etapa

1. Confirmar columnas y un histórico real anonimizado; definir cierre mensual y departamentos.
2. Implementar login, roles y auditoría antes de aprobaciones o exposición externa.
3. Agregar XLSX y migraciones; pruebas contra PostgreSQL.
4. Evaluar predicciones con partición temporal y MAE/WAPE frente a la media base.
5. Integrar Power BI según licencias y política de acceso.

## Verificación

Desde backend: `python -m pytest`. Desde frontend: `npm run build`.

### Resultado de esta entrega

Compilación React correcta y 3 pruebas de API aprobadas sobre SQLite: cálculos/duplicados, rechazo atómico de CSV y presupuesto cero/exclusión de futuro. Docker y PostgreSQL no se ejecutaron en este entorno; su integración aún debe verificarse. No se realizó inspección visual en navegador.
