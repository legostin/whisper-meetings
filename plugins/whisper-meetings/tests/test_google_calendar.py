import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import meetings as m
import calendar_links as links
import google_calendar as g


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('WHISPER_MEETINGS_HOME', str(tmp_path))
    monkeypatch.setattr(m, 'spawn', lambda *_: None)
    monkeypatch.setattr(g, 'client', lambda: {'client_id': 'synthetic.apps.googleusercontent.com'})


def test_meet_link_retained_in_final_read_and_handoff_without_calendar():
    item = m.create('Manual call', 'capture', 'small', None, False)
    transcript = m.write_transcript(item, [{'source':'microphone','start':0,'end':1,'text':'Release Friday'}], {})
    m.update(item['id'], state='ready')
    url = 'https://meet.google.com/abc-defg-hij'
    links.link_url(item['id'], url)
    read = m.read_transcript(item['id'])
    assert read['meeting_url'] == url and read['sha256'] == transcript['sha256']
    package = m.handoff(item['id'], 'product', 'Prepare release')
    assert json.loads(Path(package['json']).read_text())['meeting_url'] == url
    assert url in Path(package['markdown']).read_text()
    links.link_url(item['id'], None)
    assert m.get(item['id'])['meeting_url'] is None


@pytest.mark.parametrize('url', ['https://meet.google.com.attacker.example/a', 'https://user@meet.google.com/a',
                               'https://meet.google.com:1234/a', 'javascript:alert(1)', 'https://meet.google.com/'])
def test_manual_link_validation(url):
    with pytest.raises(ValueError):
        links.validate_meet_url(url)


@pytest.mark.parametrize('path', ['/other?state=expected&code=code', '/callback?state=wrong&code=code',
                                '/callback?state=expected&state=wrong&code=code', '/callback?state=expected',
                                '/callback?state=expected&error=access_denied'])
def test_callback_rejects_invalid_state_path_codes_and_denial(path):
    with pytest.raises(ValueError):
        g.callback_parameters(path, 'expected')
    assert g.callback_parameters('/callback?state=expected&code=synthetic-code', 'expected') == 'synthetic-code'


def event(**changes):
    return {'id':'event-123', 'summary':'Planning', 'start':{'dateTime':'2026-10-02T10:00:00+05:00'},
            'end':{'dateTime':'2026-10-02T11:00:00+05:00'}, 'attendees':[{'email':'private@example.com'}],
            'description':'Private details', 'conferenceData':{'entryPoints':[{'entryPointType':'video','uri':'https://meet.google.com/abc-defg-hij'}]}, **changes}


def test_google_mapping_discards_unneeded_data_and_handles_all_day():
    events = g.normalize_events([event(), event(status='cancelled'), event(id='all-day', start={'date':'2026-10-02'},end={'date':'2026-10-03'})])
    assert len(events) == 2
    assert events[0]['meet_url'] == 'https://meet.google.com/abc-defg-hij'
    assert events[1]['start'] == '2026-10-02'
    assert 'attendees' not in events[0] and 'description' not in events[0]


def test_google_refresh_uses_only_read_endpoint_and_minimal_fields(monkeypatch):
    g.save_state(state='connected')
    monkeypatch.setattr(g, 'access_token', lambda:'synthetic-token')
    calls=[]
    def request(url, data=None, access_token=None):
        calls.append((url,data,access_token))
        return {'items':[event()]}
    monkeypatch.setattr(g,'request_json',request)
    assert g.refresh_events()['count']==1
    url,data,token=calls[0]
    assert url.startswith('https://www.googleapis.com/calendar/v3/calendars/primary/events?')
    params=parse_qs(urlparse(url).query)
    assert params['singleEvents']==['true'] and params['maxResults']==['100'] and data is None
    assert 'attendees' not in params['fields'][0] and 'description' not in params['fields'][0]
    assert links.options()['source']=='google_calendar_direct'


def test_token_refresh_stays_out_of_panel_results(monkeypatch):
    token={'refresh_token':'synthetic-refresh','access_token':'expired','expires_at':0}
    writes=[]
    monkeypatch.setattr(g,'credentials',lambda op,value=None: token if op=='read' else writes.append(value))
    monkeypatch.setattr(g,'request_json',lambda url,data=None,**k: {'access_token':'fresh','expires_in':3600})
    assert g.access_token()=='fresh' and writes[0]['refresh_token']=='synthetic-refresh'
    assert 'synthetic-refresh' not in json.dumps(links.options())
    assert 'access_token' not in json.dumps(g.state())


