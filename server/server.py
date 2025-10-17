"""
Servidor MCP por stdio que expone herramientas (tools) para operar una base SQLite embebida.

Cómo se inicializa el servidor MCP:
- Usamos FastMCP del SDK de Python de MCP para definir un servidor y registrar tools.
- Al ejecutar `python -m server.server`, se invoca `server.run()` que abre el transporte stdio.
- Un cliente MCP puede lanzar este proceso y comunicarse por stdio (stdin/stdout),
  negociando el protocolo MCP (initialize, list_tools, call_tool, etc.).

Dominio: Asistente para registrar horas de trabajo (timesheets). Las personas tienen un identificador
único (person_id). Sólo pueden registrar/editar/eliminar/listar SUS propias horas y consultar los
proyectos a los que estén asignadas.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP
from server.db_utils import (
    ensure_db,
    db_connection,
    insert_timesheet as db_insert_timesheet,
    list_timesheets as db_list_timesheets,
    export_timesheets_csv as db_export_timesheets_csv,
    update_timesheet as db_update_timesheet,
    delete_timesheet as db_delete_timesheet,
    get_timesheet as db_get_timesheet,
    timesheet_fields_info as db_timesheet_fields_info,
)

# Crear servidor MCP con nombre
server = FastMCP("sqlite-mcp")


@server.tool()
def create_timesheet(
    nombre_personal: Optional[str] = None,
    legajo_personal: str = "",
    fecha: Any = "",
    cliente: str = "",
    nombre_cliente: Optional[str] = None,
    contrato_division: str = "",
    nombre_division: Optional[str] = None,
    contrato_tipo: str = "",
    nombre_tipo: Optional[str] = None,
    contrato_numero: str = "",
    nombre_contrato: Optional[str] = None,
    tarea: str = "",
    nombre_tarea: Optional[str] = None,
    tiempo: Any = "",
    observaciones: Optional[str] = None,
    categoria: Optional[str] = None,
) -> Dict[str, Any]:
    """Crea un registro de timesheet con las validaciones requeridas por la plantilla PF.
    Los campos obligatorios son: legajo_personal, fecha, cliente, contrato_division, contrato_tipo, contrato_numero, tarea, tiempo.
    El campo 'tiempo' acepta HH:MM, minutos enteros o horas decimales (e.g., 1.5 o "1.5h").
    """
    payload = {
        "nombre_personal": nombre_personal,
        "legajo_personal": legajo_personal,
        "fecha": fecha,
        "cliente": cliente,
        "nombre_cliente": nombre_cliente,
        "contrato_division": contrato_division,
        "nombre_division": nombre_division,
        "contrato_tipo": contrato_tipo,
        "nombre_tipo": nombre_tipo,
        "contrato_numero": contrato_numero,
        "nombre_contrato": nombre_contrato,
        "tarea": tarea,
        "nombre_tarea": nombre_tarea,
        "tiempo": tiempo,
        "observaciones": observaciones,
        "categoria": categoria,
    }
    try:
        with db_connection() as conn:
            row = db_insert_timesheet(conn, payload)
            return {"created": True, "row": row}
    except Exception as e:
        return {"created": False, "error": str(e)}


@server.tool()
def list_timesheets(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    legajo: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
) -> Dict[str, Any]:
    """Lista registros de timesheets (filtros opcionales por rango de fechas y legajo)."""
    try:
        with db_connection() as conn:
            return db_list_timesheets(conn, date_from=date_from, date_to=date_to, legajo=legajo, limit=limit, offset=offset)
    except Exception as e:
        return {"rows": [], "count": 0, "error": str(e)}


@server.tool()
def export_timesheets(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    legajo: Optional[str] = None,
) -> Dict[str, Any]:
    """Exporta los registros a un CSV con el formato exacto PF_PlantillaRegTiempos.csv.
    Retorna { filename, content, count }.
    """
    try:
        with db_connection() as conn:
            result = db_export_timesheets_csv(conn, date_from=date_from, date_to=date_to, legajo=legajo)
            return result
    except Exception as e:
        return {"error": str(e)}


@server.tool()
def get_timesheet(id: int) -> Dict[str, Any]:
    """Obtiene un registro de timesheet por id."""
    try:
        with db_connection() as conn:
            row = db_get_timesheet(conn, int(id))
            return {"found": bool(row), "row": row}
    except Exception as e:
        return {"found": False, "error": str(e)}


@server.tool()
def update_timesheet(
    id: int,
    nombre_personal: Optional[str] = None,
    legajo_personal: Optional[str] = None,
    fecha: Optional[Any] = None,
    cliente: Optional[str] = None,
    nombre_cliente: Optional[str] = None,
    contrato_division: Optional[str] = None,
    nombre_division: Optional[str] = None,
    contrato_tipo: Optional[str] = None,
    nombre_tipo: Optional[str] = None,
    contrato_numero: Optional[str] = None,
    nombre_contrato: Optional[str] = None,
    tarea: Optional[str] = None,
    nombre_tarea: Optional[str] = None,
    tiempo: Optional[Any] = None,
    tiempo_minutos: Optional[int] = None,
    observaciones: Optional[str] = None,
    categoria: Optional[str] = None,
) -> Dict[str, Any]:
    """Actualiza un registro de timesheet. Acepta 'tiempo' (HH:MM/minutos/horas decimales) o 'tiempo_minutos'.
    Valida que los campos obligatorios sigan presentes.
    """
    payload = {
        "nombre_personal": nombre_personal,
        "legajo_personal": legajo_personal,
        "fecha": fecha,
        "cliente": cliente,
        "nombre_cliente": nombre_cliente,
        "contrato_division": contrato_division,
        "nombre_division": nombre_division,
        "contrato_tipo": contrato_tipo,
        "nombre_tipo": nombre_tipo,
        "contrato_numero": contrato_numero,
        "nombre_contrato": nombre_contrato,
        "tarea": tarea,
        "nombre_tarea": nombre_tarea,
        "tiempo": tiempo,
        "tiempo_minutos": tiempo_minutos,
        "observaciones": observaciones,
        "categoria": categoria,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        with db_connection() as conn:
            row = db_update_timesheet(conn, int(id), payload)
            return {"updated": True, "row": row}
    except Exception as e:
        return {"updated": False, "error": str(e)}


@server.tool()
def delete_timesheet(id: int) -> Dict[str, Any]:
    """Elimina un registro de timesheet por id."""
    try:
        with db_connection() as conn:
            deleted = db_delete_timesheet(conn, int(id))
            return {"deleted": bool(deleted)}
    except Exception as e:
        return {"deleted": False, "error": str(e)}


@server.tool()
def get_timesheet_fields_info() -> Dict[str, Any]:
    """Devuelve campos obligatorios y opcionales y notas de formato."""
    try:
        return db_timesheet_fields_info()
    except Exception as e:
        return {"error": str(e)}

# Asegurar que la base está creada al importar/arrancar
_ = ensure_db()


if __name__ == "__main__":
    # Inicia el servidor MCP por stdio.
    # Un cliente (como client/client.py) lo lanzará con `python -m server.server` y
    # hablará por stdin/stdout usando el protocolo MCP.
    server.run()