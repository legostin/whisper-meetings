"""Direct Google Desktop OAuth + PKCE; tokens in Mac Keychain, API reads only."""
import base64
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import meetings

SCOPE = 'https://www.googleapis.com/auth/calendar.events.readonly'
AUTH = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN = 'https://oauth2.googleapis.com/token'


class GoogleAuthRequired(ValueError):
    pass


def client():
    private = meetings.data_home() / 'google-client.json'
    path = private
    if not path.exists():
        raise ValueError('Google sign-in is not available in this build. You can paste a Meet link instead.')
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or 'web' in data:
            raise ValueError
        data = data.get('installed', data)
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, OSError):
        raise ValueError('A valid Google Desktop OAuth client is required for this build.') from None
    if not isinstance(data.get('client_id'), str) or not data['client_id'].endswith('.apps.googleusercontent.com') or not isinstance(data.get('client_secret'), str) or not data['client_secret']:
        raise ValueError('A Google Desktop OAuth client is required for this build.')
    return {key: data[key] for key in ('client_id', 'client_secret') if data.get(key)}


def credentials(operation, value=None):
    binary = meetings.data_home() / 'runtime/google-credentials'
    if not binary.is_file():
        raise ValueError('Google connection setup is incomplete. Update the local runtime first.')
    account = hashlib.sha256(str(meetings.data_home()).encode()).hexdigest()
    result = subprocess.run([str(binary), operation, account], input=json.dumps(value) if value else None,
                            text=True, capture_output=True, timeout=30)
    if operation == 'read' and result.returncode == 3:
        return None
    if result.returncode:
        raise ValueError('Google credentials are unavailable in macOS Keychain. Retry the connection.')
    return json.loads(result.stdout) if operation == 'read' else None


def state():
    path = meetings.data_home() / 'google-connection.json'
    payload = json.loads(path.read_text()) if path.exists() else {'state': 'disconnected'}
    if payload['state'] in {'starting', 'authorizing'} and payload.get('expires_at', 0) < time.time():
        payload = {'state': 'disconnected', 'error': 'Google sign-in expired. Connect again.'}
    try:
        client()
        configured = (meetings.data_home() / 'runtime/google-credentials').is_file()
    except ValueError:
        configured = False
    return {**payload, 'configured': configured}


def save_state(**payload):
    meetings.atomic_json(meetings.data_home() / 'google-connection.json', payload)


def request_json(url, data=None, access_token=None):
    headers = {'Accept': 'application/json'}
    if access_token:
        headers['Authorization'] = 'Bearer ' + access_token
    body = urlencode(data).encode() if data is not None else None
    try:
        with urlopen(Request(url, data=body, headers=headers), timeout=15) as response:
            return json.load(response)
    except HTTPError as exc:
        # Do not surface provider payloads, access tokens, codes or request URLs.
        try:
            reason = json.loads(exc.read(65536)).get('error')
        except (ValueError, AttributeError):
            reason = None
        if exc.code == 401 or reason == 'invalid_grant':
            raise GoogleAuthRequired('Google Calendar access expired. Connect again.') from None
        raise ValueError('Google could not complete this request. Check Calendar API access and try again.') from None
    except (URLError, TimeoutError):
        raise ValueError('Could not reach Google. Check your connection and retry.') from None


def connection_lock():
    return (meetings.data_home() / 'google-account.lock').open('a')


def access_token():
    token = credentials('read')
    if not token:
        raise ValueError('Connect Google to load your meetings.')
    if token.get('expires_at', 0) > time.time() + 60:
        return token['access_token']
    if not token.get('refresh_token'):
        raise GoogleAuthRequired('Google Calendar access expired. Connect again.')
    fresh = request_json(TOKEN, {**client(), 'grant_type': 'refresh_token', 'refresh_token': token['refresh_token']})
    token.update(access_token=fresh['access_token'], expires_at=time.time() + fresh.get('expires_in', 3600))
    credentials('write', token)
    return token['access_token']


