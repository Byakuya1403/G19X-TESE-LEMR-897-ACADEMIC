# Historial de cambios

Este documento reúne las notas de las entregas del proyecto. Los números identifican las versiones utilizadas durante el desarrollo; no implican que existan etiquetas Git con esos nombres. No se añaden fechas de publicación que no estén registradas.

La instalación y el uso vigentes se documentan en [README.md](README.md).

## v0.18 — Regresión de presupuesto con mes del año

### Corregido

- Retirada la pestaña Power BI del menú de director y analista y eliminado su panel pendiente de configurar, de acuerdo con el alcance de la entrega.
- Reproducido el fallo con el CSV adjunto de 792 filas: importación correcta y rechazo `referencia_mejor` del modelo de tendencia simple, incapaz de representar los aumentos anuales de determinados meses.
- Se mantiene `LinearRegression`. Con 24 meses se comparan tendencia y tendencia con indicadores del mes del año. Selección temporal en los meses 19–21 y evaluación independiente en 22–24; cada ajuste utiliza únicamente meses anteriores al objetivo correspondiente. La tendencia simple se conserva con menos de 24 meses o si la configuración estacional no mejora la selección en más de un centavo.
- El MAE elevado sigue bloqueando la publicación con la política del 30% existente. Una referencia del mes previo mejor que la regresión produce ahora `evaluacion.supera_referencia=false` y una advertencia con comparación de errores, sin un bloqueo automático por diferencias pequeñas. No se sustituye el modelo por una media o por esa referencia.
- Respuesta con `configuracion`, `descripcion_modelo` y `seleccion_modelo`; interfaz indica la configuración real y explica la separación entre selección y evaluación.
- README actualizado: la predicción de presupuesto utiliza `LinearRegression` de scikit-learn sobre los presupuestos asignados guardados en la base de datos.

### Verificación y actualización

71 pruebas de backend con SQLite y 15 de frontend correctas; compilación y formato correctos. Incluyen patrón anual, cambio de año, selección independiente de los valores de evaluación final, ajustes sin futuro, preferencia por tendencia simple cuando corresponde y flujo CSV → base aislada → endpoint. El CSV sintético de 792 registros se probó completo sin modificarlo y ahora se incluye en `examples/presupuesto_historico_completo_2024_2026-v4.csv`. Sus datos fueron generados con Gemini de Google, identificado en la interfaz como «3.6 Flash», según la captura de la conversación de generación proporcionada por el autor del proyecto, y abarcan 36 meses de enero de 2024 a diciembre de 2026. También se comprobaron cortes temporales anteriores, con advertencia cuando la referencia tuvo menor MAE.

No hay dependencias ni migraciones nuevas. Actualizar frontend y backend juntos y reconstruir con `docker compose up -d --build`, conservando `.env` y volumen. No volver a importar archivos ya guardados. El pie de página indica v0.18. El autor del proyecto confirmó la prueba de la plataforma con Docker y PostgreSQL y la revisión visual en el navegador. Estas comprobaciones complementan las pruebas automatizadas con SQLite y la prueba del CSV en una base SQLite aislada. Los resultados dependen de las otras cargas, el periodo, la categoría y la moneda.

## v0.17 — Composición variable y retirada de importaciones

### Corregido

- La igualdad literal de conceptos, categorías y número de partidas deja de ser condición de entrenamiento. Un presupuesto total mensual puede cambiar de composición: ahora se informa con `composicion_variable` y una advertencia de alcance/integridad.
- Se mantienen al menos seis meses consecutivos, ventana de 24 meses, separación de moneda/categoría, deduplicación, importes válidos y evaluación temporal MAE frente a referencia. El cambio corrige el bloqueo `cobertura_variable` observado en Resumen, sin garantizar una cifra si la serie no supera los demás controles.

### Añadido

- `backend/app/imports.py`: `GET /api/financial/imports` paginado y `DELETE /api/financial/imports/{batch_id}`. Solo Analista, utilizando el permiso existente; sesión, `X-App: 1` para DELETE y confirmación exacta `ELIMINAR N` y huella del archivo validadas en el servidor.
- Componente `ImportHistory` en Importaciones: ID, archivo, moneda, periodos, número de partidas, autor, paginación y diálogo con código escrito, cancelación y bloqueo durante la operación.
- Borrado de la carga y sus partidas en una transacción, con bloqueo de fila PostgreSQL y rollback ante errores. Se conservan las otras cargas; se permite reimportar el archivo eliminado o su versión corregida si sus claves no colisionan con otros datos.
- Actualización del listado y datos financieros después de eliminar. El forecast utiliza el histórico restante y puede quedar sin información suficiente. No hay restauración desde la interfaz.

