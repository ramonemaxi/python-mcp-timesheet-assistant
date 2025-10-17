import os
import sqlite3
from typing import Tuple, Optional, List, Any, Union, Dict
from contextlib import contextmanager
import re
from datetime import datetime, date

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "db")
DB_PATH = os.path.join(DB_DIR, "database.db")
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
PF_TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "PF_PlantillaRegTiempos.csv")

def _enable_fk(conn: sqlite3.Connection):
    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass

@contextmanager
def db_connection():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    _enable_fk(conn)
    try:
        yield conn
    finally:
        conn.close()

def ensure_db():
    """
    Inicializa la base de datos SOLO para el dominio de timesheets (PF).
    Crea la tabla timesheets e índices.
    """
    with db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS timesheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_personal TEXT,
                legajo_personal TEXT NOT NULL,
                fecha TEXT NOT NULL, -- YYYY-MM-DD
                cliente TEXT NOT NULL,
                nombre_cliente TEXT,
                contrato_division TEXT NOT NULL,
                nombre_division TEXT,
                contrato_tipo TEXT NOT NULL,
                nombre_tipo TEXT,
                contrato_numero TEXT NOT NULL,
                nombre_contrato TEXT,
                tarea TEXT NOT NULL,
                nombre_tarea TEXT,
                tiempo_minutos INTEGER NOT NULL,
                observaciones TEXT,
                categoria TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        # Recommended indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_timesheets_legajo ON timesheets(legajo_personal)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_timesheets_fecha ON timesheets(fecha)")
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_timesheets_contrato ON timesheets(cliente, contrato_division, contrato_tipo, contrato_numero)"
        )
        conn.commit()

# ---- PF Timesheets helpers ----

def _truncate(s: Optional[str], maxlen: int = 255) -> Optional[str]:
    if s is None:
        return None
    s = str(s)
    return s[:maxlen]

