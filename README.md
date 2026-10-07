# Plataforma de Presupuesto · v0.7

Python, FastAPI, React y PostgreSQL. Dashboard como pantalla inicial; login opcional desde el botón superior. Invitados ven demostración; director y analista ven datos reales; administrador gestiona cuentas. Versión de desarrollo local, no sistema de producción validado.

## Nueva instalación

1. Extrae la carpeta `plataforma_presupuesto`.
2. Copia `.env.example` a `.env` y cambia POSTGRES_PASSWORD por una cadena alfanumérica larga.
3. Con Docker Desktop activo: `docker compose up -d --build`.
4. Abre http://localhost:8080. No abrir index.html con doble clic.
5. Crea la primera cuenta:
```
docker compose exec backend python -m app.create_user administrador admin
```
Escribe y confirma contraseña de 12 a 128 caracteres. Inicia sesión; en Usuarios crea una cuenta con rol Analista Financiero para importar y otra Director Financiero para consultar/simular y registrar presupuestos anteriores.

## Importar el CSV empresarial

En sesión de Analista, abre Importaciones y selecciona `examples/presupuesto_empresarial_2026.csv` o el original suministrado.

1. Confirma la moneda verdadera; el archivo no la incluye. MXN en pantalla es una selección inicial, no una moneda detectada.
2. Para este archivo, marca la reparación de columnas desplazadas: registros 132–136 traen el mes en Concepto.
3. Pulsa Validar y previsualizar; se muestran las advertencias, primeras filas y cantidad pendiente.
4. Confirma la importación. Se guardan 36 partidas en una transacción y se selecciona el último periodo disponible (marzo 2026 en este ejemplo).

Formato obligatorio de esta versión: ID_Registro, Anio, Mes, Categoria, Subcategoria, Concepto, Presupuesto_Estimado, Gasto_Real, Diferencia_Varianza, Porcentaje_Ejecucion y Estado. CSV UTF-8 con coma, importes con punto decimal, máximo 2 MB/10000 filas. Estados Pendiente y Completado. No se acepta un CSV arbitrario ni XLSX todavía.

La categoría Ingresos se interpreta como ingreso; cualquier otra como egreso. Esa clasificación se informa en la interfaz y debe ser válida para el origen. No se infieren departamentos. Nómina se identifica por subcategoría Nómina; demás egresos se consideran operación en la simulación (supuesto, no tratamiento contable de CAPEX).

Pendiente con Gasto_Real=0 se guarda como resultado desconocido (NULL); un cero completado sí es conocido. No se aceptan pendientes con importe real no cero, negativos ni ajustes contables: requieren reglas específicas. Las varianzas y porcentajes recibidos se validan contra las cifras y se recalculan al consultar. Conservamos el JSON de cada fila original, avisos y autor de la carga.

Duplicados: hash del archivo y clave año/ID/moneda. Una carga repetida o conflicto se rechaza completo; no sobrescribe partidas. Instalación por empresa y fuente homogénea; archivos de distintas fuentes con IDs coincidentes requieren una futura identificación de origen/versiones. No hay multiempresa ni mapeo universal.

## Dashboard y simulación

Vista Partidas del CSV: cuatro KPI de ingreso/egreso presupuestado/real, resultado neto, alertas por ingreso inferior al presupuesto o gasto superior, detalle por concepto, filtro de periodo/categoría/moneda. No se mezclan monedas. Los totales completos quedan pendientes si alguna partida del grupo lo está; los conocidos parciales se muestran aparte.

Predicción de egresos: se ordenan los periodos por año y mes, se toma el máximo del histórico importado para la moneda elegida y se muestra su mes siguiente (incluido cambio de año). El filtro de periodo de consulta no cambia ese horizonte. Se calcula una media de hasta tres meses con todas sus partidas completadas; los pendientes no se convierten en ceros. No IA validada. La cobertura mensual puede variar y la columna Estado no certifica que el mes esté cerrado; antes de decisiones reales se requiere cierre mensual y evaluación temporal.

Simulación solo sobre egresos completados de la selección; rechaza periodos pendientes. Ajuste salarial sobre Nómina; ajuste operativo e inflación sobre otros egresos. No es una predicción validada.

La interfaz consulta únicamente partidas del CSV, sin selector de fuente. Los registros del formato anterior permanecen en la base y sus endpoints de compatibilidad siguen disponibles; no se eliminan ni se suman a las partidas nuevas.

## Actualizar conservando datos y cuentas

Cambió el nombre de la carpeta, la base por defecto y el volumen por defecto. Una instalación nueva no recupera automáticamente el volumen anterior. NO borres volúmenes ni ejecutes down -v.

Opción A: conserva el volumen y la BD existentes. Antes de cambiar, anota el nombre real del volumen (`docker volume ls`) y los valores POSTGRES_DB y POSTGRES_USER del contenedor anterior. Copia la contraseña vigente a .env y configura POSTGRES_DB, POSTGRES_USER y POSTGRES_VOLUME con esos valores. Detén la instalación anterior con `docker compose down` (sin -v), luego inicia esta versión. No renombra físicamente la BD antigua; conserva su identidad por continuidad. El código y todos los nombres del paquete nuevo usan denominaciones neutras. Deberás volver a iniciar sesión porque cambió el nombre de cookie.

