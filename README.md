# Plataforma de Presupuesto

Aplicación para comparar el presupuesto estimado con los ingresos y egresos reales de una empresa a partir de archivos CSV. Centraliza las partidas por mes, categoría y moneda, señala desviaciones y permite explorar escenarios de gasto sin modificar los datos originales.

El proyecto utiliza **React, Python, FastAPI y PostgreSQL**. Power BI Embedded forma parte de la integración prevista y todavía no está configurado. El historial de cambios y las notas de actualización están en [CHANGELOG.md](CHANGELOG.md).

## Qué problema resuelve

La revisión de presupuestos en archivos separados dificulta identificar qué gastos excedieron lo previsto, qué ingresos quedaron por debajo de la meta y cuáles resultados siguen pendientes. La plataforma reúne esa información en una vista mensual y conserva el archivo de origen, las advertencias y el autor de cada importación.

Sus funciones actuales son:

- Importar y validar un formato definido de CSV empresarial antes de guardarlo.
- Consultar partidas, presupuestos, resultados reales y alertas mediante filtros de mes, categoría y moneda.
- Mostrar una estimación del gasto del mes siguiente al último periodo importado.
- Predecir el presupuesto asignado a egresos del siguiente mes mediante regresión lineal local, cuando existe un histórico suficiente.
- Simular ajustes de nómina, otros egresos e inflación sobre resultados completados.
- Administrar cuentas por roles, invitaciones por correo, activación y eliminación de usuarios.

La instalación está pensada para una empresa y una fuente de datos homogénea. No transforma cualquier CSV en una base de datos ni ofrece aislamiento multiempresa.

## Arquitectura

| Componente | Tecnología | Responsabilidad |
| --- | --- | --- |
| Interfaz | React y Vite | Navegación, filtros, formularios, dashboard y simulación |
| Servidor web | Nginx en Docker | Sirve el frontend compilado y redirige `/api/` al backend |
| API | Python 3.12 y FastAPI | Autenticación, permisos, validación, importaciones y cálculos |
| Persistencia | PostgreSQL 16 y SQLAlchemy | Usuarios, sesiones, invitaciones, archivos y partidas financieras |
| Envío de invitaciones | SMTP externo con TLS | Entrega los enlaces de activación cuando está configurado |

En Docker, el navegador accede a Nginx en el puerto 8080. Las peticiones `/api/` pasan al servicio `backend:8000`, que consulta `db:5432` en la red de Compose. PostgreSQL no publica un puerto en el equipo anfitrión y sus datos persisten en el volumen `postgres_data`, cuyo nombre se configura con `POSTGRES_VOLUME`.

En desarrollo sin contenedores, Vite sirve la interfaz en el puerto 5173 y redirige `/api` a `127.0.0.1:8000`. Si no se define `DATABASE_URL`, el backend utiliza SQLite para desarrollo y pruebas.

### Organización del código

| Ruta | Contenido |
| --- | --- |
| [frontend/src/main.jsx](frontend/src/main.jsx) | Montaje de React y estilos |
| [frontend/src/App.jsx](frontend/src/App.jsx) | Coordinación de sesión, navegación, filtros y acciones |
| [frontend/src/components](frontend/src/components) | `Dashboard`, `Importaciones`, `Login`, `BudgetForecast` y `BudgetTrendChart` |
| [frontend/src/services/api.js](frontend/src/services/api.js) | Cliente HTTP, cookies y manejo de errores |
| [frontend/src/utils/formatters.js](frontend/src/utils/formatters.js) | Formatos monetarios y de periodos |
| [frontend/src/Simulation.jsx](frontend/src/Simulation.jsx) | Simulación de escenarios |
| [frontend/src/Users.jsx](frontend/src/Users.jsx) | Invitación y eliminación de cuentas |
| [frontend/src/Activation.jsx](frontend/src/Activation.jsx) | Creación de contraseña mediante invitación |
| [backend/app/main.py](backend/app/main.py) | Composición de la aplicación, middleware y registro de routers |
| [backend/app/database.py](backend/app/database.py) | Base declarativa, conexión y dependencia de sesión SQLAlchemy |
| [backend/app/models.py](backend/app/models.py) | Los siete modelos persistentes, sin cambios de esquema |
| [backend/app/schemas.py](backend/app/schemas.py) | Contratos de entrada de sesión y cuentas |
| [backend/app/security.py](backend/app/security.py) | Hash de contraseñas, sesión actual y autorización por roles |
| [backend/app/routers](backend/app/routers) | Rutas de autenticación, usuarios y estado |
| [backend/app/financial.py](backend/app/financial.py) | Importaciones por partidas, indicadores y proyección de gasto real |
| [backend/app/forecast.py](backend/app/forecast.py) | Regresión lineal de presupuestos asignados, evaluación temporal y endpoint protegido |
| [backend/app/invitations.py](backend/app/invitations.py) | Envío, caducidad, reenvío y activación de invitaciones |
| [backend/tests](backend/tests) | Pruebas de API, aislamiento y pronóstico; configuración SQLite compartida |
| [frontend/tests/budgetForecast.test.js](frontend/tests/budgetForecast.test.js) | Pruebas de renderizado del pronóstico y continuidad del dashboard |
| [database](database) | Creación de estructura y actualización SQL de invitaciones |
| [examples](examples) | Archivos CSV de referencia |