def parse_fecha(value: Union[str, int, float]) -> str:
    """Acepta YYYY-MM-DD, DD/MM/YYYY o timestamp (segundos). Devuelve YYYY-MM-DD."""
    if value is None:
        raise ValueError("fecha requerida")
    if isinstance(value, (int, float)):
        dt = datetime.fromtimestamp(float(value))
        return dt.strftime("%Y-%m-%d")
    s = str(value).strip()
    # YYYY-MM-DD
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    # DD/MM/YYYY
    try:
        dt = datetime.strptime(s, "%d/%m/%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    raise ValueError("fecha inválida: usa YYYY-MM-DD, DD/MM/YYYY o timestamp")

def to_ddmmyyyy(yyyy_mm_dd: str) -> str:
    dt = datetime.strptime(yyyy_mm_dd, "%Y-%m-%d")
    return dt.strftime("%d/%m/%Y")

def parse_tiempo(value: Union[str, int, float]) -> int:
    """Convierte distintas representaciones a minutos enteros (>0).
    Acepta:
    - "H:MM" o "HH:MM"
    - Entero (minutos)
    - Flotante u string con sufijo h/hs (horas decimales), p.ej. 1.5, "1.5h"
    - String numérico entero se interpreta como minutos
    """
    if value is None:
        raise ValueError("tiempo requerido")
    # HH:MM
    if isinstance(value, str) and ":" in value:
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("formato de tiempo inválido")
        try:
            h = int(parts[0])
            m = int(parts[1])
        except Exception:
            raise ValueError("formato de tiempo inválido")
        if h < 0 or m < 0 or m >= 60:
            raise ValueError("formato de tiempo inválido")
        total = h * 60 + m
        if total <= 0:
            raise ValueError("tiempo debe ser > 0")
        return total
    # Sufijos horas
    if isinstance(value, str) and re.fullmatch(r"\s*\d+(?:[\.,]\d+)?\s*(h|hs)\s*", value, flags=re.IGNORECASE):
        num = re.sub(r"[^0-9\.,]", "", value)
        num = num.replace(",", ".")
        hours = float(num)
        total = int(round(hours * 60))
        if total <= 0:
            raise ValueError("tiempo debe ser > 0")
        return total
    # Números
    try:
        if isinstance(value, str):
            v = value.strip()
            # string numérico entero => minutos
            if re.fullmatch(r"\d+", v):
                total = int(v)
                if total <= 0:
                    raise ValueError("tiempo debe ser > 0")
                return total
            # flotante => horas decimales
            if re.fullmatch(r"\d+(?:[\.,]\d+)?", v):
                hours = float(v.replace(",", "."))
                total = int(round(hours * 60))
                if total <= 0:
                    raise ValueError("tiempo debe ser > 0")
                return total
        # numérico directo
        if isinstance(value, (int, float)):
            # interpretamos minutos si es entero, horas si float (convención simple)
            if isinstance(value, int):
                total = int(value)
                if total <= 0:
                    raise ValueError("tiempo debe ser > 0")
                return total
            else:
                total = int(round(float(value) * 60))
                if total <= 0:
                    raise ValueError("tiempo debe ser > 0")
                return total
    except Exception:
        pass
    raise ValueError("tiempo inválido: usa HH:MM, minutos, o horas decimales (e.g., 1.5h)")

def to_hhmm(mins: int) -> str:
    if mins is None or int(mins) < 0:
        raise ValueError("minutos inválidos")
    h = int(mins) // 60
    m = int(mins) % 60
    return f"{h:02d}:{m:02d}"

def insert_timesheet(conn: sqlite3.Connection, payload: Dict[str, Any]) -> Dict[str, Any]:
    required_fields = [
        "legajo_personal",
        "fecha",
        "cliente",
        "contrato_division",
        "contrato_tipo",
        "contrato_numero",
        "tarea",
        "tiempo",
    ]
    for f in required_fields:
        if f not in payload or (isinstance(payload[f], str) and payload[f].strip() == ""):
            raise ValueError(f"Campo obligatorio faltante: {f}")

    fecha_iso = parse_fecha(payload.get("fecha"))
    minutos = parse_tiempo(payload.get("tiempo"))

    # Truncar y normalizar strings
    def norm(k: str) -> Optional[str]:
        v = payload.get(k)
        if v is None:
            return None
        return _truncate(str(v))

    row = {
        "nombre_personal": norm("nombre_personal"),
        "legajo_personal": _truncate(str(payload.get("legajo_personal"))),
        "fecha": fecha_iso,
        "cliente": _truncate(str(payload.get("cliente"))),
        "nombre_cliente": norm("nombre_cliente"),
        "contrato_division": _truncate(str(payload.get("contrato_division"))),
        "nombre_division": norm("nombre_division"),
        "contrato_tipo": _truncate(str(payload.get("contrato_tipo"))),
        "nombre_tipo": norm("nombre_tipo"),
        "contrato_numero": _truncate(str(payload.get("contrato_numero"))),
        "nombre_contrato": norm("nombre_contrato"),
        "tarea": _truncate(str(payload.get("tarea"))),
        "nombre_tarea": norm("nombre_tarea"),
        "tiempo_minutos": int(minutos),
        "observaciones": norm("observaciones"),
        "categoria": norm("categoria"),
    }

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO timesheets (
            nombre_personal, legajo_personal, fecha, cliente, nombre_cliente,
            contrato_division, nombre_division, contrato_tipo, nombre_tipo,
            contrato_numero, nombre_contrato, tarea, nombre_tarea, tiempo_minutos,
            observaciones, categoria
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["nombre_personal"], row["legajo_personal"], row["fecha"], row["cliente"], row["nombre_cliente"],
            row["contrato_division"], row["nombre_division"], row["contrato_tipo"], row["nombre_tipo"],
            row["contrato_numero"], row["nombre_contrato"], row["tarea"], row["nombre_tarea"], row["tiempo_minutos"],
            row["observaciones"], row["categoria"],
        ),
    )
    row_id = cur.lastrowid
    conn.commit()

    cur.execute("SELECT * FROM timesheets WHERE id = ?", (row_id,))
    out = dict(cur.fetchone())
    return out

def list_timesheets(conn: sqlite3.Connection, date_from: Optional[str] = None, date_to: Optional[str] = None, legajo: Optional[str] = None, limit: int = 1000, offset: int = 0) -> Dict[str, Any]:
    where: List[str] = []
    params: List[Any] = []
    if legajo:
        where.append("legajo_personal = ?")
        params.append(str(legajo))
    if date_from:
        date_from = parse_fecha(date_from)
        where.append("fecha >= ?")
        params.append(date_from)
    if date_to:
        date_to = parse_fecha(date_to)
        where.append("fecha <= ?")
        params.append(date_to)

    base_sql = "FROM timesheets"
    if where:
        base_sql += " WHERE " + " AND ".join(where)

    count_sql = "SELECT COUNT(*) " + base_sql
    
    cur = conn.cursor()
    
    cur.execute(count_sql, tuple(params))
    total_count = cur.fetchone()[0]

    sql = "SELECT * " + base_sql + " ORDER BY fecha ASC, id ASC"
    
    if limit <= 0:
        limit = 1000
    if offset < 0:
        offset = 0
        
    sql += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    
    cur.execute(sql, tuple(params))
    rows = [dict(r) for r in cur.fetchall()]
    return {"rows": rows, "count": total_count}