def normalize_events(items):
    from calendar_links import CalendarEvent, validate_meet_url
    events = []
    for event in items:
        if event.get('status') == 'cancelled':
            continue
        start = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
        end = event.get('end', {}).get('dateTime') or event.get('end', {}).get('date')
        if not start or not end or not event.get('id'):
            continue
        meet_url = event.get('hangoutLink')
        if not meet_url:
            meet_url = next((e.get('uri') for e in event.get('conferenceData', {}).get('entryPoints', [])
                             if e.get('entryPointType') == 'video' and urlparse(e.get('uri', '')).hostname == 'meet.google.com'), None)
        try:
            meet_url = validate_meet_url(meet_url)
        except ValueError:
            meet_url = None
        value = {'calendar_id': 'primary', 'event_id': event['id'], 'title': (event.get('summary') or 'Untitled meeting')[:240],
                 'start': start, 'end': end, 'meet_url': meet_url, 'event_url': event.get('htmlLink')}
        try:
            events.append(CalendarEvent.model_validate(value).model_dump())
        except ValueError:
            value['event_url'] = None
            try:
                events.append(CalendarEvent.model_validate(value).model_dump())
            except ValueError:
                continue  # Skip malformed provider events without losing valid choices.
    return events


def refresh_events():
    with connection_lock() as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if state()['state'] != 'connected':
            raise ValueError('Connect Google to load your meetings.')
        try:
            token = access_token()
        except GoogleAuthRequired as exc:
            save_state(state='failed', error=str(exc))
            raise
        current = datetime.now(timezone.utc)
        query = {'timeMin': (current-timedelta(hours=2)).isoformat(), 'timeMax': (current+timedelta(days=7)).isoformat(),
                 'singleEvents': 'true', 'orderBy': 'startTime', 'maxResults': 100,
                 'fields': 'items(id,summary,start,end,htmlLink,hangoutLink,conferenceData(entryPoints(entryPointType,uri))),nextPageToken'}
        try:
            result = request_json('https://www.googleapis.com/calendar/v3/calendars/primary/events?' + urlencode(query), access_token=token)
        except GoogleAuthRequired as exc:
            save_state(state='failed', error=str(exc))
            raise
        events = normalize_events(result.get('items', []))
        meetings.atomic_json(meetings.data_home() / 'calendar-events.json',
                             {'events': events, 'updated_at': meetings.now(), 'source': 'google_calendar_direct',
                              'has_more': bool(result.get('nextPageToken'))})
        save_state(state='connected')
        return {'count': len(events), 'updated_at': meetings.now()}


def connect():
    client()
    if not (meetings.data_home() / 'runtime/google-credentials').is_file():
        raise ValueError('Update the local runtime to enable Google sign-in.')
    with (meetings.data_home() / 'google-launch.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        current = state()
        if current['state'] == 'authorizing':
            return open_sign_in(current)
        flow = secrets.token_urlsafe(32)
        save_state(state='starting', flow=flow, expires_at=time.time()+600)
        with (meetings.data_home() / 'google-connection.log').open('ab') as log:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), flow], stdin=subprocess.DEVNULL,
                             stdout=log, stderr=log, start_new_session=True)
        for _ in range(60):
            current = state()
            if current['state'] != 'starting':
                return open_sign_in(current)
            time.sleep(0.05)
        raise ValueError('Google sign-in is starting. Try Connect Google again.')


def open_sign_in(current):
    opened = False
    if current.get('auth_url') and sys.platform == 'darwin':
        result = subprocess.run(['/usr/bin/open', current['auth_url']], capture_output=True, timeout=10)
        opened = result.returncode == 0
    return {**current, 'browser_opened': opened}


def disconnect():
    with connection_lock() as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        save_state(state='disconnected')  # Invalidates an in-flight callback.
        token = credentials('read')
        credentials('delete')
        snapshot = meetings.data_home() / 'calendar-events.json'
        if snapshot.exists() and json.loads(snapshot.read_text()).get('source') == 'google_calendar_direct':
            snapshot.unlink()
    revoked = True
    if token:
        try:
            with urlopen(Request('https://oauth2.googleapis.com/revoke', data=urlencode({'token': token.get('refresh_token') or token['access_token']}).encode()), timeout=15):
                pass
        except (HTTPError, URLError, TimeoutError):
            revoked = False
    return {'state': 'disconnected', 'google_grant_revoked': revoked, 'local_credentials_removed': True}