## Instalación desde GitHub

Necesitas Git y Docker con el complemento Compose v2; en Windows puedes usar Docker Desktop. Mantén Docker activo antes de ejecutar los comandos. No necesitas instalar Python ni Node.js en el equipo si utilizas la instalación completa con Docker.

### 1. Clonar el repositorio

```bash
git clone https://github.com/Byakuya1403/G19X-TESE-LEMR-897-ACADEMIC.git plataforma_presupuesto
cd plataforma_presupuesto
```

El último argumento de `git clone` fija el nombre de la carpeta local; puede diferir del nombre del repositorio remoto. Los siguientes comandos se ejecutan desde esa carpeta, donde se encuentra `compose.yaml`.

### 2. Configurar el entorno

Copia [.env.example](.env.example) a `.env`.

PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Cambia `POSTGRES_PASSWORD` por una contraseña alfanumérica larga. Para probar las invitaciones en tu equipo sin configurar un servidor de correo, establece:

```dotenv
APP_PUBLIC_URL=http://localhost:8080
COOKIE_SECURE=false
INVITE_DELIVERY=manual
```

Conserva las demás variables del ejemplo. `.env` contiene la configuración privada y está excluido por `.gitignore`.

### 3. Iniciar los servicios

```bash
docker compose up -d --build
docker compose ps
```