def test_disconnect_invalidates_pending_flow_and_preserves_saved_event(monkeypatch):
    item=m.create('Call','capture','small',None,False)
    m.update(item['id'],calendar_event={'title':'retained'})
    g.save_state(state='authorizing',flow='pending',expires_at=9999999999)
    m.atomic_json(m.data_home()/'calendar-events.json',{'source':'google_calendar_direct','events':[event()]})
    operations=[]
    monkeypatch.setattr(g,'credentials',lambda op,value=None:operations.append(op))
    result=g.disconnect()
    assert result['local_credentials_removed'] and operations==['read','delete']
    assert g.state()['state']=='disconnected' and 'flow' not in g.state()
    assert links.options()['events']==[] and m.get(item['id'])['calendar_event']=={'title':'retained'}


def start_callback(monkeypatch):
    import threading
    import time
    g.save_state(state='starting',flow='fixture-flow',expires_at=time.time()+600)
    worker=threading.Thread(target=g.authorize,args=('fixture-flow',),daemon=True)
    worker.start()
    deadline=time.monotonic()+5
    while g.state()['state']=='starting' and time.monotonic()<deadline:
        time.sleep(0.01)
    params=parse_qs(urlparse(g.state()['auth_url']).query)
    return worker,params


def test_loopback_callback_validates_host_state_and_pkce_before_keychain_write(monkeypatch):
    import base64,hashlib
    from urllib.request import Request,urlopen
    from urllib.error import HTTPError
    calls,writes=[],[]
    def request(url,data=None,**kwargs):
        calls.append((url,data))
        return {'access_token':'synthetic-access','refresh_token':'synthetic-refresh','scope':g.SCOPE,'expires_in':3600}
    monkeypatch.setattr(g,'request_json',request)
    monkeypatch.setattr(g,'credentials',lambda op,value=None:writes.append((op,value)))
    monkeypatch.setattr(g,'refresh_events',lambda:calls.append(('refresh',None)))
    worker,params=start_callback(monkeypatch)
    callback=params['redirect_uri'][0]
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(Request(callback+'?state='+params['state'][0]+'&code=synthetic-code',headers={'Host':'attacker.example'}),timeout=2)
        assert error.value.code==400 and calls==[] and writes==[]
        with pytest.raises(HTTPError):
            urlopen(callback+'?state=wrong&code=synthetic-code',timeout=2)
        assert calls==[] and writes==[]
        with urlopen(callback+'?state='+params['state'][0]+'&code=synthetic-code',timeout=2) as response:
            html=response.read().decode()
            assert response.headers['Cache-Control']=='no-store'
        worker.join(2)
        assert not worker.is_alive() and g.state()['state']=='connected'
        exchange=calls[0][1]
        challenge=base64.urlsafe_b64encode(hashlib.sha256(exchange['code_verifier'].encode()).digest()).rstrip(b'=').decode()
        assert params['code_challenge']==[challenge] and params['code_challenge_method']==['S256']
        assert exchange['redirect_uri']==callback and calls[1][0]=='refresh'
        assert writes[0][0]=='write' and writes[0][1]['refresh_token']=='synthetic-refresh'
        assert 'synthetic-access' not in html and 'synthetic-code' not in html
        assert 'auth_url' not in g.state() and 'refresh_token' not in json.dumps(links.options())
    finally:
        g.save_state(state='disconnected')
        worker.join(2)


def test_disconnect_during_token_exchange_cannot_recreate_credentials(monkeypatch):
    from urllib.request import urlopen
    writes=[]
    monkeypatch.setattr(g,'credentials',lambda op,value=None:writes.append((op,value)))
    def request(*args,**kwargs):
        g.disconnect()
        return {'access_token':'synthetic-access','refresh_token':'synthetic-refresh','scope':g.SCOPE}
    monkeypatch.setattr(g,'request_json',request)
    worker,params=start_callback(monkeypatch)
    try:
        with urlopen(params['redirect_uri'][0]+'?state='+params['state'][0]+'&code=synthetic-code',timeout=2) as response:
            assert 'could not finish' in response.read().decode()
        worker.join(2)
        assert g.state()['state']=='disconnected' and not any(op=='write' for op,_ in writes)
    finally:
        g.save_state(state='disconnected')
        worker.join(2)


def test_expired_grant_marks_reconnect_without_exposing_tokens(monkeypatch):
    g.save_state(state='connected')
    def expired():
        raise g.GoogleAuthRequired('Google Calendar access expired. Connect again.')
    monkeypatch.setattr(g,'access_token',expired)
    with pytest.raises(g.GoogleAuthRequired):g.refresh_events()
    assert g.state()['state']=='failed' and 'Connect again' in g.state()['error']


def test_invalid_provider_event_does_not_block_valid_events():
    assert len(g.normalize_events([event(start={'dateTime':'invalid'}),event()]))==1