### Actualización y verificación

66 pruebas de backend con SQLite y 13 de frontend correctas; compilación y formato correctos. Casos de composición variable, evaluación deficiente, permisos, confirmación ausente/incorrecta, archivos con nombres iguales, eliminación aislada, rollback, última carga, reimportación, paginación y recálculo del forecast tras borrar.

No se agregan dependencias ni cambios de tablas. Conservar `.env` y volumen, actualizar código y ejecutar `docker compose up -d --build`. No reimportar archivos existentes para actualizar. Docker/PostgreSQL, concurrencia entre procesos y revisión visual con navegador quedan pendientes en el entorno de despliegue. La plataforma no deduce cierre mensual, integridad total de una carga ni empresas independientes a partir del contenido.

## v0.16 — Presupuesto conocido con ejecución pendiente

### Corregido

- `forecast.py` acepta los presupuestos asignados aunque `Estado=Pendiente` y `actual=NULL`. El gasto real y el estado de ejecución no determinan la elegibilidad del presupuesto conocido, ni se imputan como cero.
- Se conservan seis meses mínimos, continuidad cronológica, cobertura comparable, deduplicación, validación temporal con MAE, referencia del mes anterior y rechazo de importes inválidos. El importe base es el presupuesto asignado del mes seleccionado.
- `historial[].ejecucion_completada` reemplaza `completo` y describe exclusivamente la ejecución del gasto. La gráfica muestra todos los presupuestos registrados como valores conocidos y señala ejecución pendiente en los títulos y tabla. El aviso de gasto pendiente es informativo.

### Eliminado

- Función `financial.forecast_expenses`, media de hasta tres meses de gasto real, llamada desde dashboard, campo `prediction` y pruebas exclusivas de ese cálculo retirado.
- El único módulo de pronóstico es `forecast.py`; ambas vistas de Resumen continúan compartiendo su respuesta. `financial.py` conserva importación, indicadores, alertas y Simulación.

### Actualización y verificación

Actualizar backend y frontend juntos y ejecutar `docker compose up -d --build`, conservando `.env` y el volumen. No se agregan dependencias, tablas ni migraciones; no es necesario reimportar archivos. Los clientes externos que consuman el campo retirado deben consultar `/api/forecast/budget` con sesión financiera.

56 pruebas de backend con SQLite y ocho de frontend, compilación y formato correctos. Incluyen seis CSV mensuales con ejecución pendiente, persistencia de `actual=NULL`, forecast disponible para presupuestos válidos, igualdad frente a la misma serie completada, rechazo con historial insuficiente o mala evaluación, dashboard sin `prediction` y Simulación todavía bloqueada por gasto pendiente. No se ha ejecutado Docker/PostgreSQL ni revisión visual con navegador en este entorno. Esta corrección elimina el bloqueo observado en la captura; no garantiza que el histórico del despliegue cumpla los demás criterios.

## v0.15 — Forecast sobre el histórico acumulado en la base de datos

### Corregido

- La tarjeta verde de predicción del siguiente mes utiliza ahora `GET /api/forecast/budget`, igual que el detalle de regresión lineal y su gráfica. Una única consulta alimenta ambas vistas; ya no muestra la media anterior de gasto real.
- El forecast agrupa las partidas guardadas en `financial_entries` de todas las importaciones del espacio financiero, por año, mes, moneda y categoría. Los archivos mensuales y las cargas complementarias construyen un histórico común.
- Eliminados el selector de CSV, el filtro `batch_id` del forecast y la respuesta de selección ambigua. La procedencia se informa con el número de registros e importaciones analizados, sin exigir un archivo.
- La deduplicación defensiva utiliza la clave global existente año/ID/moneda, independientemente de la importación. Se conservan el rechazo de hashes repetidos y conflictos por clave al importar; no se sobrescriben ni borran partidas.
- Consulta SQL limitada a los últimos 24 meses aplicables. Se conservan seis meses mínimos, validación temporal con MAE, separación de monedas/ingresos y filtros de periodo/categoría.

