"""Exercise the real installed process through MCP, without model/API spending."""
import asyncio
import json
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command=sys.executable, args=[sys.argv[1]])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            names = {t.name for t in tools.tools}
            assert {'estado_integracion', 'oportunidades_camino_blanco', 'importar_excel_compra_agil', 'preparar_propuesta', 'completar_anexo_comprador'} <= names
            state = await client.call_tool('estado_integracion', {})
            assert not state.isError
            rows = await client.call_tool('oportunidades_camino_blanco', {'busqueda': '2403-844-COT26'})
            assert not rows.isError
            encoded = json.dumps(rows.model_dump(), ensure_ascii=False)
            assert '2403-844-COT26' in encoded and 'INVESTIGAR' in encoded
            print(json.dumps({'mcp_handshake': 'OK', 'tools': len(names), 'consulta_real_local': 'OK', 'estado': state.model_dump()}, ensure_ascii=False))

if __name__ == '__main__':
    asyncio.run(main())
