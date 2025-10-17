"""
Cliente MCP que:
- Lanza el servidor MCP por stdio (python -m server.server).
- Descubre las tools expuestas.
- Permite al usuario escribir instrucciones en lenguaje natural.
- Orquesta con un modelo (LM Studio u OpenAI) que, en base a las tools, devuelve acciones en JSON
  del tipo {"action":"tool","tool_name":"...","arguments":{...}} o {"action":"final","content":"..."}.
- Ejecuta las tools con MCP y retroalimenta los resultados al modelo hasta obtener una respuesta final.

Notas:
- LM Studio funciona si ejecutas su API OpenAI-compatible en http://localhost:1234/v1 y eliges 'lmstudio'.
- OpenAI requiere OPENAI_API_KEY (o ingresar la clave al iniciar el cliente).
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from colorama import Fore, Style, init as colorama_init
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters

try:
    from openai import OpenAI  # OpenAI SDK v1
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


@dataclass
class ProviderConfig:
    provider: str  # 'lmstudio' | 'openai'
    model: str
    base_url: Optional[str] = None  # requerido para lmstudio
    api_key: Optional[str] = None   # requerido para openai (o dummy para lmstudio)


def ask_provider() -> ProviderConfig:
    print(Fore.CYAN + "Elegí proveedor de modelo: (lmstudio/openai) [lmstudio]: " + Style.RESET_ALL, end="")
    p = input().strip().lower() or "lmstudio"
    if p not in ("lmstudio", "openai"):
        p = "lmstudio"

    if p == "lmstudio":
        base_url = os.environ.get("LMSTUDIO_BASE_URL") or "http://192.168.2.84:5544/v1"
        print(Fore.CYAN + f"Base URL LM Studio [{base_url}]: " + Style.RESET_ALL, end="")
        entered = input().strip()
        base_url = entered or base_url
        model = os.environ.get("LMSTUDIO_MODEL") or "qwen3-4b-2507"
        print(Fore.CYAN + f"Modelo LM Studio [{model}]: " + Style.RESET_ALL, end="")
        m_in = input().strip()
        model = m_in or model
        api_key = os.environ.get("LMSTUDIO_API_KEY") or "lm-studio"
        return ProviderConfig(provider=p, model=model, base_url=base_url, api_key=api_key)
    else:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print(Fore.CYAN + "OPENAI_API_KEY (se ocultará en consola): " + Style.RESET_ALL, end="")
            # evitar dependencias adicionales, entrada simple
            api_key = input().strip()
        model = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"
        print(Fore.CYAN + f"Modelo OpenAI [{model}]: " + Style.RESET_ALL, end="")
        m_in = input().strip()
        model = m_in or model
        return ProviderConfig(provider=p, model=model, api_key=api_key)


class LLM:
    def __init__(self, cfg: ProviderConfig):
        if OpenAI is None:
            raise RuntimeError("El paquete openai no está instalado")
        if cfg.provider == "lmstudio":
            self.client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        else:
            self.client = OpenAI(api_key=cfg.api_key)
        self.model = cfg.model
        self.is_lmstudio = cfg.provider == "lmstudio"

    def complete_json(self, messages: List[Dict[str, str]]) -> str:
        """Obtiene una respuesta del modelo. Se le pide que devuelva SOLO JSON."""
        sys_prompt = {
            "role": "system",
            "content": (
                "Eres un planner que decide acciones usando tools MCP. Debes SIEMPRE responder con un JSON válido. "
                "Formato:\n"
                "{\n  \"action\": \"tool\" | \"final\",\n  \"tool_name\": <string si action=tool>,\n  \"arguments\": <obj si action=tool>,\n  \"content\": <string si action=final>\n}\n"
                "No incluyas texto fuera del JSON."
            ),
        }
        full_messages = [sys_prompt] + messages
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=full_messages,
            temperature=0,
            # response_format={"type": "json_object"},  # muchos servidores compatibles lo soportan
        )
        return resp.choices[0].message.content or "{}"


def parse_json_object(s: str) -> Dict[str, Any]:
    # intenta parsear un objeto JSON de la respuesta
    try:
        return json.loads(s)
    except Exception:
        # fallback: extraer el primer {...}
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(s[start : end + 1])
            except Exception:
                pass
    raise ValueError("No se pudo parsear JSON de la respuesta del modelo")


def pretty_tools(tools: List[Any]) -> str:
    lines = []
    for t in tools:
        name = getattr(t, "name", "")
        desc = getattr(t, "description", "") or ""
        schema = getattr(t, "inputSchema", None) or getattr(t, "input_schema", None)
        lines.append(f"- {name}: {desc}")
        if schema:
            try:
                schema_str = json.dumps(schema, ensure_ascii=False)
                lines.append(f"  schema: {schema_str}")
            except Exception:
                pass
    return "\n".join(lines)


async def run_agent(session: ClientSession):
    # Descubrir tools disponibles
    res = await session.list_tools()
    tools = getattr(res, "tools", res)
    tools_by_name = {}
    for t in tools:
        name = getattr(t, "name", None)
        if not name and hasattr(t, "model_dump"):
            try:
                name = t.model_dump().get("name")
            except Exception:
                name = None
        name = name or ""
        tools_by_name[name] = t

    # Mostrar tools
    print(Fore.YELLOW + "Tools disponibles:" + Style.RESET_ALL)
    print(pretty_tools(tools))

    cfg = ask_provider()
    llm = LLM(cfg)


    print(Fore.GREEN + "Escribe una instrucción en lenguaje natural (salir/exit para terminar):" + Style.RESET_ALL)
    while True:
        print(Fore.CYAN + ">> " + Style.RESET_ALL, end="")
        user_text = input().strip()
        if not user_text:
            continue
        if user_text.lower() in {"salir", "exit", "quit"}:
            print("Hasta luego!")
            break

        messages: List[Dict[str, str]] = []
        # Proveer catálogo de tools al modelo en el mensaje del usuario
        tools_text = pretty_tools(tools)
        messages.append({
            "role": "user",
            "content": (
                "Eres un asistente de timesheets (PF). Tu única función es crear, listar, actualizar, eliminar y exportar registros de tiempo, "
                "usando exclusivamente las tools: create_timesheet, list_timesheets, update_timesheet, delete_timesheet, export_timesheets, get_timesheet, get_timesheet_fields_info. "
                "Para crear o actualizar una tarea (registro), DEBES solicitar al usuario y usar los campos obligatorios de la plantilla PF: "
                "legajo_personal, fecha, cliente, contrato_division, contrato_tipo, contrato_numero, tarea, tiempo. "
                "Formatos aceptados: fecha (YYYY-MM-DD o DD/MM/YYYY) y tiempo (HH:MM, minutos enteros o horas decimales como 1.5 o '1.5h'). "
                "Puedes usar get_timesheet_fields_info para consultar cuáles son los campos obligatorios y opcionales. "
                "No inventes ni asumas valores por defecto; si falta algún dato obligatorio, primero pregúntalo y NO llames a la tool hasta tenerlo. "
                "Siempre responde SOLO con JSON válido del tipo {\"action\":\"tool\",\"tool_name\":\"...\",\"arguments\":{...}} o {\"action\":\"final\",\"content\":\"...\"}.\n\n"
                f"Tools disponibles y esquemas:\n{tools_text}\n\n"
                f"Instrucción del usuario: {user_text}"
            ),
        })

        # loop de planificación/ejecución (máx 6 pasos)
        tool_context: List[Tuple[str, Any]] = []  # (tool_name, resultado)
        for step in range(6):
            raw = llm.complete_json(messages)
            try:
                obj = parse_json_object(raw)
            except Exception as e:
                print(Fore.RED + f"Error parseando JSON del modelo: {e}" + Style.RESET_ALL)
                break

            action = str(obj.get("action", "")).lower()
            if action == "tool":
                tool_name = obj.get("tool_name")
                arguments = obj.get("arguments") or {}
                if tool_name not in tools_by_name:
                    print(Fore.RED + f"Tool desconocida: {tool_name}" + Style.RESET_ALL)
                    break
                # Ejecutar tool via MCP
                try:
                    result = await session.call_tool(tool_name, arguments=arguments)
                    # Unificar resultado legible (json/text)
                    rendered: Any = []
                    content_list = getattr(result, "content", [])
                    for c in content_list:
                        ctype = getattr(c, "type", None)
                        if ctype == "json":
                            rendered.append(getattr(c, "data", None))
                        elif ctype == "text":
                            rendered.append(getattr(c, "text", None))
                        else:
                            rendered.append(getattr(c, "text", None) or getattr(c, "data", None) or str(c))
                    if len(rendered) == 1:
                        rendered = rendered[0]
                except Exception as e:
                    rendered = {"error": str(e)}

                tool_context.append((tool_name, rendered))
                # Añadir contexto de tool al historial y pedir siguiente acción
                messages.append({
                    "role": "assistant",
                    "content": json.dumps({"action": "tool", "tool_name": tool_name, "arguments": arguments}, ensure_ascii=False),
                })
                messages.append({
                    "role": "user",
                    "content": "Resultado de la tool {name}:\n".format(name=tool_name) + json.dumps(rendered, ensure_ascii=False),
                })
                continue
            elif action == "final":
                content = obj.get("content") or "(sin contenido)"
                print(Fore.MAGENTA + "Respuesta final:" + Style.RESET_ALL)
                print(content)
                break
            else:
                print(Fore.RED + f"Acción desconocida: {action}" + Style.RESET_ALL)
                break
        else:
            print(Fore.RED + "Se alcanzó el máximo de pasos sin respuesta final." + Style.RESET_ALL)


async def main():
    colorama_init()
    # Arranca el servidor MCP por stdio: python -m server.server
    # Esto inicia el transporte stdio para el protocolo MCP.
    python_bin = sys.executable
    server_module = "server.server"
    async with stdio_client(StdioServerParameters(command=python_bin, args=["-m", server_module])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            await run_agent(session)


if __name__ == "__main__":
    asyncio.run(main())