### Persistencia, actualización y límites

Los CSV ya se guardaban en base de datos al confirmar la importación; se reutiliza esa persistencia. El forecast no lee CSV ni requiere conservar los archivos. `batch_id` mantiene la trazabilidad, sin aislar el entrenamiento. La instalación representa un espacio financiero común: no se incorpora separación por empresas ni identificación automática de duplicados con IDs distintos.

No cambian las tablas SQL, el login, los roles ni Simulación. No hay dependencias nuevas. El campo de proyección estadística del dashboard financiero se conserva por compatibilidad de API, pero deja de alimentar la interfaz. Actualizar el código y ejecutar `docker compose up -d --build`, conservando `.env` y el volumen; no reimportar archivos existentes ni ejecutar migraciones.

### Verificación

**53 pruebas de backend con SQLite y siete de frontend correctas; compilación y formato correctos.** Pruebas de cargas mensuales desordenadas entre archivos, partidas complementarias, persistencia en sesiones SQL independientes, duplicados y conflictos, forecast sin parser CSV, actualización desde la base, filtros, evaluación temporal y ambas tarjetas. Se mantiene el límite de cobertura comparable y partidas completadas; no se certifica el cierre contable. La ejecución de Docker/PostgreSQL y la revisión visual con navegador deben validarse en el entorno de despliegue.

## v0.14 — Predicción mensual de presupuestos

### Añadido

- `backend/app/forecast.py`: agregación mensual del presupuesto asignado a egresos y `LinearRegression` local de scikit-learn. Se utiliza `financial_entries.budget`, no el gasto real.
- `GET /api/forecast/budget` protegido por los permisos financieros existentes, con filtros de periodo, moneda, categoría e importación y respuesta tipada.
- Aislamiento por `batch_id`; selección explícita si hay varios conjuntos. No se deducen relaciones entre archivos ni se mezclan ingresos con egresos.
- Ventana de seis a 24 meses consecutivos, con partidas completadas y cobertura comparable. Rechazo de meses faltantes, registros inválidos y duplicados inconsistentes.
- Evaluación de los últimos tres meses por origen móvil, MAE y referencia del mes anterior. Se rechaza una regresión peor que esa referencia o con error relativo por encima de la política inicial del 30%, con tolerancia mínima de un centavo. No se publican porcentajes de confianza.
- Límite no negativo explícito, variación porcentual nula con base cero y rechazo de resultados no finitos.
- Nueva sección de Resumen, componentes `BudgetForecast` y `BudgetTrendChart`, gráfica SVG con histórico, estimación diferenciada y tabla accesible. Sin nueva biblioteca de gráficas.
- Pruebas del modelo, endpoint, importación CSV, aislamiento, filtros, respuesta insuficiente y renderizado. Fixtures comunes del backend en `tests/conftest.py`.

### Conservado

Los paneles anteriores y la proyección estadística de gasto real se mantienen. El mes elegido acota solo el nuevo pronóstico al mes siguiente; no modifica el horizonte de la proyección anterior. Se conservaron sin cambios login, roles, importaciones, Simulación y modelos SQL. No se incorporaron recomendaciones, LLM, chatbots ni servicios externos de IA.

### Dependencias y actualización

Se agregó `scikit-learn>=1.5,<2` (comprobado con 1.9.1). Conservar `.env` y el volumen, actualizar el código y reconstruir con `docker compose up -d --build`. No ejecutar migraciones ni reimportar archivos existentes. Cada archivo debe contener por sí mismo un histórico suficiente; esta versión no agrega una función de actualización/unión de importaciones. El ejemplo de tres meses con pendientes muestra no disponibilidad y no produce una cifra inventada.

### Verificación y límites

49 pruebas de backend con SQLite y seis de frontend correctas; compilación y formato correctos. Se comprobaron ausencia de fuga temporal, agrupación por año/mes, cambio de año, separación de presupuesto frente a gasto real, deduplicación, aislamiento por importación/moneda/categoría, refresco tras importación, permisos, insuficiencia, calidad deficiente y continuidad de los paneles previos. No hubo ejecución Docker/PostgreSQL ni revisión visual con navegador. Estado Completado y cobertura homogénea son proxies de elegibilidad, no cierre contable certificado; el modelo no estima estacionalidad y el umbral de error no constituye una garantía de precisión.