def _pf_header_lines() -> List[str]:
    # Prefer reading from the provided PF template to match exact characters
    # Try utf-8 first, then latin-1 as fallback (the sample file shows replacement chars in some viewers)
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(PF_TEMPLATE_PATH, "r", encoding=enc) as f:
                lines = f.read().splitlines()
            return [lines[i] if i < len(lines) else "" for i in range(10)]
        except Exception:
            continue
    # Fallback literals (may differ if template encoding is special)
    return [
        "#;Tipo de registro:;;;;;;;;;;;;;;;",
        "#;  Comentarios (#);;;;;;;;;;;;;;;",
        "#;  Titulo de columna (T);;;;;;;;;;;;;;;",
        "#;  Fila de datos (D);;;;;;;;;;;;;;;",
        "#;(*) Datos de la fila que deben ser completados con carácter obligatorio;;;;;;;;;;;;;;;",
        "#;;;;;;;;;;;;;;;",
        "#;POR FAVOR, SI CARGA DATOS NUMÉRICOS, VERIFIQUE QUE LA COLUMNA TENGA FORMATO 'TEXTO/TEXT';;;;;;;;;;;;;;;",
        "#;;;;;;;;;;;;;;;",
        "#;Alfanumérico;Alfanumérico;DD/MM/AAAA;Numérico;Alfanumérico;Indefinido;Alfanumérico;Alfanumérico;Alfanumérico;Numérico;Alfanumérico;Alfanumérico;Alfanumérico;HH/MM;Alfanumérico;Alfanumíco",
        "T;NOMBRE_PERSONAL;*LEGAJO_PERSONAL;*FECHA;*CLIENTE;NOMBRE CLIENTE;*CONTRATO-DIVISION;NOMBRE DIVISION;*CONTRATO-TIPO; NOMBRE TIPO;*CONTRATO-NUMERO; NOMBRE CONTRATO;*TAREA; NOMBRE TAREA;*TIEMPO;OBSERVACIONES;CATEGORIA",
    ]

