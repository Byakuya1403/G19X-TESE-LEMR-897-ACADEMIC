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
- Dashboard y filtros conectados al backend; invitados ven una demostración y los roles financieros acceden a datos guardados.
- KPI: presupuesto, gasto, saldo y utilización. Moneda inicial MXN.
- Importación CSV UTF-8 transaccional, máximo 2 MB y 10000 filas; errores o duplicados rechazan el archivo completo.
- Proyección base: media de hasta tres meses completos para los mismos departamentos, anteriores o iguales al periodo seleccionado.
- What-If: ajustes separados de nómina y operación; inflación afecta solo operación.
- Alertas: consumo >=90% informativo; sobrepresupuesto hasta 10% advertencia; superior a 10% crítico. Presupuesto cero y gasto positivo es crítico; cero/cero no calcula porcentaje.
- Pantalla de estado de Power BI pendiente de configurar.

## Límites y decisiones pendientes

Se agregó autenticación y autorización por rol. Faltan aprobaciones, auditoría, XLSX, escenarios guardados e IA validada. No cargar datos financieros sensibles todavía ni publicar el servidor en internet. Las cifras agregadas no sustituyen un registro contable de movimientos. La proyección puede mezclar un mes incompleto con meses cerrados; se debe incorporar estado de cierre y evaluación temporal antes de usarla para decisiones.

Los umbrales, fórmulas, moneda, KPI y cortes mensuales son supuestos provisionales. Faltan migraciones Alembic, control de concurrencia de importaciones, CRUD de departamentos y usuarios y manejo de conflictos en inserciones simultáneas. El esquema inicial se crea con create_all únicamente para desarrollo.

## Power BI Embedded

Antes de implementarlo hay que decidir entre **user owns data** (usuarios internos con identidad y permisos Microsoft) y **app owns data** (backend genera tokens). No son intercambiables en permisos/licencias.

Para app owns data: aplicación Microsoft Entra, service principal habilitado, acceso al workspace, reporte publicado y capacidad para producción. Secretos y token de Entra solo en backend. La emisión de embed tokens debe exigir autenticación y permisos; añadir RLS si el acceso se limita por departamento. React usará powerbi-client-react después de configurar ese contrato. Los reportes leen PostgreSQL mediante un modelo semántico; definir Import/DirectQuery y gateway/red según el alojamiento. No existe PBIX ni integración activa en este paquete.

Documentación oficial:
- https://learn.microsoft.com/en-us/power-bi/developer/embedded/embed-service-principal
- https://learn.microsoft.com/en-us/power-bi/guidance/powerbi-implementation-planning-usage-scenario-embed-for-your-customers

## Próxima etapa

1. Confirmar columnas y un histórico real anonimizado; definir cierre mensual y departamentos.
2. Incorporar auditoría, recuperación de contraseña y controles de producción antes de exposición externa.
3. Agregar XLSX y migraciones; pruebas contra PostgreSQL.
4. Evaluar predicciones con partición temporal y MAE/WAPE frente a la media base.
5. Integrar Power BI según licencias y política de acceso.

## Verificación

Desde backend: `python -m pytest`. Desde frontend: `npm run build`.

### Resultado de esta entrega

Compilación React correcta y 3 pruebas de API aprobadas sobre SQLite: cálculos/duplicados, rechazo atómico de CSV y presupuesto cero/exclusión de futuro. Docker y PostgreSQL no se ejecutaron en este entorno; su integración aún debe verificarse. No se realizó inspección visual en navegador.


## v0.2 · Inicio de sesión sin cambiar la pantalla inicial

Al abrir la plataforma aparece el dashboard con datos de demostración, claramente indicados. No se abre automáticamente el formulario de acceso. El botón **Iniciar sesión** de la esquina superior abre un diálogo; al ingresar se conserva el dashboard y se cargan los datos permitidos. Al cerrar sesión se vuelve a la demostración. Los registros reales nunca se devuelven a invitados.

### Crear la primera cuenta

Con Docker funcionando, desde la carpeta byakuyo:
```
docker compose exec backend python -m app.create_user administrador admin
```
Escribe una contraseña de 12 a 128 caracteres y confírmala. No aparece mientras la escribes. No existen contraseñas predeterminadas. Inicia sesión con `administrador`; en **Usuarios** crea las cuentas financieras. Alternativamente:
```
docker compose exec backend python -m app.create_user director director
docker compose exec backend python -m app.create_user analista analyst
```
Sin Docker, desde backend y con el entorno activado, ejecuta `python -m app.create_user administrador admin`.

### Permisos de esta entrega

| Rol | Datos financieros reales | Registrar presupuesto | CSV | Simulación | Crear/listar cuentas |
|---|---|---|---|---|---|
| Invitado | No (solo demo) | No | No | No | No |
| Director Financiero | Sí | Sí | No | Sí | No |
| Analista Financiero | Sí | No | Sí | Sí | No |
| Administrador | No (solo demo) | No | No | No | Sí |

Los permisos se validan en FastAPI además de la interfaz. El administrador no obtiene acceso financiero por ser administrador. La asignación es por cuenta, no por selección en el formulario. La aprobación/ajuste de presupuestos del director sigue pendiente; no se muestra como implementada.

### Sesiones y límites

Contraseñas con PBKDF2-SHA256 y sal aleatoria; sesiones opacas de 8 horas persistidas en BD, almacenando solo hash del token. Cookie HttpOnly y SameSite=Strict; encabezado obligatorio en peticiones que modifican datos. Cierre de sesión revoca el token. Límite de 10 intentos de acceso por minuto/IP por proceso; con proxy local pueden compartir IP. Antes de producción: HTTPS y COOKIE_SECURE=true en backend, almacenamiento compartido para el límite de intentos, auditoría, recuperación/cambio de contraseña, migraciones y pruebas con PostgreSQL. No desplegar esta base local como solución de producción.

### Actualizar una instalación previa

Detén los contenedores, reemplaza el código con esta versión y conserva tu `.env`. Ejecuta `docker compose up --build` usando el mismo proyecto y volumen. No borres el volumen PostgreSQL. El backend crea las tablas nuevas sin eliminar presupuestos existentes; esta creación automática no sustituye migraciones de producción.

Verificación v0.2: React compiló y 6 pruebas de API pasaron con SQLite, incluidos aislamiento de invitados, permisos, sesiones vencidas y rechazo de peticiones sin encabezado de protección. PostgreSQL/Docker y revisión visual en navegador siguen pendientes; el navegador de pruebas no estuvo disponible.
