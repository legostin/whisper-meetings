"""Loopback-only MCP Apps preview with clearly labelled synthetic meeting data.
Never calls the recorder, opens real audio, or writes a meeting archive.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import json
import secrets
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/whisper-meetings'))
import reporting
TOKEN = secrets.token_urlsafe(24)
MEETINGS = [
 {"id":"demo-planning","title":"Планирование продукта","state":"ready","created_at":"2026-10-01T08:30:00Z","directory":"/demo/meetings/planning","model":"small","transcribe_on_stop":True},
 {"id":"demo-team","title":"Синхронизация команды","state":"recorded","created_at":"2026-09-30T08:00:00Z","directory":"/demo/meetings/team","model":"small","transcribe_on_stop":False},
]
EVENT={"calendar_id":"primary","event_id":"demo-event","title":"Планирование продукта","start":"2026-10-01T13:30:00+05:00","end":"2026-10-01T14:00:00+05:00","meet_url":"https://meet.google.com/abc-defg-hij","event_url":"https://calendar.google.com/calendar/event?eid=demo"}
MEETINGS[0]['calendar_event']=EVENT
MEETINGS[0].update(diarization_status='complete',diarize_on_stop=True,transcript_sha256='demo-sha')
SPEAKERS=[{'id':'microphone:A','source':'microphone','name':None},{'id':'system:A','source':'system','name':None},{'id':'system:B','source':'system','name':None}]
SHA='demo-sha'
SEGMENTS = [
 {"id":"s00001","start":12,"end":19,"source":"microphone","text":"Предлагаю запустить первую версию в пятницу. Начнём с записи и расшифровки."},
 {"id":"s00002","start":22,"end":30,"source":"system","text":"Согласна. Я подготовлю инструкцию по установке и проверю её на чистом Mac."},
 {"id":"s00003","start":35,"end":42,"source":"microphone","text":"Ещё нужно проверить разрешения macOS и восстановление после сбоя. Без этого релиз рискованный."},
 {"id":"s00004","start":48,"end":57,"source":"system","text":"Нужен ли экспорт в другие чаты уже в первой версии? Давайте решим после тестирования."},
]
for segment in SEGMENTS:
    segment.update(speaker_id=segment['source']+':A',speaker_ids=[segment['source']+':A'],overlapping_speech=False,speaker_assignment='estimated')
SEGMENTS[-1].update(speaker_id=None,speaker_ids=['system:A','system:B'],overlapping_speech=True,speaker_assignment='uncertain')
ANALYSIS = {"summary":"Команда согласовала запуск первой версии в пятницу.","overview":[{"title":"Что входит в первую версию","points":["Запись встречи и локальная расшифровка.","Выбор источников звука в зависимости от наушников."]},{"title":"Что нужно до релиза","points":["Проверить установку на чистом Mac.","Проверить разрешения и восстановление записи после сбоя."]}],"decisions":[{"text":"Запустить первую версию с записью и расшифровкой в пятницу.","evidence_segment_ids":["s00001","s00002"]}],"action_items":[{"text":"Подготовить инструкцию по установке и проверить её на чистом Mac.","owner":None,"due_date":None,"evidence_segment_ids":["s00002"]}],"risks":[{"text":"Разрешения macOS и восстановление после сбоя требуют проверки до релиза.","evidence_segment_ids":["s00003"]}],"open_questions":[{"text":"Включать ли экспорт в другие чаты в первую версию?","evidence_segment_ids":["s00004"]}],"transcript_sha256":"demo-sha"}
CALLS = []

def invoke(name, args):
    global SHA
    CALLS.append({"name":name,"arguments":args})
    item = next((m for m in MEETINGS if m['id']==args.get('meeting_id')),None)
    if name=='meetings_panel_state':
        return {"setup":{"capture_available":True,"models":["small","base"],"permissions":{"microphone":"authorized","screen_audio":True},"data_directory":"/demo/local-archive","diarization":{"available":True,"model_installed":True,"account_required":False}},"meetings":MEETINGS,"calendar":{"events":[EVENT],"updated_at":"2026-10-01T08:00:00Z"}}
    if name=='meetings_read_transcript':
        return {"segments":SEGMENTS[args.get('offset',0):args.get('offset',0)+args.get('limit',100)],"total_segments":len(SEGMENTS),"next_offset":None,"sha256":SHA,"speakers":SPEAKERS,"diarization":{"status":"complete","note":"Synthetic speaker estimates; no identities inferred"}}
    if name=='meetings_read_analysis':return {"analysis":reporting.view(ANALYSIS) if item['id']=='demo-planning' and SHA=='demo-sha' else None}
    if name=='meetings_diarize':item.update(state='ready',diarization_status='complete');return item
    if name=='meetings_rename_speaker':
        speaker=next(s for s in SPEAKERS if s['id']==args['speaker_id']);speaker['name']=args['name'];SHA='demo-sha-renamed';item['transcript_sha256']=SHA;return {'speaker_id':speaker['id'],'name':speaker['name'],'transcript_sha256':SHA}
    if name=='meetings_start':
        if any(m['state']=='recording' for m in MEETINGS):raise ValueError('Demo recording already active')
        item={"id":"demo-active-"+secrets.token_hex(4),"title":args['title'],"state":"recording","created_at":datetime.now(timezone.utc).isoformat(),"started_at":datetime.now(timezone.utc).isoformat(),"model":args['model'],"transcribe_on_stop":args['transcribe_on_stop'],"diarize_on_stop":args.get('diarize',False),"language":args.get('language')}
        if args.get('calendar_event_id'):item['calendar_event']=EVENT
        item.update(headphones=args.get('headphones',False),capture_sources=['microphone','system'] if args.get('headphones',False) else ['microphone']);MEETINGS.insert(0,item);return item
    if name=='meetings_stop':item['state']='ready' if args.get('transcribe',item['transcribe_on_stop']) else 'recorded';return item
    if name=='meetings_set_transcription':item['transcribe_on_stop']=args['enabled'];return item
    if name=='meetings_transcribe':item['state']='ready';return item
    if name=='meetings_link_calendar_event':item['calendar_event']=args['event'];return item
    if name=='meetings_prepare_handoff':return {"json":"/demo/handoff/context.json","markdown":"/demo/handoff/context.md","delivery":"local_file_only; no message sent"}
    if name=='meetings_import':raise ValueError('File import is disabled in the synthetic preview; use the actual plugin.')
    raise ValueError('Unsupported demo tool')

PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Whisper Meetings · Demo</title><style>body{margin:0;background:#fff;font:12px system-ui}header{padding:10px 18px;background:#f5f5f5;color:#666}iframe{width:100%;height:calc(100vh - 38px);border:0;display:block}</style><header>PREVIEW · Synthetic data · Microphone is not activated <button id="mode">Inline / Fullscreen</button><button id="theme">Light / Dark</button></header><iframe title="Whisper Meetings panel" src="/widget" sandbox="allow-scripts allow-same-origin"></iframe><script>
const frame=document.querySelector('iframe');let mode='fullscreen',theme='light';document.querySelector('#mode').onclick=()=>{mode=mode==='fullscreen'?'inline':'fullscreen';frame.contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/host-context-changed',params:{displayMode:mode}},location.origin);};document.querySelector('#theme').onclick=()=>{theme=theme==='light'?'dark':'light';frame.contentWindow.postMessage({jsonrpc:'2.0',method:'ui/notifications/host-context-changed',params:{theme}},location.origin);};
window.addEventListener('message',async event=>{
 if(event.source!==frame.contentWindow || event.origin!==location.origin)return;
 const msg=event.data;if(!msg || msg.jsonrpc!=='2.0' || msg.id===undefined)return;
 let result;
 try {
 if(msg.method==='ui/initialize')result={protocolVersion:msg.params.protocolVersion,hostInfo:{name:'Synthetic Preview Host',version:'0.4.1'},hostCapabilities:{serverTools:{},message:{text:{}},logging:{}},hostContext:{theme:'light',locale:'ru-RU',displayMode:'fullscreen',availableDisplayModes:['inline','fullscreen'],platform:'desktop'}};
 else if(msg.method==='ui/request-display-mode')result={mode:msg.params.mode};
 else if(msg.method==='tools/call'){const response=await fetch('/rpc',{method:'POST',headers:{'Content-Type':'application/json','X-Preview-Token':'TOKEN'},body:JSON.stringify(msg.params)});result=await response.json();}
 else if(msg.method==='ui/message'){await fetch('/message',{method:'POST',headers:{'Content-Type':'application/json','X-Preview-Token':'TOKEN'},body:JSON.stringify(msg.params)});result={};document.querySelector('header').textContent='PREVIEW · Request received by test host · No message sent to Codex';}
 else result={};
 frame.contentWindow.postMessage({jsonrpc:'2.0',id:msg.id,result},location.origin);
 }catch(error){frame.contentWindow.postMessage({jsonrpc:'2.0',id:msg.id,error:{code:-32603,message:error.message}},location.origin);}
});
</script></html>'''.replace('TOKEN',TOKEN)

class Handler(BaseHTTPRequestHandler):
    def send(self, payload, mime='application/json'):
        raw=payload.encode() if isinstance(payload,str) else payload
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/':self.send(PAGE,'text/html; charset=utf-8')
        elif self.path=='/widget':self.send((ROOT/'plugins/whisper-meetings/web/dist/widget.html').read_bytes(),'text/html; charset=utf-8')
        elif self.path=='/calls':self.send(json.dumps(CALLS))
        else:self.send_error(404)
    def do_POST(self):
        if self.headers.get('X-Preview-Token')!=TOKEN:self.send_error(403);return
        args=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        if self.path=='/message':CALLS.append({'message':args});self.send('{}');return
        try:result=invoke(args['name'],args.get('arguments',{}));self.send(json.dumps({'content':[{'type':'text','text':json.dumps(result)}],'structuredContent':{'result':result}}))
        except Exception as exc:self.send(json.dumps({'isError':True,'content':[{'type':'text','text':str(exc)}]}))
    def log_message(self,*args):pass

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8768);args=parser.parse_args()
    print(f'Synthetic preview: http://127.0.0.1:{args.port}',flush=True)
    ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