Opción B: para usar una base con nombre nuevo y conservar datos, haz respaldo y restauración. En la carpeta anterior:
```
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/respaldo.dump'
docker compose cp db:/tmp/respaldo.dump ./respaldo.dump
docker compose down
```
Conserva respaldo.dump y la carpeta anterior. En la carpeta nueva, configura .env para finanzas y un volumen NUEVO; inicia solamente PostgreSQL (no el backend todavía):
```
docker compose up -d db
```
Espera a que esté healthy y copia el respaldo a la carpeta nueva. Restaura en la BD nueva vacía:
```
docker compose cp respaldo.dump db:/tmp/respaldo.dump
docker compose exec db pg_restore -U finanzas -d finanzas --no-owner --no-privileges /tmp/respaldo.dump
docker compose up -d --build
```
Si la restauración da errores, no continúes como si hubiera terminado. Esta ruta requiere una base destino sin las tablas de la aplicación. No crea ni borra automáticamente tu instalación previa. Los presupuestos y cuentas anteriores quedan en sus tablas; las partidas nuevas se crean al arrancar el backend.

## Script SQL incluido

`database/crear_base_datos.sql` crea la estructura exacta utilizada por esta versión, más vistas para consultas y Power BI. Sustituye la propuesta anterior de tablas normalizadas independientes: esta entrega persiste partidas en public.financial_entries y archivos en public.financial_imports. El backend crea las tablas faltantes al iniciar, así que no es obligatorio ejecutar SQL para la aplicación. Las vistas sí requieren ejecutarlo:
```
docker compose cp database/crear_base_datos.sql db:/tmp/crear_base_datos.sql
docker compose exec db psql -U finanzas -d postgres -v ON_ERROR_STOP=1 -f /tmp/crear_base_datos.sql
```
Estas instrucciones SQL asumen la BD nueva finanzas. Si reutilizas otra BD, adapta la conexión del script o ejecuta solo BEGIN..COMMIT dentro de esa BD mediante pgAdmin. IF NOT EXISTS no aplica migraciones a tablas existentes.

## Desarrollo sin Docker

Backend: entorno virtual, `pip install -r requirements.txt`, `uvicorn app.main:app --reload`. Sin DATABASE_URL usa SQLite finanzas.db; para PostgreSQL configura DATABASE_URL. Frontend: `npm ci`, `npm run dev`, abre http://localhost:5173. API: http://localhost:8000/docs.

## Verificación y límites

Compilación React correcta. Pruebas API con SQLite: importación de las 36 partidas, reparación solo autorizada, rechazo atómico, duplicados, monedas separadas, permisos, login y totales. Enero: ingresos 285600.00 y egresos 189120.50; febrero: 285000.00 y 203110.00; marzo: resultados pendientes. Estos importes son de prueba; la moneda debe confirmarse por el usuario.

Docker/PostgreSQL y revisión visual con navegador no se ejecutaron aquí. SQL generado desde los modelos de la aplicación y validado sintácticamente. Power BI sigue pendiente de configuración. Faltan auditoría completa, recuperación de contraseña, cierre/aprobación y modelos de IA evaluados. Antes de producción: HTTPS/cookie Secure, permisos de servidor, pruebas PostgreSQL, migraciones, revisión de red, backups y evaluación de acceso/concurrencia. No hay capacidad multiempresa.

## Cambios v0.7

Sin filtro de fuente ni vistas duplicadas. La tarjeta de predicción muestra mes/año objetivo, último periodo disponible y meses usados para el cálculo. Con el archivo empresarial: referencia marzo 2026, objetivo abril 2026, base enero y febrero completados. Estimación de egresos 196115.25 en la moneda elegida. El cálculo es una referencia estadística; no entrenamiento de IA. No requiere cambiar esquema SQL ni volver a importar el CSV.

Verificación v0.7: React compiló; 10 pruebas API/funcionales sobre SQLite pasaron, incluida invariancia frente al orden de filas, cambio de año y horizonte independiente del filtro de consulta. Docker/PostgreSQL y revisión visual siguen pendientes.

## Diseño principal v0.7

Se recuperó la composición inicial: histórico mensual con barras por categoría a la izquierda, predicción a la derecha y cuatro KPI debajo. El filtro superior de periodo limita el panel al mes seleccionado y actualiza KPI, alertas y detalle. La predicción conserva el horizonte del último mes importado. Las partidas pendientes tienen una barra diferenciada sin porcentaje engañoso de cero. No se restauró el selector de fuente, no se mezclan ingresos con consumo presupuestario y no se requieren cambios en la base.

Verificación visual de composición por código y compilación React correcta; comprobación del histórico contra las 36 partidas: orden, totales por mes, filtros, pendientes y separación de ingresos. Sin revisión en navegador en esta entrega. Backend y esquema no cambiaron respecto a v0.5.

## Corrección de filtros v0.7

El panel izquierdo aplica el mes elegido y oculta los demás meses. El filtro de categoría ahora incluye Ingresos, identificado como ingreso, con importe recibido y porcentaje de cumplimiento; egresos usan importe utilizado y ejecución. Sin sumar ingresos como consumo ni marcar su cumplimiento superior a 100% como sobrepresupuesto. La predicción sigue siendo de egresos y conserva el horizonte siguiente al último mes importado. Si se selecciona solo Ingresos se explica que esa predicción no aplica. No hay cambios de esquema ni necesidad de reimportar.

Verificación v0.7: compilación React correcta y comprobación de filtros combinados contra el CSV suministrado: enero/febrero/marzo aislados, ingreso de enero 285600 sobre 280000 (102%), pendientes, moneda y selección sin datos. Sin cambios de backend; no hubo revisión visual en navegador.
