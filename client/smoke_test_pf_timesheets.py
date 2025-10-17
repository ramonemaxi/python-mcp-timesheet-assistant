import asyncio
import sys
import re
from typing import Any, Dict, List
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession


def extract_payload(result) -> Any:
    try:
        content_list = getattr(result, "content", [])
        for c in content_list:
            ctype = getattr(c, "type", None)
            if ctype == "json":
                data = getattr(c, "data", None)
                if isinstance(data, dict) and "result" in data:
                    return data["result"]
                return data
            if ctype == "text":
                txt = getattr(c, "text", None)
                if isinstance(txt, str) and txt.strip().startswith("{"):
                    import json
                    try:
                        return json.loads(txt)
                    except Exception:
                        return txt
                return txt
    except Exception:
        pass
    return None


def read_pf_header() -> List[str]:
    import os
    base = os.path.dirname(os.path.dirname(__file__))
    path = os.path.join(base, "PF_PlantillaRegTiempos.csv")
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                lines = f.read().splitlines()
            return [lines[i] if i < len(lines) else "" for i in range(10)]
        except Exception:
            continue
    raise RuntimeError("No se pudo leer PF_PlantillaRegTiempos.csv")


import os

async def main():
    python_bin = sys.executable
    server_module = "server.server"
    async with stdio_client(StdioServerParameters(command=python_bin, args=["-m", server_module])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Tools disponibles
            res = await session.list_tools()
            tool_list = getattr(res, "tools", res)
            names = []
            for t in tool_list:
                name = getattr(t, "name", None)
                if not name and hasattr(t, "model_dump"):
                    try:
                        name = t.model_dump().get("name")
                    except Exception:
                        name = None
                names.append(name or "<noname>")
            print("TOOLS:", names)
            assert "create_timesheet" in names, "Falta tool create_timesheet"
            assert "list_timesheets" in names, "Falta tool list_timesheets"
            assert "export_timesheets" in names, "Falta tool export_timesheets"

            # Crear varios registros con formatos variados
            samples: List[Dict[str, Any]] = [
                {
                    "nombre_personal": "BRAIAN",
                    "legajo_personal": "BRAIAN",
                    "fecha": "2025-01-21",
                    "cliente": "1",
                    "nombre_cliente": "IOT",
                    "contrato_division": "IOT",
                    "contrato_tipo": "7",
                    "contrato_numero": "1456",
                    "tarea": "ATC",
                    "tiempo": "01:30",
                    "observaciones": "prueba export 1",
                },
                {
                    # fecha DD/MM/YYYY y tiempo en horas decimales
                    "nombre_personal": "BRAIAN",
                    "legajo_personal": "BRAIAN",
                    "fecha": "22/01/2025",
                    "cliente": "1",
                    "contrato_division": "IOT",
                    "contrato_tipo": "7",
                    "contrato_numero": "1456",
                    "tarea": "NF",
                    "tiempo": 1.5,
                    "observaciones": "prueba export 2",
                },
                {
                    # tiempo minutos enteros
                    "nombre_personal": "BRAIAN",
                    "legajo_personal": "BRAIAN",
                    "fecha": "2025-01-23",
                    "cliente": "1",
                    "contrato_division": "IOT",
                    "contrato_tipo": "7",
                    "contrato_numero": "1456",
                    "tarea": "UTG",
                    "tiempo": 90,
                    "observaciones": "ñandú con tilde",
                    "categoria": "área",
                },
            ]

            for s in samples:
                r = await session.call_tool("create_timesheet", arguments=s)
                payload = extract_payload(r)
                print("create_timesheet:", payload)
                assert isinstance(payload, dict)
                assert payload.get("created") is True, f"create_timesheet falló: {payload}"

            # Listar por rango
            r = await session.call_tool("list_timesheets", arguments={"date_from": "2025-01-01", "date_to": "2025-01-31", "legajo": "BRAIAN"})
            payload = extract_payload(r)
            print("list_timesheets:", payload)
            assert isinstance(payload, dict)
            assert payload.get("count", 0) >= 3

            # Exportar
            r = await session.call_tool("export_timesheets", arguments={"date_from": "2025-01-01", "date_to": "2025-01-31", "legajo": "BRAIAN"})
            payload = extract_payload(r)
            print("export_timesheets filename:", (payload or {}).get("filename"))
            content = (payload or {}).get("content", "")
            assert isinstance(content, str) and len(content) > 0
            assert not content.startswith("\ufeff"), "CSV no debe tener BOM"
            saved_path = (payload or {}).get("saved_path")
            assert isinstance(saved_path, str) and len(saved_path) > 0, "saved_path faltante"
            assert os.path.exists(saved_path), f"Archivo no encontrado en {saved_path}"

            lines = content.splitlines()
            # Encabezados
            tpl = read_pf_header()
            assert lines[:10] == tpl[:10], "Encabezados (primeras 10 líneas) no coinciden con plantilla"

            # Validaciones de filas D;
            data_lines = [ln for ln in lines[10:] if ln.strip()]
            assert all(ln.startswith("D;") for ln in data_lines)
            # Para cada D;, deben haber exactamente 16 ';' en la línea (1 por prefijo + 15 separadores de 16 campos)
            for ln in data_lines:
                assert ln.count(";") == 16, f"Separadores inesperados en: {ln}"
                parts = ln.split(";")
                assert len(parts) == 17
                # parts[0] == 'D'
                fecha = parts[3]
                tiempo = parts[14]
                assert re.fullmatch(r"\d{2}/\d{2}/\d{4}", fecha), f"Fecha no DD/MM/YYYY: {fecha}"
                assert re.fullmatch(r"\d{2}:\d{2}", tiempo), f"Tiempo no HH:MM: {tiempo}"

            print("OK smoke_test_pf_timesheets: exportación PF válida")


if __name__ == "__main__":
    asyncio.run(main())
