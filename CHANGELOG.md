# Historial de cambios

Este documento reúne las notas de las entregas del proyecto. Los números identifican las versiones utilizadas durante el desarrollo; no implican que existan etiquetas Git con esos nombres. No se añaden fechas de publicación que no estén registradas.

La instalación y el uso vigentes se documentan en [README.md](README.md).

## Sin publicar

### Documentación

- README reescrito como documento del proyecto: problema, funciones, arquitectura, instalación, configuración, uso, roles, API y mantenimiento.
- Instalación desde GitHub mediante clonación, en lugar de instrucciones para descomprimir una entrega.
- Historial de versiones y notas de migración separados en este archivo.
- Endpoints documentados a partir del código actual, incluidos los de compatibilidad.
- Sin cambios en el frontend, backend ni esquema de datos en esta actualización documental.

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
