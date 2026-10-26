# Plataforma de Presupuesto

Aplicación para comparar el presupuesto estimado con los ingresos y egresos reales de una empresa a partir de archivos CSV. Centraliza las partidas por mes, categoría y moneda, señala desviaciones y permite explorar escenarios de gasto sin modificar los datos originales.

El proyecto utiliza **React, Python, FastAPI y PostgreSQL**. **Power BI Embedded queda fuera del alcance de esta entrega por la limitación de tiempo disponible.** Su integración podrá evaluarse en una fase posterior. El historial de cambios y las notas de actualización están en [CHANGELOG.md](CHANGELOG.md).

## Desarrollo asistido por IA

Durante el desarrollo de este proyecto se utilizó **ChatGPT/Codex de OpenAI** como asistente de programación para implementar y refactorizar componentes del frontend y del backend, preparar pruebas automatizadas y redactar documentación.

Esta asistencia forma parte del proceso de desarrollo. La predicción de presupuestos de la plataforma se ejecuta localmente mediante modelos de **scikit-learn**, como se describe en la sección de predicción inteligente.

## Qué problema resuelve

La revisión de presupuestos en archivos separados dificulta identificar qué gastos excedieron lo previsto, qué ingresos quedaron por debajo de la meta y cuáles resultados siguen pendientes. La plataforma reúne esa información en una vista mensual y conserva el archivo de origen, las advertencias y el autor de cada importación.

Sus funciones actuales son:

- Importar y validar un formato definido de CSV empresarial antes de guardarlo.
- Consultar partidas, presupuestos, resultados reales y alertas mediante filtros de mes, categoría y moneda.
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
| Analista Financiero (`analyst`) | Datos reales, partidas y simulación | Validar e importar CSV y calcular escenarios |
| Director Financiero (`director`) | Datos reales, partidas y simulación | Calcular escenarios; no importa CSV desde la interfaz |

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

### Eliminar una carga incorrecta

En **Importaciones → Importaciones guardadas**, el analista ve las cargas del espacio financiero compartido, con ID, nombre, moneda, periodos, número de partidas y usuario que las importó. El listado se pagina de 25 en 25 y permite actualizarlo. La gestión corresponde al rol que ya puede importar; director, administrador y visitante no reciben este permiso.

Pulsa **Eliminar carga**, comprueba el ID y los datos del archivo, escribe `ELIMINAR N` (N es su ID) y pulsa **Eliminar definitivamente**. Cancelar o cerrar el diálogo no envía una eliminación. El backend también valida la confirmación exacta, la sesión, el rol, `X-App: 1` y la huella `sha256` de la carga seleccionada; no depende solo del botón deshabilitado.

Se borran la fila de `financial_imports` y sus `financial_entries` dentro de una transacción, bloqueando la carga durante la eliminación en PostgreSQL. Una excepción revierte toda la operación. Los demás archivos y sus partidas se conservan. No hay restauración desde la interfaz; conserva tu archivo fuente si necesitas volver a cargarlo.

Al terminar se actualizan listado y datos financieros. El forecast se vuelve a calcular con las partidas restantes; si quedan pocos meses o huecos puede pasar a no disponible. El filtro de periodo puede seguir apuntando a un mes que quedó vacío: selecciona otro periodo o importa el definitivo. Al retirar la carga se liberan su hash y sus claves de origen, por lo que puedes importar el archivo corregido sin los conflictos de esa carga eliminada; las claves que pertenezcan a otras cargas siguen protegidas.

### Consultar resultados y proyección

**Resumen** muestra únicamente el mes seleccionado, sus categorías, cuatro indicadores de ingresos/egresos presupuestados y reales, resultado del periodo y alertas. **Presupuestos** contiene el detalle por concepto. Los filtros de categoría y moneda acotan la consulta; no se suman monedas diferentes. Si hay partidas pendientes, el total real del grupo se muestra pendiente y se informa por separado lo conocido.

La **predicción de presupuesto utiliza `LinearRegression` de scikit-learn** en `forecast.py`, a través de `/api/forecast/budget`. Aprende de los presupuestos asignados guardados en la base de datos. La tarjeta verde y el detalle con gráfica comparten el mismo resultado.

### Predicción inteligente de presupuesto

Esta sección adicional de **Resumen** predice el **presupuesto de egresos asignado**, usando `financial_entries.budget` (columna `Presupuesto_Estimado` del CSV). No utiliza `actual`/`Gasto_Real` como objetivo y no suma ingresos con egresos. La tarjeta principal y el detalle con gráfica consumen una única consulta al endpoint de forecast; se mantienen presupuestos mensuales, indicadores y alertas.