## v0.13 — Retirada de la API financiera anterior

### Eliminado

- Cinco operaciones del formato anterior: `GET /api/budgets`, `POST /api/budgets`, `GET /api/dashboard`, `POST /api/simulations` y `POST /api/imports/csv`.
- Router `backend/app/routers/legacy.py`, su registro, los contratos `BudgetInput`, `Scenario`, el alias `Money` y la dependencia exclusiva `Director`.
- Listado de endpoints anteriores en el README vigente; el historial conserva su referencia para explicar la retirada.

### Comportamiento y actualización

Las rutas retiradas responden 404 y no aparecen en OpenAPI. La API `/api/financial/*` mantiene los mismos contratos y permisos. Los presupuestos anteriores permanecen en `budgets`, sin API de consulta: no se borran tablas ni registros, ni se incorporan automáticamente al formato nuevo. Se conserva el modelo de esa tabla histórica; no se requiere SQL adicional ni volver a importar CSV. La creación administrativa de cuentas `POST /api/users` sigue disponible y no forma parte del router financiero retirado.

Eliminar el archivo local `backend/app/routers/legacy.py` si actualizas mediante copia de archivos; un cambio aplicado desde Git registrará su eliminación. Después reconstruir con `docker compose up -d --build`, conservando `.env` y el volumen actual. Cualquier consumidor que aún llamara a esas rutas debe utilizar el contrato por partidas; no se ofrecen redirecciones porque los formatos de datos son diferentes.

### Verificación

Las pruebas financieras, de permisos y de validación utilizan `/api/financial/*`. Se comprueba la respuesta 404 y ausencia de OpenAPI de las cinco operaciones retiradas, además de la conservación de los datos históricos. Resultado: 27 pruebas API con SQLite correctas; compilación y formato del frontend correctos. Los 18 contratos vigentes y el DDL de las siete tablas se compararon con v0.12 y permanecen iguales. El README coincide con OpenAPI. No se ejecutaron pruebas Docker/PostgreSQL ni revisión visual con navegador.

## v0.12 — Backend por responsabilidades

### Cambios

- `main.py` reducido a composición de FastAPI, ciclo de vida, middleware y registro de routers.
- Conexión y sesiones en `database.py`; los siete modelos persistentes en `models.py`; contratos de entrada en `schemas.py`; contraseñas y autorización en `security.py`.
- Rutas agrupadas en `routers/auth.py`, `routers/users.py`, `routers/system.py` y `routers/legacy.py`.
- Finanzas e invitaciones usan `APIRouter` con dependencias compartidas, sin funciones de instalación ni modelos definidos dentro del registro de rutas.
- Cinco operaciones del formato anterior marcadas `deprecated` en OpenAPI y conservadas para compatibilidad. No se cambia su autorización ni su comportamiento.
- Backend formateado en bloques legibles. Actualizados los imports de la creación del administrador y las pruebas.
- README y documentación de arquitectura actualizados. Se mantienen sus instrucciones de clonación y el historial separado de v0.7 a v0.11.

### Actualización y verificación

No hay cambios de esquema ni credenciales. Conservar `.env`, base y volumen; actualizar el código y reconstruir con `docker compose up -d --build`. No ejecutar SQL adicional ni volver a importar el CSV.

Verificación: 22 pruebas API con SQLite; contrato OpenAPI de 23 operaciones equivalente al anterior salvo versión, etiquetas y deprecación; DDL PostgreSQL de las siete tablas idéntico. Funciones de seguridad equivalentes por comparación de AST y creación del administrador inicial comprobada. Se conservan validación, cookies, hashes, permisos y separación entre demostración y datos reales. Compilación y formato del frontend comprobados; solo cambió su indicador de versión. No hubo pruebas Docker/PostgreSQL de ejecución o concurrencia ni revisión visual en navegador.

### Documentación integrada

- README reescrito como documento del proyecto, con instalación mediante GitHub, problema, arquitectura, configuración, uso, roles y los 23 endpoints.
- Notas de las entregas anteriores y migraciones trasladadas a CHANGELOG.md. La actualización documental previa no modificó código ni esquema.

## v0.11 — Organización del frontend