def export_timesheets_csv(conn: sqlite3.Connection, date_from: Optional[str] = None, date_to: Optional[str] = None, legajo: Optional[str] = None) -> Dict[str, Any]:
    result = list_timesheets(conn, date_from, date_to, legajo, limit=-1)
    rows = result["rows"]
    out_lines: List[str] = []
    out_lines.extend(_pf_header_lines())

    # Data rows
    for r in rows:
        fields: List[str] = [
            # 1..16 as per spec
            r.get("nombre_personal") or "",
            r.get("legajo_personal") or "",
            to_ddmmyyyy(r.get("fecha")),
            r.get("cliente") or "",
            r.get("nombre_cliente") or "",
            r.get("contrato_division") or "",
            r.get("nombre_division") or "",
            r.get("contrato_tipo") or "",
            r.get("nombre_tipo") or "",
            r.get("contrato_numero") or "",
            r.get("nombre_contrato") or "",
            r.get("tarea") or "",
            r.get("nombre_tarea") or "",
            to_hhmm(int(r.get("tiempo_minutos") or 0)),
            r.get("observaciones") or "",
            r.get("categoria") or "",
        ]
        line = "D;" + ";".join(fields)
        out_lines.append(line)

    # Filename
    base_dt: date
    if date_from:
        base_dt = datetime.strptime(parse_fecha(date_from), "%Y-%m-%d").date()
    else:
        base_dt = datetime.utcnow().date()
    yyyymm = f"{base_dt.year}{base_dt.month:02d}"
    leg = (legajo or "todos").replace(" ", "_")
    filename = f"PF_PlantillaRegTiempos_{yyyymm}_{leg}.csv"

    content = "\n".join(out_lines) + "\n"
    # Save to exports directory
    exports_dir = os.path.join(PROJECT_ROOT, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    file_path = os.path.join(exports_dir, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"filename": filename, "content": content, "count": len(rows), "saved_path": file_path}

# ---- Additional Timesheet CRUD helpers ----

def get_timesheet(conn: sqlite3.Connection, ts_id: int) -> Optional[Dict[str, Any]]:
    cur = conn.cursor()
    cur.execute("SELECT * FROM timesheets WHERE id = ?", (int(ts_id),))
    row = cur.fetchone()
    return dict(row) if row else None

def _required_fields_list() -> List[str]:
    return [
        "legajo_personal",
        "fecha",
        "cliente",
        "contrato_division",
        "contrato_tipo",
        "contrato_numero",
        "tarea",
        # store as tiempo_minutos internally
        "tiempo_minutos",
    ]

def timesheet_fields_info() -> Dict[str, Any]:
    """Return required and optional fields info and format notes."""
    required = [
        "legajo_personal",
        "fecha",
        "cliente",
        "contrato_division",
        "contrato_tipo",
        "contrato_numero",
        "tarea",
        "tiempo",  # input alias for tiempo_minutos
    ]
    optional = [
        "nombre_personal",
        "nombre_cliente",
        "nombre_division",
        "nombre_tipo",
        "nombre_contrato",
        "nombre_tarea",
        "observaciones",
        "categoria",
    ]
    notes = {
        "fecha": "Acepta YYYY-MM-DD, DD/MM/YYYY o timestamp; se guarda como YYYY-MM-DD; exporta DD/MM/AAAA",
        "tiempo": "Acepta HH:MM, minutos enteros o horas decimales (1.5 / '1.5h'); se guarda en minutos",
    }
    return {"required": required, "optional": optional, "notes": notes}

def update_timesheet(conn: sqlite3.Connection, ts_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Update fields for a timesheet. Accepts same keys as insert_timesheet, plus 'tiempo' or 'tiempo_minutos'.
    Validates that required fields remain present after update.
    """
    base = get_timesheet(conn, int(ts_id))
    if not base:
        raise ValueError("timesheet no encontrado")

    updates: Dict[str, Any] = {}

    # fecha
    if "fecha" in payload and payload.get("fecha") is not None and str(payload.get("fecha")).strip() != "":
        updates["fecha"] = parse_fecha(payload.get("fecha"))

    # tiempo / tiempo_minutos
    if "tiempo" in payload and payload.get("tiempo") not in (None, ""):
        updates["tiempo_minutos"] = int(parse_tiempo(payload.get("tiempo")))
    elif "tiempo_minutos" in payload and payload.get("tiempo_minutos") is not None:
        tm = int(payload.get("tiempo_minutos"))
        if tm <= 0:
            raise ValueError("tiempo_minutos debe ser > 0")
        updates["tiempo_minutos"] = tm

    # Simple text fields (truncate)
    simple_fields = [
        "nombre_personal",
        "legajo_personal",
        "cliente",
        "nombre_cliente",
        "contrato_division",
        "nombre_division",
        "contrato_tipo",
        "nombre_tipo",
        "contrato_numero",
        "nombre_contrato",
        "tarea",
        "nombre_tarea",
        "observaciones",
        "categoria",
    ]
    for k in simple_fields:
        if k in payload:
            v = payload.get(k)
            if v is None:
                updates[k] = None
            else:
                updates[k] = _truncate(str(v))

    # Build resulting row for validation
    resulting = dict(base)
    resulting.update(updates)

    # Validate required remain present
    req = _required_fields_list()
    for f in req:
        if f == "tiempo_minutos":
            if int(resulting.get("tiempo_minutos") or 0) <= 0:
                raise ValueError("Campo obligatorio faltante o inválido: tiempo")
        else:
            val = resulting.get(f)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                raise ValueError(f"Campo obligatorio faltante: {f}")

    # Prepare SQL update
    if not updates:
        return base

    sets: List[str] = []
    params: List[Any] = []
    for k, v in updates.items():
        sets.append(f"{k} = ?")
        params.append(v)
    sets.append("updated_at = datetime('now')")
    params.append(int(ts_id))

    cur = conn.cursor()
    cur.execute(f"UPDATE timesheets SET {', '.join(sets)} WHERE id = ?", tuple(params))
    conn.commit()
    cur.execute("SELECT * FROM timesheets WHERE id = ?", (int(ts_id),))
    row = dict(cur.fetchone())
    return row

def delete_timesheet(conn: sqlite3.Connection, ts_id: int) -> bool:
    cur = conn.cursor()
    cur.execute("DELETE FROM timesheets WHERE id = ?", (int(ts_id),))
    deleted = cur.rowcount > 0
    conn.commit()
    return deleted