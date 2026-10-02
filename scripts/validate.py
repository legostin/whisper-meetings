"""Check official portable schemas and the actual MCP tool/resource contract."""
import asyncio
import json
from pathlib import Path
from urllib.request import urlopen
from jsonschema import Draft202012Validator
import sys

ROOT=Path(__file__).resolve().parents[1]
PLUGIN=ROOT/'plugins/whisper-meetings'
sys.path.insert(0,str(PLUGIN))
import server

for name in ('plugin','mcp'):
    data=json.loads((PLUGIN/f'{name}.json').read_text())
    with urlopen(data['$schema'],timeout=30) as response:
        schema=json.load(response)
    Draft202012Validator(schema).validate(data)
manifest=json.loads((PLUGIN/'plugin.json').read_text())
for key in ('composerIcon','composerIconDark','logo','logoDark'):
    assert (PLUGIN/manifest['extensions']['com.openai']['interface'][key]).is_file()
assert (PLUGIN/'web/dist/widget.html').stat().st_size<2_000_000
assert '/* WIDGET_SCRIPT */' not in (PLUGIN/'web/dist/widget.html').read_text()
assert not list(PLUGIN.rglob('node_modules'))

async def check():
    tools=await server.mcp.list_tools()
    assert len(tools)==26
    for tool in tools:
        assert tool.description and tool.inputSchema['type']=='object'
        assert all(isinstance(getattr(tool.annotations,key),bool) for key in ('readOnlyHint','destructiveHint','openWorldHint'))
    for name in ('meetings_connect_google','meetings_refresh_google_calendar','meetings_disconnect_google'):
        assert next(tool for tool in tools if tool.name==name).meta['ui']['visibility']==['app']
    panel=next(tool for tool in tools if tool.name=='meetings_open_panel')
    assert panel.meta['ui']['resourceUri']==server.PANEL_URI
    assert panel.meta['openai/ui']['entrypoints']==[{'type':'global'},{'type':'thread'}]
    resources=await server.mcp.list_resources()
    resource=next(r for r in resources if str(r.uri)==server.PANEL_URI)
    assert resource.mimeType=='text/html;profile=mcp-app'
    assert resource.meta['ui']['csp']=={'connectDomains':[],'resourceDomains':[]}
    html=(await server.mcp.read_resource(server.PANEL_URI))[0].content
    assert 'Whisper Meetings' in html
    print(f'PASS: official Agent Plugins schemas; {len(tools)} tools; MCP Apps resource and OpenAI entrypoints')

asyncio.run(check())