### Cambios

- `main.jsx` reducido al montaje de React y los estilos; coordinación de la aplicación en `App.jsx`.
- Componentes `Dashboard`, `Importaciones` y `Login` separados en `frontend/src/components`.
- Cliente HTTP extraído a `services/api.js`; formatos monetarios y de meses en `utils/formatters.js`; descripciones y roles en `constants.js`.
- JavaScript y JSX formateados, incluidos los componentes existentes de simulación, activación y usuarios.
- Prettier con versión fija y comandos `npm run format` y `npm run format:check`.
- Estado de importación conservado en App para mantener la selección al cambiar de pestaña.

### Actualización y verificación registradas

Sin cambios de backend, esquema o credenciales. No se requiere reimportar CSV. Compilación y comprobación de formato correctas; diez comparaciones de renderizado con v0.10 idénticas y cinco comparaciones de API correctas, incluidos errores, cookies, X-App y multipart. No se hizo revisión visual con navegador ni se repitieron pruebas del backend.

## v0.10 — Eliminación de usuarios

### Cambios

- Botón Eliminar con confirmación y cancelación en Usuarios.
- Eliminación transaccional de cuenta, sesiones, correo asociado e invitaciones; los enlaces pendientes dejan de servir.
- Conservación del histórico financiero, archivos y autor de las cargas anteriores.
- Protección del servidor contra eliminación de la propia cuenta administrativa y pérdida del último administrador activo.
- Coordinación de eliminaciones de administradores mediante bloqueo de filas en PostgreSQL y sincronización con login.
- Posibilidad de volver a invitar un correo eliminado como cuenta independiente; sin deshacer desde la plataforma.

### Actualización y verificación registradas

Sin migración SQL ni reimportación. Para quitar la cuenta inicial, activar primero el administrador por correo e iniciar sesión con él. Se registraron 21 pruebas API con SQLite correctas, compilación React y comprobación de renderizado de la confirmación. No se comprobó concurrencia equivalente en PostgreSQL ni revisión visual con navegador.

## v0.9 — Invitaciones y activación por correo

### Cambios

- Invitación por correo personal o empresarial con rol asignado por el administrador; cuenta pendiente hasta activación.
- Creación y confirmación de contraseña por el destinatario, de 12 a 128 caracteres; login posterior por correo.
- Enlaces con token aleatorio de 256 bits, hash almacenado, caducidad de 24 horas y consumo de un solo uso al confirmar la contraseña.
- Previsualizar un enlace no lo consume. Reenviar invalida el anterior; un fallo SMTP conserva el anterior y revierte nuevas altas incompletas.
- Envío SMTP con STARTTLS o TLS implícito y modo manual explícito sin envío de correo.
- URL de la plataforma tomada de configuración fija y token retirado de la barra de dirección en la activación.
- Normalización de correos, rechazo de nombres visibles y caracteres de control; roles comprobados por el servidor.
- Compatibilidad de acceso por nombre de usuario para las cuentas anteriores. Sin registro público ni recuperación de contraseña.

### Actualización y verificación registradas

Se agregaron `user_emails` y `user_invitations` sin modificar las tablas anteriores. Conservar `.env`, base y volumen, incorporar las variables de correo y reconstruir los servicios. El arranque crea las tablas faltantes; el SQL alternativo es [database/009_invitaciones.sql](database/009_invitaciones.sql). No se requiere reimportar ni cambiar contraseñas existentes. Crear un administrador por correo genera una cuenta independiente, no asocia el correo a una cuenta anterior.

Se registraron 17 pruebas API con SQLite y compilación correctas. Incluyeron activación, confirmación, caducidad, reenvío, rechazo de enlaces usados, permisos y límites de intentos; el transporte SMTP se simuló para comprobar STARTTLS y certificados sin enviar correos reales. Se comprobó una actualización aditiva en SQLite preservando usuarios y presupuestos. Los dos scripts SQL pasaron validación sintáctica PostgreSQL; no se ejecutó Docker/PostgreSQL ni se revisó visualmente en navegador.

Referencia de diseño de los enlaces: [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html). Su uso como referencia para activación no implica que exista recuperación de contraseña.

## v0.8 — Simulación guiada

### Cambios

