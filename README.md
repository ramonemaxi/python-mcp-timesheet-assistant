# Importante: Este proyecto ahora es SOLO Timesheets (PF)

Se eliminó el flujo antiguo de proyectos/time_entries (list_projects, get_project, add_time_entry, update_time_entry, delete_time_entry, list_time_entries). El servidor MCP expone únicamente las tools PF:
- create_timesheet
- list_timesheets
- get_timesheet
- update_timesheet
- delete_timesheet
- get_timesheet_fields_info
- export_timesheets (también guarda el archivo en la carpeta exports/)

# Demo MCP (Model Context Protocol) en Python: Asistente de Registro de Horas (Timesheets)

Este proyecto demuestra un flujo completo MCP en local con un dominio de registro de horas:
- Un servidor MCP (por stdio) que expone tools para consultar proyectos asignados y registrar/editar/eliminar/listar horas del usuario actual en una base SQLite embebida.
- Un cliente MCP que recibe instrucciones en lenguaje natural, consulta a un modelo (LM Studio u OpenAI, elegible al inicio) y, según la respuesta, ejecuta tools del servidor para cumplir la tarea.

Requisitos:
- Python 3.10+
- Opcional: LM Studio instalado y sirviendo una API OpenAI‑compatible (p. ej. `http://localhost:1234/v1`).
- Si se usa OpenAI: variable `OPENAI_API_KEY` o introducir la clave al iniciar el cliente.

## Instalación

1) Crear y activar entorno virtual (recomendado):

```
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# o
.venv\Scripts\activate    # Windows
```

2) Instalar dependencias:

```
pip install -r requirements.txt
```

## Estructura del proyecto

```
client/
  client.py          # Cliente MCP: conversa con el modelo y ejecuta tools del servidor
server/
  server.py          # Servidor MCP: define y expone tools de timesheets por stdio
  db_utils.py        # Utilidades de base de datos (init/conn)
db/
  database.db        # SQLite embebida (se crea/actualiza al iniciar el servidor)
README.md
requirements.txt
```

## Cómo ejecutar

1) Iniciar el cliente (el cliente arranca el servidor MCP automáticamente por stdio):

```
python -m client.client
```

2) Elegir proveedor de modelo:
- `lmstudio`: usa API OpenAI‑compatible local (base_url configurable).
- `openai`: usa OpenAI oficial (requiere `OPENAI_API_KEY`).

3) Ingresar identificador de usuario (person_id): por ejemplo `maxi` o `maca` (vienen pre‑cargados como ejemplo).

4) Escribir instrucciones en lenguaje natural. Ejemplos:
- "listá mis proyectos"
- "agregá 2.5 horas en el Limpiar el patio el 2025-09-05 con descripción 'cortar el pasto'"
- "mostrame mis horas del Organizar cumpleaños entre 2025-09-01 y 2025-09-10"
- "editá la entrada de horas 3 a 1.5 horas"
- "eliminá la entrada 3"

Escribe `salir` o `exit` para terminar.

## Notas de implementación

- Servidor MCP: se inicia por stdio. Define tools con `FastMCP` del SDK MCP de Python. Cada tool opera la base SQLite `db/database.db` en el dominio de timesheets. Las tools incluyen:
  - `list_projects(current_user_id, ...)`: lista los proyectos asignados al usuario.
  - `get_project(current_user_id, project_id)`: obtiene un proyecto si el usuario está asignado.
  - `list_time_entries(current_user_id, ...)`: lista horas del usuario actual (opcionalmente por proyecto y rango de fechas).
  - `add_time_entry(current_user_id, project_id, work_date, hours, description)`: crea una parte de horas (valida fecha y horas; requiere asignación y descripción obligatoria).
  - `update_time_entry(current_user_id, entry_id, [...])`: actualiza una entrada del propio usuario (con validaciones).
  - `delete_time_entry(current_user_id, entry_id)`: borra una entrada del propio usuario.
- Cliente MCP: lanza y conecta el servidor por stdio, descubre las tools y corre un bucle de "agente". El cliente pide el `person_id` inicial y además inyecta automáticamente `current_user_id` en cada llamada de tool. El modelo recibe el catálogo de tools y debe responder en JSON con `action = tool/final`.

## Reglas y seguridad

- Control de acceso: el usuario sólo puede operar sobre sus propias horas y consultar únicamente proyectos a los que está asignado (tabla `assignments`).
- Validaciones: `work_date` debe ser `YYYY-MM-DD`, `hours` debe ser numérico en (0, 24].
- No hay tools para crear/editar proyectos; sólo se pueden consultar.

## Comentarios clave (en el código)

- En `server/server.py` hay comentarios sobre cómo se inicializa un servidor MCP por stdio y cómo registrar tools.
- En `client/client.py` se explica cómo se arranca el servidor MCP, se establece la sesión y cómo el cliente orquesta al modelo y a las tools (inyectando `current_user_id`).

## Troubleshooting

- Si LM Studio no responde, verifica que el servidor HTTP esté activo, el modelo cargado y la `base_url` correcta.
- Si usas OpenAI, asegura que `OPENAI_API_KEY` esté configurada o introdúcela cuando lo pida el cliente.
- En Windows, podría ser necesario usar `python` o `py` para lanzar el módulo.


## Variables de entorno (opcional)