**Periodo y filtros.** El mes seleccionado es el mes base y el objetivo es su mes siguiente, incluso al cambiar de año. Solo se utilizan registros de meses anteriores al objetivo. Moneda y categoría provienen de los filtros actuales; no se convierten ni mezclan monedas. Con una categoría de ingresos no se genera este pronóstico de egresos. La tarjeta muestra el origen en base de datos, las cantidades de partidas e importaciones analizadas, el periodo objetivo, el presupuesto base, el importe estimado, la variación porcentual, el modelo, los meses analizados y el MAE cuando puede evaluarse.

**Persistencia e histórico acumulado.** Al confirmar una carga, el importador guarda las partidas en `financial_entries` y su procedencia en `financial_imports`, dentro de una transacción. El forecast consulta esas filas con SQLAlchemy a través de `DATABASE_URL` (PostgreSQL en Docker); no abre archivos CSV, no recibe sus contenidos ni depende de conservarlos. La previsualización por sí sola no guarda partidas.

Todas las importaciones de esta instalación aportan al mismo espacio financiero, como ya ocurre en los indicadores de Resumen. `batch_id` identifica la procedencia de una fila y no separa series del modelo. Puedes cargar enero en un archivo y febrero en otro, o repartir partidas del mismo mes entre archivos: se suman los presupuestos de las partidas distintas, se ordenan por año/mes y se aplican los filtros actuales. No existe selector de CSV ni parámetro `batch_id` en el forecast.

La clave existente `año + ID_Registro + moneda` evita repetir partidas; el hash evita importar de nuevo el mismo archivo. Un conflicto rechaza toda la nueva carga, sin sobrescribir datos ni insertar filas parciales. Los ID deben identificar establemente cada partida y ser distintos para partidas legítimamente diferentes dentro del mismo año/moneda, incluso entre archivos. No reinicies la numeración por archivo ni cambies ID para volver a cargar una partida existente: un duplicado con otro ID no se puede reconocer con certeza. Para corregir una carga completa, elimínala desde Importaciones y luego importa el archivo definitivo. No se editan ni sobrescriben filas de forma individual.

El modelo actual no tiene entidad empresa o unidad contable: esta acumulación es para **un mismo espacio financiero**, no una separación automática de empresas. No cargues presupuestos de empresas independientes en una instalación esperando que el nombre del archivo las separe. Los filtros siguen separando monedas y categorías, y los ingresos no se mezclan con egresos. No se crean tablas ni se requiere migración SQL.

**Requisitos de los datos.** Se requieren al menos seis meses consecutivos con importes de presupuesto válidos y se analizan como máximo los últimos 24 meses hasta el periodo base. El modelo aprende la suma mensual de egresos. Los conceptos, las categorías y el número de partidas pueden variar: no se exige que coincidan literalmente entre meses. Si cambia la composición se devuelve `composicion_variable=true` y una advertencia para comprobar el ámbito y la integridad de las cargas, sin bloquear automáticamente el cálculo. El cambio de composición puede ser legítimo o deberse a un archivo incompleto; la plataforma no puede distinguirlo de forma concluyente con los campos actuales. Las partidas registradas no certifican un cierre mensual.

**`Estado=Pendiente` y `Gasto_Real=NULL` no bloquean el forecast:** describen la ejecución del gasto, mientras que el presupuesto asignado ya está registrado. Se utiliza ese presupuesto sin inventar ni completar el gasto real. La comparación se realiza contra el presupuesto asignado del mes base. La continuidad mensual, los importes válidos y la evaluación temporal siguen siendo requisitos; no se fuerza una estimación cuando el modelo falla esos controles.

No se rellenan meses ausentes con ceros. Se cuenta una sola vez la misma fila de origen; un duplicado con valores inconsistentes invalida la serie. No se usan la tabla histórica `budgets`, datos de demostración ni servicios externos. El ejemplo breve [presupuesto_empresarial_2026.csv](examples/presupuesto_empresarial_2026.csv) tiene tres meses y permite verificar el mensaje de histórico insuficiente; sus gastos pendientes no son un motivo de exclusión del forecast. El nuevo ejemplo [presupuesto_historico_completo_2024_2026-v4.csv](examples/presupuesto_historico_completo_2024_2026-v4.csv) contiene 792 registros de 36 meses, de enero de 2024 a diciembre de 2026, para probar la predicción con un histórico suficiente. Son datos sintéticos generados con Gemini de Google, identificado en la interfaz como «3.6 Flash», según la captura de la conversación de generación proporcionada por el autor del proyecto; no representan operaciones reales de una empresa. Los ejemplos se importan de forma explícita y no se cargan automáticamente en la plataforma.