def callback_parameters(path, expected_state):
    parsed = urlparse(path)
    if parsed.path != '/callback':
        raise ValueError('Invalid callback path')
    values = parse_qs(parsed.query)
    if len(values.get('state', [])) != 1 or not secrets.compare_digest(values['state'][0], expected_state):
        raise ValueError('Invalid sign-in state')
    if values.get('error'):
        raise ValueError('Google sign-in was cancelled. Connect again when ready.')
    if len(values.get('code', [])) != 1 or not values['code'][0]:
        raise ValueError('Missing authorization code')
    return values['code'][0]


def authorize(flow):
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    oauth_state = secrets.token_urlsafe(32)
    done = False
    class Callback(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(10)
            super().setup()
        def log_message(self, *_):
            pass  # Never log the URL containing the authorization code.
        def do_GET(self):
            nonlocal done
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                self.send_error(400); return
            try:
                code = callback_parameters(self.path, oauth_state)
            except ValueError:
                params = parse_qs(urlparse(self.path).query)
                if (urlparse(self.path).path == '/callback' and params.get('state') == [oauth_state]
                        and params.get('error') and state().get('flow') == flow):
                    save_state(state='failed', error='Google sign-in was cancelled. Connect again when ready.')
                    done = True
                self.send_error(400, 'Invalid Google sign-in response'); return
            try:
                token = request_json(TOKEN, {**client(), 'code': code, 'code_verifier': verifier,
                                            'redirect_uri': redirect, 'grant_type': 'authorization_code'})
                if SCOPE not in token.get('scope', '').split() or not token.get('access_token') or not token.get('refresh_token'):
                    raise ValueError('Calendar permission was not granted. Connect again and allow calendar access.')
                with connection_lock() as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX)
                    if state().get('flow') != flow:
                        raise ValueError('This sign-in request was cancelled.')
                    credentials('write', {'access_token': token['access_token'], 'refresh_token': token['refresh_token'],
                                          'expires_at': time.time()+token.get('expires_in', 3600)})
                    save_state(state='connected')
                try:
                    refresh_events()
                except Exception:
                    with connection_lock() as lock:
                        fcntl.flock(lock, fcntl.LOCK_EX)
                        if state()['state'] == 'connected':
                            save_state(state='connected', error='Connected. Calendar could not load yet; choose Refresh meetings.')
                message = 'Google Calendar connected. You can close this tab and return to Whisper Meetings.'
            except Exception:
                # Keep errors generic; a provider response never reaches UI/logs.
                message = 'Google connection could not finish. Return to Whisper Meetings and retry.'
                if state().get('flow') == flow:
                    save_state(state='failed', error='Google sign-in failed. Please reconnect.')
            done = True
            content = ('<!doctype html><meta charset="utf-8"><title>Whisper Meetings</title><p>'+message+'</p>').encode()
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store'); self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'none'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(content)
    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 0.5
        redirect = f'http://127.0.0.1:{server.server_port}/callback'
        url = AUTH+'?'+urlencode({**{'client_id':client()['client_id']}, 'redirect_uri':redirect,
            'response_type':'code', 'scope':SCOPE, 'state':oauth_state, 'code_challenge':challenge,
            'code_challenge_method':'S256', 'access_type':'offline', 'prompt':'consent select_account'})
        if state().get('flow') != flow:
            return
        save_state(state='authorizing', flow=flow, auth_url=url, expires_at=time.time()+600)
        deadline=time.monotonic()+600
        while not done and time.monotonic()<deadline and state().get('flow')==flow:
            server.handle_request()
        if not done and state().get('flow')==flow:
            save_state(state='disconnected',error='Google sign-in expired. Connect again.')


if __name__ == '__main__':
    os.umask(0o077)
    try:
        authorize(sys.argv[1])
    except Exception:
        if state().get('flow') == sys.argv[1]:
            save_state(state='failed',error='Google sign-in could not start. Retry the connection.')