| Recurso local | Dirección |
| --- | --- |
| Plataforma | [http://localhost:8080](http://localhost:8080) |
| Documentación interactiva de la API | [http://localhost:8000/docs](http://localhost:8000/docs) |
| Esquema OpenAPI | [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json) |
| Estado de la API | [http://localhost:8000/api/health](http://localhost:8000/api/health) |

Abre la dirección de la plataforma en el navegador. Abrir `frontend/index.html` con doble clic no ejecuta React ni el backend.

### 4. Crear el primer administrador

No existen usuarios ni contraseñas predeterminados. Crea la cuenta inicial desde la terminal:

```bash
docker compose exec backend python -m app.create_user administrador admin
```

Escribe y confirma una contraseña de 12 a 128 caracteres; no se muestra mientras la introduces. En la plataforma pulsa **Iniciar sesión** y utiliza `administrador` y esa contraseña.

Esta cuenta inicial utiliza un nombre de usuario, sin correo asociado. Para administrar con un correo, invita tu dirección desde **Usuarios**, selecciona **Administrador** y completa la activación. Esto crea una cuenta independiente: no modifica la inicial. Si deseas eliminar la cuenta inicial, primero inicia sesión con el nuevo administrador por correo.

## Configuración

| Variable | Uso y valor inicial |
| --- | --- |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL; obligatoria en Compose. Cambia el valor de ejemplo |
| `POSTGRES_DB` | Base de datos; `finanzas` |
| `POSTGRES_USER` | Rol de PostgreSQL; `finanzas` |
| `POSTGRES_VOLUME` | Volumen persistente; `presupuesto_postgres_data` |
| `APP_PUBLIC_URL` | Dirección base de los enlaces de activación, sin rutas ni parámetros |
| `COOKIE_SECURE` | `false` en localhost HTTP; `true` para publicación HTTPS |
| `INVITE_DELIVERY` | `smtp` por defecto; usa `manual` para generar enlaces sin correo |
| `SMTP_HOST`, `SMTP_FROM` | Servidor SMTP y dirección remitente |
| `SMTP_PORT`, `SMTP_SECURITY` | `587` y `starttls` por defecto; también se admite `ssl` con su puerto |
| `SMTP_USER`, `SMTP_PASSWORD` | Credenciales autorizadas por el proveedor SMTP, cuando sean necesarias |
| `DATABASE_URL` | Conexión del backend. Compose la construye con las variables de PostgreSQL; fuera de Docker puedes definirla directamente |

### Invitaciones por correo

Para enviar correos reales, configura los campos SMTP y cambia `INVITE_DELIVERY` a `smtp`. Ejemplo de estructura; sustituye los valores por los de tu servicio:

```dotenv
APP_PUBLIC_URL=https://presupuesto.tu-dominio.com
COOKIE_SECURE=true
INVITE_DELIVERY=smtp
SMTP_HOST=smtp.tu-proveedor.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_FROM=presupuesto@tu-dominio.com
SMTP_USER=usuario-autorizado
SMTP_PASSWORD=credencial-del-servicio
```

El cliente admite STARTTLS y TLS implícito (`SMTP_SECURITY=ssl`, normalmente puerto 465); no admite SMTP sin cifrado. Utiliza autenticación SMTP convencional: un proveedor que exija OAuth necesita una adaptación o un relay autorizado. La interfaz informa si el servidor aceptó el envío; eso no garantiza que el mensaje llegue a la bandeja principal.

La plataforma puede enviar correo aunque se ejecute localmente. Sin embargo, un enlace con `localhost` solo abre la plataforma en el equipo del destinatario: para otras personas debes configurar una dirección que realmente puedan alcanzar. El Compose incluido escucha únicamente en `127.0.0.1`; no configura dominio, certificados ni publicación externa. Cambiar `APP_PUBLIC_URL` no publica el sitio.

## Roles y permisos

| Perfil | Consulta | Acciones |
| --- | --- | --- |
| Visitante, sin sesión | Resumen con datos de demostración | Abrir el inicio de sesión |
| Administrador (`admin`) | Resumen de demostración y cuentas | Invitar, reenviar invitaciones y eliminar otros usuarios |
| Analista Financiero (`analyst`) | Datos reales, partidas, simulación y estado de Power BI | Validar e importar CSV y calcular escenarios |
| Director Financiero (`director`) | Datos reales, partidas, simulación y estado de Power BI | Calcular escenarios; no importa CSV desde la interfaz |

El rol administrativo no habilita por sí mismo el acceso a datos financieros reales. Los permisos se comprueban en el servidor. Los endpoints disponibles se detallan en la sección de API.

### Activar y eliminar cuentas

El administrador introduce correo y rol en **Usuarios**. En modo SMTP se envía la invitación; en modo manual se muestra un enlace privado que puede abrirse en una ventana de incógnito para probar. La cuenta permanece pendiente hasta que el destinatario define y confirma su contraseña.

El enlace caduca en 24 horas y es de un solo uso. Abrirlo o previsualizarlo no lo consume; confirmar la contraseña sí. Reenviar genera un enlace nuevo e invalida el anterior. Se almacena el hash del token, no el enlace original. Tras activarse, el usuario inicia sesión con su correo y la contraseña elegida. Si recarga la pantalla de activación, debe volver a abrir el enlace original porque el token se retira de la barra de dirección.

**Eliminar** requiere confirmación y borra la cuenta, sus sesiones, su correo y sus invitaciones. Conserva los archivos importados, presupuestos y partidas anteriores. No permite eliminar la propia cuenta administrativa y no ofrece deshacer dentro de la aplicación.

## Uso de la plataforma

### Importar partidas desde CSV

Inicia sesión como Analista y abre **Importaciones**:

1. Selecciona la moneda real del archivo; no se detecta automáticamente.
2. Selecciona el CSV y, únicamente si corresponde, confirma la reparación de columnas desplazadas.
3. Pulsa **Validar y previsualizar** y revisa filas, advertencias y resultados pendientes.
4. Confirma la importación. Se guardan todas las partidas en una transacción y se selecciona el último periodo del archivo.

El ejemplo [presupuesto_empresarial_2026.csv](examples/presupuesto_empresarial_2026.csv) contiene 36 partidas de enero a marzo de 2026. Los registros 132–136 tienen las columnas de texto desplazadas y requieren confirmar su reparación. Los registros de marzo están pendientes.

El contrato aceptado es CSV UTF-8, separado por comas, con importes de hasta dos decimales y punto decimal, sin separadores de miles. El límite es 2 MB y 10 000 partidas. Debe contener exactamente estas columnas, sin columnas adicionales; su orden puede variar:

```text
ID_Registro,Anio,Mes,Categoria,Subcategoria,Concepto,Presupuesto_Estimado,Gasto_Real,Diferencia_Varianza,Porcentaje_Ejecucion,Estado
```

Reglas de interpretación:

- `Mes` utiliza nombres de meses en español; los periodos se ordenan por año y mes.
- `Categoria=Ingresos` representa ingresos; las demás categorías representan egresos. Confirma que esta regla corresponda a tu fuente.
- `Subcategoria=Nómina` identifica nómina para simular; los demás egresos se consideran operación. No se deducen departamentos.
- `Estado=Pendiente` requiere `Gasto_Real=0` y se guarda como resultado desconocido (`NULL`). `Completado` con importe cero sí representa un cero conocido.
- Se rechazan importes negativos, valores no finitos, varianzas inconsistentes, porcentajes que no corresponden a los importes y duplicados por ID/año dentro del archivo.
- Un archivo ya importado se rechaza por su hash. También se rechazan conflictos de año/ID/moneda con partidas existentes; no se sobrescriben ni se guardan filas parciales.

La varianza recibida debe coincidir con presupuesto menos gasto real; los porcentajes se validan contra los importes. La plataforma recalcula esos valores al consultar y conserva la fila original como JSON. No se admiten XLSX, movimientos contables arbitrarios ni mapeo automático entre formatos.

### Consultar resultados y proyección

**Resumen** muestra únicamente el mes seleccionado, sus categorías, cuatro indicadores de ingresos/egresos presupuestados y reales, resultado del periodo y alertas. **Presupuestos** contiene el detalle por concepto. Los filtros de categoría y moneda acotan la consulta; no se suman monedas diferentes. Si hay partidas pendientes, el total real del grupo se muestra pendiente y se informa por separado lo conocido.

La proyección estima egresos para el mes siguiente al máximo periodo importado de la moneda seleccionada, incluso al cambiar de año. El filtro del mes que estás consultando no modifica ese horizonte. Se calcula la media de hasta tres meses con resultados de egresos completos para la selección; no convierte pendientes en ceros. Es una referencia estadística, no un modelo de IA entrenado o validado. Cambios de cobertura entre meses pueden afectar su interpretación.

### Predicción inteligente de presupuesto

Esta sección adicional de **Resumen** predice el **presupuesto de egresos asignado**, usando `financial_entries.budget` (columna `Presupuesto_Estimado` del CSV). No utiliza `actual`/`Gasto_Real` como objetivo y no suma ingresos con egresos. Conserva todos los paneles existentes, incluida la proyección estadística de gasto real descrita arriba; son dos cálculos distintos.

**Periodo y filtros.** El mes seleccionado es el mes base y el objetivo es su mes siguiente, incluso al cambiar de año. Solo se utilizan registros de meses anteriores al objetivo. Moneda y categoría provienen de los filtros actuales; no se convierten ni mezclan monedas. Con una categoría de ingresos no se genera este pronóstico de egresos. La tarjeta muestra el archivo analizado, el periodo objetivo, el presupuesto base, el importe estimado, la variación porcentual, el modelo, los meses analizados y el MAE cuando puede evaluarse.

**Conjuntos de datos.** La relación de origen disponible es `Entry.batch_id → ImportBatch.id`. No existe un identificador que permita demostrar que archivos separados pertenecen a la misma serie. Por eso cada importación se analiza independientemente. Con un único archivo elegible se selecciona automáticamente; con varios aparece un selector dentro de la nueva sección, sin alterar los filtros ni los indicadores del resto del resumen. La API nunca suma esas importaciones para entrenar. Un archivo debe contener por sí mismo el histórico necesario. Varios archivos con un solo mes no forman automáticamente una serie; el proyecto todavía no tiene actualización o unión de importaciones por identidad de origen.

**Requisitos de los datos.** Se requieren al menos seis meses consecutivos y se analizan como máximo los últimos 24 meses hasta el periodo base. Todas las partidas de egresos de ese intervalo deben estar `Completado` y tener la misma cobertura mensual: categoría, subcategoría, concepto y cantidad de partidas por combinación. Los ID de registro pueden variar entre meses. Son condiciones conservadoras para reducir cambios de cobertura y meses parciales; **no certifican un cierre contable**, porque ese dato no existe en el modelo actual. El presupuesto ya es conocido aunque un resultado esté pendiente, pero esta primera versión no publica un pronóstico con ese histórico pendiente.

No se rellenan meses ausentes con ceros. Se cuenta una sola vez la misma fila de origen; un duplicado con valores inconsistentes invalida la serie. No se usan la tabla histórica `budgets`, datos de demostración ni servicios externos. El CSV de ejemplo tiene tres meses y partidas pendientes: permite verificar el mensaje de no disponibilidad, pero no un entrenamiento suficiente. No se agregan datos de prueba a la plataforma para producir una cifra.

**Modelo y evaluación.** `scikit-learn` ajusta `LinearRegression` sobre el número de mes transcurrido y la suma mensual de presupuestos. Se evalúan los tres últimos meses mediante origen móvil: para cada mes evaluado se entrena exclusivamente con los anteriores. El MAE se compara con la referencia de repetir el presupuesto del mes previo. Después de evaluar se reentrena con todo el intervalo elegible para predecir su mes siguiente.

El criterio de publicación actual rechaza una regresión cuyo MAE supere al de la referencia por más de un centavo o supere el máximo entre un centavo y el 30% del presupuesto medio de los meses de validación. El umbral es una **política inicial de elegibilidad**, no un porcentaje de precisión ni una garantía calibrada para una empresa. No se calcula ni presenta R² como confianza. La regresión no modela estacionalidad. Las métricas históricas no garantizan resultados futuros.

Se redondean importes a dos decimales. Una salida no finita se rechaza; una tendencia negativa se limita a cero y se informa explícitamente. Si el presupuesto base es cero, la variación porcentual se devuelve como `null`, sin división por cero. El presupuesto base mostrado corresponde al último mes elegible del intervalo, que debe coincidir con el periodo seleccionado.

**Gráfica y actualización.** La gráfica SVG añade histórico registrado y un segmento discontinuo con rombo para la estimación. Incluye títulos con valores exactos, leyenda y tabla accesible; con una serie no elegible solo muestra registros existentes. No había biblioteca de gráficas en el proyecto, por lo que no se añadió otra dependencia de frontend. El servidor consulta y entrena con los datos persistidos en cada petición, sin caché de predicciones. La sección vuelve a consultar al cambiar filtros, elegir importación o actualizar los datos de Resumen; las respuestas anteriores canceladas no sustituyen una selección nueva.

**Referencia técnica:** [LinearRegression](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LinearRegression.html), [MAE](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_absolute_error.html) y [evaluación de series temporales](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split), documentación oficial de scikit-learn.

### Simular escenarios

En **Simulación**, revisa la base real del mes y categoría, define los porcentajes y compara el resultado. Los ajustes permitidos son nómina de −30% a +30%, otros egresos de −50% a +50% y precios/inflación de −10% a +30%.

La fórmula es `nómina × (1 + ajuste salarial) + otros egresos × (1 + ajuste operativo) × (1 + inflación)`, expresando los porcentajes como fracciones. Los dos ajustes sobre otros egresos se acumulan de forma multiplicativa. Se rechazan selecciones con egresos pendientes o sin gastos. Calcular no modifica el CSV ni guarda cambios en el presupuesto; tampoco constituye la proyección del siguiente mes.

## API y endpoints

La API utiliza el prefijo `/api`. El frontend envía la cookie de sesión HttpOnly `finanzas_session` y el encabezado `X-App: 1` en las peticiones. Los endpoints protegidos que modifican datos, login, logout y activación comprueban ese encabezado. La sesión tiene una vigencia de ocho horas. Los límites de intentos actuales se aplican por proceso.

Consulta los detalles de parámetros y esquemas disponibles en [Swagger UI](http://localhost:8000/docs). Algunos endpoints financieros reciben un objeto JSON genérico; se describen sus campos debajo de la tabla.

### Sesión y cuentas

| Método | Endpoint | Acceso | Función |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | Público | Inicia sesión con `username` (correo o usuario anterior) y `password` |
| GET | `/api/auth/me` | Público | Devuelve la cuenta de la sesión o `null` |
| POST | `/api/auth/logout` | Público | Invalida la sesión actual |
| POST | `/api/auth/invitation/validate` | Poseedor del enlace | Comprueba `token` sin consumirlo |
| POST | `/api/auth/activate` | Poseedor del enlace | Recibe `token`, `password` y `confirmation`; activa la cuenta |
| GET | `/api/users` | Administrador | Lista cuentas y estados de activación |
| GET | `/api/users/invitation-settings` | Administrador | Informa el modo y la configuración de invitaciones |
| POST | `/api/users/invitations` | Administrador | Invita mediante JSON con `email` y `role` |
| POST | `/api/users/{user_id}/invitation` | Administrador | Reenvía o regenera una invitación pendiente |
| DELETE | `/api/users/{user_id}` | Administrador | Elimina otra cuenta y sus accesos asociados |
| POST | `/api/users` | Administrador | Compatibilidad: crea cuenta con `username`, `password` y `role`; la interfaz actual utiliza invitaciones |

### Finanzas por partidas

| Método | Endpoint | Acceso | Función |
| --- | --- | --- | --- |
| POST | `/api/financial/imports/preview` | Analista | Previsualiza multipart con `file` y `repair_shifted` opcional |
| POST | `/api/financial/imports/csv` | Analista | Importa multipart con `file`, `currency` y `repair_shifted` opcional |
| GET | `/api/financial/entries` | Público con demostración; financiero con datos reales | Lista partidas con periodo, categoría, concepto e importes |
| GET | `/api/financial/dashboard` | Público con demostración; financiero con datos reales | Recibe `period=YYYY-MM`, `currency` (MXN por defecto) y `category` opcional |
| POST | `/api/financial/simulations` | Director o Analista | Calcula el escenario sobre egresos completados |

El JSON de simulación requiere `period` y `currency`; acepta `department` como nombre del filtro de **categoría** por compatibilidad, además de `payroll`, `operating` e `inflation` como porcentajes (cero por defecto). No envíes `category` en ese endpoint esperando que filtre.

### Pronóstico de presupuesto

| Método | Endpoint | Acceso | Función |
| --- | --- | --- | --- |
| GET | `/api/forecast/budget` | Director o Analista | Predice presupuesto de egresos a partir de una sola importación real |

Parámetros de consulta:

| Parámetro | Uso |
| --- | --- |
| `currency` | Código de tres letras mayúsculas; `MXN` por defecto |
| `category` | Categoría exacta opcional; si se omite, suma las categorías de egresos de esa importación |
| `period` | Mes base `YYYY-MM`, entre 1900 y 9999. Si se omite, toma el máximo periodo de la selección |
| `batch_id` | ID de importación opcional. Es necesario seleccionar uno si hay varios conjuntos elegibles |

Una respuesta 200 puede tener `disponible: false` por histórico insuficiente, meses pendientes o ausentes, cobertura variable, mala evaluación o selección ambigua. En esos casos `presupuesto_estimado` es `null` y `codigo`/`mensaje` explican el motivo. `conjuntos_disponibles` enumera los archivos que pueden seleccionarse. Una importación inexistente produce 404; filtros inválidos producen 422; sin sesión devuelve 401 y un administrador sin rol financiero recibe 403. El endpoint no devuelve datos sintéticos ni crea sesiones.

La respuesta incluye `periodo_pronosticado`, `presupuesto_actual`, `presupuesto_estimado`, `variacion_porcentual`, `modelo`, `meses_analizados`, `periodo_base`, `moneda`, `batch_id`, `historial`, `evaluacion` y advertencias. Su esquema completo está en Swagger UI. No se incluye un ejemplo numérico como si fuera una predicción de los datos existentes.

### Estado e integración

| Método | Endpoint | Acceso | Función |
| --- | --- | --- | --- |
| GET | `/api/health` | Público | Estado de la API |
| GET | `/api/powerbi/status` | Público | Informa que Power BI no está configurado |

### API financiera vigente

La interfaz utiliza únicamente `/api/financial/*`. Los endpoints financieros del formato anterior fueron retirados y ya no aparecen en OpenAPI. Sus URL devuelven 404. El detalle de la retirada está en [CHANGELOG.md](CHANGELOG.md).

La tabla histórica `budgets` se conserva en la base, sin rutas de acceso en esta API, para evitar borrar datos existentes. No se mezcla con `financial_entries`. Esta actualización no ejecuta `DROP TABLE` ni migra sus registros automáticamente.

Los errores habituales son 401 (sin sesión), 403 (sin permiso o encabezado requerido), 404 (sin recurso/datos), 409 (conflicto), 413 (archivo demasiado grande), 422 (validación), 429 (límite de intentos), 502 (SMTP rechazado) y 503 (configuración de invitaciones incompleta).

## Base de datos y scripts SQL

La aplicación crea las tablas faltantes al arrancar: `users`, `login_sessions`, `user_emails`, `user_invitations`, `financial_imports`, `financial_entries` y `budgets`. Este mecanismo no sustituye un sistema de migraciones para modificar columnas existentes.

[database/crear_base_datos.sql](database/crear_base_datos.sql) contiene la estructura PostgreSQL y las vistas `v_partidas_presupuesto` y `v_resumen_partidas`, útiles para consultas e integración posterior con reportes. Las vistas requieren ejecutar el SQL; las tablas pueden crearse desde el arranque de la API.

Con los nombres predeterminados `finanzas`, ejecuta desde la raíz del repositorio:

```bash
docker compose cp database/crear_base_datos.sql db:/tmp/crear_base_datos.sql
docker compose exec db psql -U finanzas -d postgres -v ON_ERROR_STOP=1 -f /tmp/crear_base_datos.sql
```

El script contiene comandos propios de `psql`, crea la base `finanzas` si no existe y se conecta a ella. Si usas otra base o rol, adapta también el script; cambiar solo `-U` no cambia la base definida dentro. En pgAdmin crea o selecciona la base correcta y ejecuta únicamente el bloque `BEGIN`–`COMMIT`.

[database/009_invitaciones.sql](database/009_invitaciones.sql) agrega las dos tablas de invitaciones a una base existente. Las notas históricas de actualización están en [CHANGELOG.md](CHANGELOG.md).

## Desarrollo y comprobaciones

Para trabajar sin contenedores necesitas Python 3.12 y Node.js 22 como referencias de los Dockerfiles. Desde la raíz, crea un entorno virtual:

```bash
python -m venv .venv
```

Actívalo con `.venv\Scripts\Activate.ps1` en PowerShell o `source .venv/bin/activate` en Linux/macOS. Antes de iniciar el backend, configura `APP_PUBLIC_URL=http://localhost:5173` e `INVITE_DELIVERY=manual` en `.env` para probar invitaciones en Vite. Después:

```bash
cd backend
python -m pip install -r requirements.txt
python -m app.create_user administrador admin
uvicorn app.main:app --reload --env-file ../.env
```

El comando de creación de usuario y Uvicorn deben usar la misma `DATABASE_URL`, definida en el entorno antes de ambos comandos si deseas PostgreSQL; sin ella ambos utilizan SQLite en la carpeta backend. El módulo `create_user` no lee `.env` automáticamente. Las variables `POSTGRES_*` de `.env` tampoco construyen por sí solas `DATABASE_URL` fuera de Compose. No crees otra vez el administrador si ya existe.

En otra terminal, desde la raíz:

```bash
cd frontend
npm ci
npm run dev
```

Abre [http://localhost:5173](http://localhost:5173). Las variables de correo se cargan mediante `--env-file` al arrancar Uvicorn.

Comandos de comprobación, ejecutados en las carpetas indicadas:

| Carpeta | Comando | Propósito |
| --- | --- | --- |
| `frontend` | `npm run build` | Compilar la interfaz |
| `frontend` | `npm run format:check` | Comprobar formato del JavaScript/JSX |
| `frontend` | `npm run format` | Aplicar Prettier |
| `frontend` | `npm test` | Comprobar estados del pronóstico, gráfica y continuidad de los paneles |
| `backend` | `python -m pytest -q` | Ejecutar pruebas de API con SQLite |

Las verificaciones realizadas por entrega y sus límites están documentados en [CHANGELOG.md](CHANGELOG.md). Las pruebas con SQLite no sustituyen la validación de PostgreSQL, concurrencia y envío real de correo.

## Actualizar, respaldar y detener

En una copia clonada, conserva `.env` y los valores de base, usuario y volumen vigentes. Con el árbol de trabajo preparado para actualizar:

```bash
git pull --ff-only
docker compose up -d --build
```

Comprueba los cambios de configuración y migraciones descritos en [CHANGELOG.md](CHANGELOG.md). No necesitas reimportar los mismos archivos para actualizar el código.

Para generar un respaldo con las credenciales del contenedor:

```bash
docker compose exec db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/presupuesto.dump'
docker compose cp db:/tmp/presupuesto.dump ./presupuesto.dump
```

Guarda el respaldo fuera del repositorio. Para detener los servicios conservando datos utiliza `docker compose down`. No agregues `-v` si quieres conservar el volumen. Cambiar `POSTGRES_DB`, `POSTGRES_USER` o `POSTGRES_VOLUME` no renombra ni migra una base existente; consulta las notas de migración en el changelog.

Si un servicio falla, revisa `docker compose ps` y `docker compose logs backend db frontend`. En Usuarios, un aviso de SMTP incompleto impide invitar por correo hasta configurar el envío o seleccionar modo manual.

## Alcance actual

Power BI Embedded, recuperación de contraseñas, asociación de correos a cuentas anteriores, auditoría completa y cierre/aprobación mensual están pendientes. La proyección de gasto real conserva su media estadística; el pronóstico de presupuesto usa regresión lineal con evaluación temporal cuando la serie es elegible. El cierre mensual formal y la validación del modelo con datos representativos de cada empresa siguen pendientes. La solución no ofrece carga universal de CSV ni aislamiento multiempresa.

La publicación para usuarios remotos requiere una configuración de HTTPS, acceso de red y correo distinta de la instalación local incluida. Los límites de intentos son por proceso y requieren almacenamiento compartido antes de escalar a varios servidores.


## Verificar la predicción de presupuesto

La única dependencia directa nueva es `scikit-learn>=1.5,<2` en `backend/requirements.txt`; instala sus dependencias numéricas transitivas. La implementación se comprobó con scikit-learn 1.9.1. No hay cambios de tablas ni migraciones SQL y no se requieren claves de IA.

1. Conserva `.env`, base y volumen. Actualiza el código y ejecuta `docker compose up -d --build` para instalar scikit-learn y compilar la interfaz. No vuelvas a importar un archivo ya guardado.
2. Inicia sesión como Director o Analista y entra a Resumen. Con el ejemplo existente debes ver un mensaje informativo, porque tres meses con pendientes no cumplen los criterios.
3. Para obtener una cifra, importa como Analista un histórico **real** de al menos seis meses consecutivos, con partidas completadas y cobertura comparable dentro del mismo archivo. Selecciona el último mes de ese histórico y su moneda/categoría. Si hay varios archivos, elige uno en la nueva tarjeta. No cambies ID de archivos existentes para forzar una unión entre conjuntos.
4. Comprueba que el periodo objetivo sea el mes siguiente, que el presupuesto base coincida con las partidas asignadas y que el punto estimado esté separado visualmente de los valores registrados. Cambiar a un periodo anterior debe excluir todos los datos posteriores de este nuevo pronóstico.
5. Puedes comprobar la respuesta en Swagger, con una sesión financiera iniciada en el navegador usando el mismo host (`localhost`, sin alternar con `127.0.0.1`). Las pruebas automáticas no requieren un histórico real ni un servidor de correo y utilizan exclusivamente fixtures aisladas.

Desde `backend`, con las dependencias instaladas:

```bash
python -m pytest -q
```

Desde `frontend`:

```bash
npm ci
npm test
npm run build
npm run format:check
```

La verificación de esta entrega incluye 49 pruebas de backend con SQLite y seis pruebas de renderizado de frontend. No sustituye pruebas Docker/PostgreSQL, revisión visual en navegador ni evaluación financiera con datos de producción. El código de login, roles, modelos SQL, importación y Simulación se comparó con la entrega anterior y permanece sin cambios.

### Archivos de la entrega de IA

| Acción | Archivos | Propósito |
| --- | --- | --- |
| Creados | `backend/app/forecast.py` | Agregación, elegibilidad, regresión, evaluación y endpoint |
| Creados | `frontend/src/components/BudgetForecast.jsx`, `frontend/src/components/BudgetTrendChart.jsx` | Consulta, estados de la tarjeta y gráfica |
| Creados | `backend/tests/conftest.py`, `backend/tests/test_forecast.py`, `frontend/tests/budgetForecast.test.js` | Fixtures aisladas y pruebas automáticas |
| Modificados | `backend/app/main.py`, `backend/requirements.txt` | Registro del router, versión e instalación de scikit-learn |
| Modificados | `frontend/src/components/Dashboard.jsx`, `frontend/src/styles.css` | Integración visual adicional |
| Modificados | `frontend/package.json`, `frontend/src/App.jsx` | Comando de pruebas e indicador de versión |
| Modificados | `backend/tests/test_api.py` | Reutilización de la fixture común; conserva las pruebas existentes |
| Modificados | `README.md`, `CHANGELOG.md` | Funcionamiento, límites, actualización y verificación |