- Simulación reorganizada en revisión de base, ajustes y comparación.
- Barras sustituidas por campos numéricos con explicación, ejemplos y rangos.
- Base visible de nómina, otros egresos y total real, excluyendo ingresos; ajustes sin base deshabilitados.
- Explicación del efecto multiplicativo de inflación y ajuste operativo.
- Comparación de gasto real frente al escenario, diferencia monetaria y porcentual, y acción Restablecer a 0%.
- Bloqueo de selecciones sin egresos o con resultados pendientes; cambio de filtros descarta el resultado anterior.
- Fórmula del servidor y composición del resumen conservadas. La simulación no modifica archivos ni presupuestos y no equivale a la proyección del siguiente mes.

### Actualización y verificación registradas

Sin cambios SQL ni reimportación. Compilación y comprobaciones de base/renderizado correctas: periodos, categorías, monedas, nómina, ingresos excluidos y pendientes. No se hicieron nuevas pruebas de backend ni revisión visual con navegador.

## v0.7 — Resumen, filtros y proyección

### Cambios

- Composición principal recuperada: histórico mensual a la izquierda, proyección a la derecha y cuatro indicadores debajo.
- Eliminación del selector de fuente «Presupuestos anteriores / Partidas del CSV» sin mezclar las fuentes.
- Filtro de periodo aplicado al histórico para ocultar los demás meses; también actualiza indicadores, alertas y detalle.
- Categoría Ingresos visible con importe recibido y porcentaje de cumplimiento; egresos con gasto utilizado y ejecución. Ingresos superiores al presupuesto no se marcan como sobreconsumo.
- Partidas pendientes identificadas sin representar su resultado como cero.
- Proyección con mes/año objetivo, último periodo disponible y meses utilizados; horizonte posterior al máximo periodo importado, independiente del mes consultado.
- Mensaje explicativo al filtrar solo ingresos, porque la proyección estima egresos.

### Actualización y verificación registradas

Sin nuevos cambios de esquema ni reimportación. En el CSV de referencia, marzo 2026 fija el horizonte en abril; enero y febrero completados producen una estimación de egresos de 196115.25 en la moneda seleccionada. Se registraron compilación, diez pruebas API/funcionales y comprobaciones del histórico: orden de meses, cambio de año, filtros combinados, pendientes, monedas e ingresos (enero: 285600 sobre 280000, 102%). No se ejecutó Docker/PostgreSQL ni revisión visual con navegador.

## Notas para instalaciones anteriores al cambio de nombre

Durante las primeras entregas cambiaron los nombres predeterminados de carpeta, base, volumen y cookie. Renombrar el código no renombra físicamente roles o bases de PostgreSQL. Las cuentas y los presupuestos del formato anterior permanecen en sus tablas y endpoints de compatibilidad; no se suman a las partidas nuevas.

### Conservar la base y el volumen existentes

Antes de actualizar, identifica el nombre real del volumen con `docker volume ls` y los valores vigentes de `POSTGRES_DB`, `POSTGRES_USER` y contraseña. Mantén esos valores en `.env`, incluido `POSTGRES_VOLUME`. Detén la instalación anterior con `docker compose down` sin `-v` y después inicia el código actualizado. No se recupera automáticamente un volumen anterior si se configura uno nuevo. El cambio de cookie requiere volver a iniciar sesión.

### Cambiar de base mediante respaldo y restauración

Esta alternativa necesita una base de destino vacía. En la instalación anterior:

```bash
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/respaldo.dump'
docker compose cp db:/tmp/respaldo.dump ./respaldo.dump
docker compose down
```

Conserva el respaldo y la instalación anterior. Configura el destino con una base y un volumen nuevos, inicia solo PostgreSQL y espera a que esté saludable:

```bash
docker compose up -d db
```

Copia `respaldo.dump` a la nueva carpeta del proyecto y restaura. Estos comandos asumen que la base y el usuario de destino son `finanzas`:

```bash
docker compose cp respaldo.dump db:/tmp/respaldo.dump
docker compose exec db pg_restore -U finanzas -d finanzas --no-owner --no-privileges /tmp/respaldo.dump
docker compose up -d --build
```

No continúes si la restauración falla. El destino debe estar libre de las tablas de la aplicación y el backend no debe iniciarse antes de restaurar. Esta ruta no elimina la instalación anterior y requiere adaptar los nombres si usas otros valores.