- LMSTUDIO_BASE_URL: URL de la API OpenAI‑compatible de LM Studio. Si no se define, el cliente te pedirá la URL y podrás ajustarla (por ejemplo, http://localhost:1234/v1 según tu instalación de LM Studio).
- LMSTUDIO_MODEL: nombre del modelo en LM Studio. Por defecto, el cliente propone un valor configurable.
- LMSTUDIO_API_KEY: token (string) requerido por algunos clientes HTTP. El cliente propone un valor por defecto.
- OPENAI_API_KEY: clave para OpenAI si eliges el proveedor 'openai'.
- OPENAI_MODEL: modelo de OpenAI a usar. Por defecto "gpt-4o-mini" (puedes sobrescribirlo por variable).

## Comportamiento del cliente (anti‑invención de datos)

Para la tool add_time_entry el cliente aplica validaciones adicionales y no completa datos por su cuenta:
- Son obligatorios: project_id, work_date (YYYY‑MM‑DD), hours y description.
- El cliente NO asume valores por defecto (no usa "hoy", ni inventa horas o descripciones).
- En el texto de tu instrucción debes mencionar explícitamente:
  - La fecha en formato YYYY‑MM‑DD.
  - La cantidad de horas con unidades (h/hs/hora/horas), p. ej. "2 horas" o "1.5 h".
  - La descripción (tal como la quieres registrar).
- Si falta cualquiera de esos datos en el mensaje del usuario, el cliente no llamará a la tool y te pedirá aclararlos.

## Pruebas rápidas

Puedes ejecutar algunos scripts de smoke test:

```
python -m client.smoke_test
python -m client.smoke_test_timesheets
python -m client.smoke_test_missing_fields
```

## Tips de troubleshooting adicionales

- Si al listar proyectos no ves resultados, verifica el person_id que ingresaste: la base de ejemplo incluye usuarios como "alice" y "bob" con asignaciones. Otros (p. ej., "marcelo") no tienen proyectos por defecto.
- Si quieres re‑inicializar los datos de ejemplo, elimina el archivo db/database.db y vuelve a ejecutar: se recrearán tablas y datos seed automáticamente.


## Nuevas tools PF (Plantilla PF_PlantillaRegTiempos.csv)

El servidor ahora expone herramientas para cargar tareas diarias y exportarlas en el formato exacto de PF_PlantillaRegTiempos.csv.

Tools MCP nuevas:
- create_timesheet(nombre_personal?, legajo_personal, fecha, cliente, nombre_cliente?, contrato_division, nombre_division?, contrato_tipo, nombre_tipo?, contrato_numero, nombre_contrato?, tarea, nombre_tarea?, tiempo, observaciones?, categoria?)
  - Obligatorios: legajo_personal, fecha, cliente, contrato_division, contrato_tipo, contrato_numero, tarea, tiempo.
  - Formatos aceptados:
    - fecha: "YYYY-MM-DD", "DD/MM/YYYY" o timestamp.
    - tiempo: "HH:MM", minutos enteros (p. ej. 90), horas decimales (1.5 u "1.5h").
- list_timesheets(date_from?, date_to?, legajo?, limit?, offset?)
- export_timesheets(date_from?, date_to?, legajo?) -> { filename, content, count }
  - content es el CSV (UTF-8, sin BOM) con:
    - Las primeras 10 líneas de encabezado idénticas a la plantilla del repo.
    - Filas de datos que comienzan con "D;" seguidas de 16 campos en el orden exacto, separados por ";".

Ejemplos de uso (vía cliente MCP interactivo):
- "crear 3 timesheets con legajo MAXI, fecha 2025-01-21, cliente 1, división IOT, tipo 7, número 1456, tarea ATC, tiempo 01:30"
- "crear timesheets con legajo RAMON, para 2025-09-23, cliente 1, división IOT, tipo 7, número 1456, tarea UDP, tiempo 8"
- "exportar timesheets del 2025-01-01 al 2025-01-31 para legajo BRAIAN"

## Nueva prueba de humo PF

Ejecuta la prueba que inserta registros y valida la exportación:

```
python -m client.smoke_test_pf_timesheets
```

Esto generará una exportación en memoria y verificará que:
- Las 10 primeras líneas coincidan exactamente con la plantilla del repo.
- Cada fila de datos empiece con "D;" y tenga 16 separadores ";" (17 partes al dividir por ";").
- Los formatos de FECHA y TIEMPO sean DD/MM/AAAA y HH:MM respectivamente.


## Campos de Timesheet (obligatorios y opcionales)

- Obligatorios: legajo_personal, fecha, cliente, contrato_division, contrato_tipo, contrato_numero, tarea, tiempo.
- Opcionales: nombre_personal, nombre_cliente, nombre_division, nombre_tipo, nombre_contrato, nombre_tarea, observaciones, categoria.
- Formatos:
  - fecha: "YYYY-MM-DD", "DD/MM/YYYY" o timestamp; se almacena como YYYY-MM-DD y se exporta como DD/MM/AAAA.
  - tiempo: "HH:MM", minutos enteros (p. ej. 90) u horas decimales (1.5 / "1.5h"); se almacena en minutos (tiempo_minutos) y se exporta como HH:MM.

Puedes consultar esta información en tiempo de ejecución con la tool MCP `get_timesheet_fields_info`.

## Exportación a CSV (PF)

La tool `export_timesheets` ahora también guarda el archivo generado en la carpeta `exports/` del proyecto y retorna `saved_path` junto con `filename`, `content` y `count`. El contenido respeta la plantilla PF_PlantillaRegTiempos.csv (encabezados y filas "D;" con 16 campos separados por punto y coma).