**Modelo y evaluación.** Se mantiene `LinearRegression` de scikit-learn y se ajusta sobre la suma mensual de presupuestos asignados. Con seis a 23 meses se utiliza una tendencia lineal. Con 24 meses consecutivos se comparan dos configuraciones: tendencia y tendencia con once indicadores del mes del año (enero es la referencia). La segunda permite representar patrones anuales, como importes mayores en ciertos meses; no aprende el gasto real ni utiliza servicios externos.

La configuración se selecciona antes de la evaluación final: con una ventana de 24 meses, ambas se prueban en los meses 19–21, entrenando cada vez solo con los anteriores. Se elige la estacional únicamente si reduce ese MAE en más de un centavo; en un empate se conserva la tendencia simple. La configuración elegida se evalúa por origen móvil en los meses 22–24, que no participaron en la selección. El entrenamiento final usa los 24 meses para estimar el siguiente. Con ventanas más cortas se mantiene la evaluación de los tres últimos meses, sin selección estacional. Este procedimiento evita elegir la configuración con el mismo bloque usado para informar su MAE final.

El criterio de publicación rechaza un MAE que supere el máximo entre un centavo y el 30% del presupuesto medio de los meses de evaluación. Es una **política inicial de elegibilidad**, no un porcentaje de precisión ni una garantía calibrada para una empresa. La referencia de repetir el presupuesto anterior sigue calculándose: si tiene menor MAE, `supera_referencia=false` y se muestra una advertencia explícita junto a ambos errores, sin ocultar automáticamente una estimación de error moderado. La estimación siempre sigue siendo la regresión entrenada; no se sustituye por la referencia para presentarla como IA.

No se calcula ni presenta R² como confianza. Los patrones anuales pueden cambiar y el error histórico no garantiza resultados futuros. Las validaciones de importes, continuidad mensual, mínimo histórico, filtros, no negatividad y corte temporal se mantienen.

Se redondean importes a dos decimales. Una salida no finita se rechaza; una tendencia negativa se limita a cero y se informa explícitamente. Si el presupuesto base es cero, la variación porcentual se devuelve como `null`, sin división por cero. El presupuesto base mostrado corresponde al último mes elegible del intervalo, que debe coincidir con el periodo seleccionado.

**Gráfica y actualización.** La gráfica SVG añade histórico registrado y un segmento discontinuo con rombo para la estimación. Incluye títulos con valores exactos, leyenda y tabla accesible; con una serie no elegible solo muestra registros existentes. No había biblioteca de gráficas en el proyecto, por lo que no se añadió otra dependencia de frontend. El servidor consulta y entrena con los datos persistidos en cada petición, sin caché de predicciones. La sección vuelve a consultar al cambiar filtros o actualizar los datos de Resumen después de importar o eliminar cargas; las respuestas anteriores canceladas no sustituyen una selección nueva.

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
| GET | `/api/financial/imports` | Analista | Lista cargas por ID descendente, con `limit` (1–100, 25 por defecto) y `offset` (desde 0) |
| DELETE | `/api/financial/imports/{batch_id}` | Analista | Elimina una carga y sus partidas; requiere JSON `confirmation` con el texto exacto `ELIMINAR {batch_id}` y `sha256` recibido en el listado |
| GET | `/api/financial/entries` | Público con demostración; financiero con datos reales | Lista partidas con periodo, categoría, concepto e importes |
| GET | `/api/financial/dashboard` | Público con demostración; financiero con datos reales | Recibe `period=YYYY-MM`, `currency` (MXN por defecto) y `category` opcional |
| POST | `/api/financial/simulations` | Director o Analista | Calcula el escenario sobre egresos completados |

El JSON de simulación requiere `period` y `currency`; acepta `department` como nombre del filtro de **categoría** por compatibilidad, además de `payroll`, `operating` e `inflation` como porcentajes (cero por defecto). No envíes `category` en ese endpoint esperando que filtre.

### Pronóstico de presupuesto

| Método | Endpoint | Acceso | Función |
| --- | --- | --- | --- |
| GET | `/api/forecast/budget` | Director o Analista | Predice presupuesto de egresos sobre el histórico acumulado en la base de datos |

Parámetros de consulta:

| Parámetro | Uso |
| --- | --- |
| `currency` | Código de tres letras mayúsculas; `MXN` por defecto |
| `category` | Categoría exacta opcional; si se omite, suma las categorías de egresos almacenadas |
| `period` | Mes base `YYYY-MM`, entre 1900 y 9999. Si se omite, toma el máximo periodo de la selección |

Una respuesta 200 puede tener `disponible: false` por histórico insuficiente, meses ausentes, presupuestos inválidos o mala evaluación. En esos casos `presupuesto_estimado` es `null` y `codigo`/`mensaje` explican el motivo. No es necesario elegir un archivo. Los filtros inválidos producen 422; sin sesión devuelve 401 y un administrador sin rol financiero recibe 403. El endpoint no devuelve datos sintéticos ni crea sesiones.

La respuesta incluye `periodo_pronosticado`, `presupuesto_actual`, `presupuesto_estimado`, `variacion_porcentual`, `modelo`, `configuracion`, `descripcion_modelo`, `seleccion_modelo`, `meses_analizados`, `periodo_base`, `moneda`, `origen`, `registros_analizados`, `importaciones_analizadas`, `historial`, `evaluacion`, `composicion_variable` y advertencias. Cada punto del historial incluye `ejecucion_completada`, un dato informativo sobre el gasto real que no condiciona el entrenamiento; no certifica el cierre del presupuesto mensual. Su esquema completo está en Swagger UI. No se incluye un ejemplo numérico como si fuera una predicción de los datos existentes.

### Estado e integración

| Método | Endpoint | Acceso | Función |
| --- | --- | --- | --- |
| GET | `/api/health` | Público | Estado de la API |
| GET | `/api/powerbi/status` | Público | Marcador informativo de una integración fuera del alcance de esta entrega; no ofrece reportes |

### API financiera vigente

La interfaz utiliza `/api/financial/*` para las partidas y `/api/forecast/budget` para la predicción de presupuestos. Los endpoints financieros del formato anterior fueron retirados y ya no aparecen en OpenAPI. Sus URL devuelven 404. El detalle de la retirada está en [CHANGELOG.md](CHANGELOG.md).

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

**Power BI Embedded está fuera del alcance de esta entrega debido al tiempo disponible.** No se incluye la creación, publicación ni incrustación de reportes, la configuración de Microsoft Entra, licencias, capacidad o actualización mediante gateway. La pestaña Power BI y el endpoint `/api/powerbi/status` existentes son marcadores informativos y no constituyen una integración operativa. Las vistas SQL se conservan como base para una posible integración futura.

La recuperación de contraseñas, la asociación de correos a cuentas anteriores, la auditoría completa y el cierre/aprobación mensual permanecen pendientes. La interfaz utiliza el pronóstico de presupuesto por regresión lineal con evaluación temporal cuando la serie es elegible. El dashboard financiero ya no devuelve `prediction`; el frontend consulta exclusivamente `/api/forecast/budget` para obtener el pronóstico. El cierre mensual formal y la validación del modelo con datos representativos de cada empresa siguen pendientes. La solución no ofrece carga universal de CSV ni aislamiento multiempresa.

La publicación para usuarios remotos requiere una configuración de HTTPS, acceso de red y correo distinta de la instalación local incluida. Los límites de intentos son por proceso y requieren almacenamiento compartido antes de escalar a varios servidores.


## Verificar la predicción de presupuesto

La dependencia del modelo es `scikit-learn>=1.5,<2` en `backend/requirements.txt`, comprobada con 1.9.1. Esta actualización no incorpora dependencias adicionales ni modifica las tablas SQL. Con 24 meses compara tendencia con una regresión que incluye el mes del año.

**Demostración desde una base sin datos financieros importados.** Utiliza una instalación de pruebas independiente de los datos reales. Antes de cargar el ejemplo, inicia sesión como analista y comprueba que Importaciones esté vacío y que Resumen no tenga partidas reales. Si la instalación de pruebas ya contiene cargas, elimínalas desde Importaciones con la confirmación `ELIMINAR N` para cada carga, revisando todas las páginas del listado, y verifica de nuevo que no queden datos importados. No es necesario borrar usuarios, ejecutar SQL ni eliminar el volumen de PostgreSQL.

**Importa únicamente `presupuesto_historico_completo_2024_2026-v4.csv` para esta demostración.** Este archivo y `presupuesto_empresarial_2026.csv` comparten enero, febrero y marzo de 2026 con IDs distintos. Si cargas ambos, sus partidas se aceptan como registros diferentes y los presupuestos de esos meses se suman: cambian los totales y, cuando esos meses pertenecen a la ventana analizada, la predicción. La protección contra archivos repetidos y claves duplicadas no detecta ese solapamiento semántico. El ejemplo breve debe probarse por separado, retirando antes el histórico completo de la instalación de pruebas.

1. Actualiza el código conservando `.env` y el volumen de PostgreSQL. Ejecuta `docker compose up -d --build`. Reconstruir los contenedores no vacía las cargas existentes; prepara la base de pruebas como se indica arriba.
2. Desde Importaciones, con sesión de analista, importa sólo [presupuesto_historico_completo_2024_2026-v4.csv](examples/presupuesto_historico_completo_2024_2026-v4.csv), con 792 registros de 36 meses de datos sintéticos. Comprueba que sea la única carga y que tenga 792 partidas. No importes además `presupuesto_empresarial_2026.csv` ni otros ejemplos.
3. En Resumen selecciona diciembre de 2026, moneda MXN y todas las categorías. El periodo pronosticado debe ser enero de 2027. La tarjeta verde y el detalle deben mostrar el mismo resultado de `/api/forecast/budget?currency=MXN&period=2026-12`, sin elegir archivo. Si el histórico no cumple los requisitos o el modelo no supera la evaluación, ambas vistas explican la no disponibilidad.
4. Selecciona un mes base anterior para comprobar que cambie el periodo objetivo y se excluyan los datos posteriores de la predicción. Después vuelve a diciembre de 2026. Una sesión posterior conserva los datos: la fuente es la base de datos, no el navegador ni los CSV temporales. Para comprobar más adelante la actualización con nuevas cargas, incorpora únicamente partidas nuevas del mismo ámbito financiero y moneda, sin superponer versiones alternativas del ejemplo.
5. Repetir una carga ya guardada debe devolver 409 sin alterar la predicción. Puedes comprobar las partidas con `SELECT year, month, currency, COUNT(*), SUM(budget) FROM financial_entries WHERE nature = 'expense' GROUP BY year, month, currency ORDER BY year, month, currency;` en tu cliente SQL. Puedes consultar la respuesta en Swagger con una sesión financiera iniciada en el mismo host del navegador.

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

La verificación de esta entrega incluye **71 pruebas de backend con SQLite y 15 de frontend**; compilación y formato correctos. Las pruebas del forecast incluyen cargas mensuales desordenadas, persistencia comprobada desde otra sesión SQL, suma de partidas complementarias, rechazo de duplicados, consulta sin usar el parser CSV, actualización tras cambios persistidos, filtros y corte temporal. Además de estas pruebas automatizadas, el autor del proyecto confirmó la prueba de la plataforma con Docker y PostgreSQL y la revisión visual en el navegador. Esta verificación funcional no sustituye la evaluación financiera con datos reales representativos de cada empresa.

### Archivos de esta actualización

| Archivos | Propósito |
| --- | --- |
| `backend/app/forecast.py` | Dos configuraciones de regresión lineal, selección temporal anterior a la evaluación y comparación informativa con la referencia |
| `frontend/src/components/BudgetForecast.jsx` | Descripción de la configuración utilizada y explicación de selección/evaluación |
| `backend/tests/test_forecast.py`, `frontend/tests/budgetForecast.test.js` | Patrones anuales, independencia de selección, ausencia de fuga temporal, importación y advertencias |
| `backend/app/main.py`, `frontend/src/App.jsx` | Versión visible y de API |
| `README.md`, `CHANGELOG.md` | Predicción de presupuesto con regresión lineal, metodología, límites y verificación |

La verificación incluyó el CSV sintético de 792 registros [presupuesto_historico_completo_2024_2026-v4.csv](examples/presupuesto_historico_completo_2024_2026-v4.csv), incluido en `examples/`: importación mediante la API, persistencia en una base SQLite aislada y consulta del forecast para el último mes y varios cortes anteriores. Se conserva el contenido del archivo original. Las pruebas automáticas versionadas usan sus propios datos sintéticos identificados como fixtures. Esta verificación comprueba el funcionamiento con datos de prueba; no sustituye la evaluación con datos reales representativos de cada empresa.

Se conservan el login, los roles, Simulación, importación y eliminación de cargas, modelo SQL y dependencias. Actualiza backend y frontend juntos con `docker compose up -d --build`, manteniendo `.env` y el volumen. Si el CSV ya está guardado, no lo reimportes: la consulta utiliza los registros existentes. Comprueba que el pie de página muestre **v0.18**. Los importes obtenidos en una base que contenga solo ese archivo pueden diferir de los de una instalación con otras cargas o filtros.
