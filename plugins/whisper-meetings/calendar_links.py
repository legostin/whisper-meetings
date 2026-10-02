"""Validated minimal meeting associations and direct Google picker metadata."""
import json
from datetime import datetime
from urllib.parse import urlparse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import meetings


def validate_meet_url(value):
    if value is None or not value.strip():
        return None
    value = value.strip()
    url = urlparse(value)
    if (url.scheme != 'https' or url.hostname != 'meet.google.com' or url.username or url.password
            or url.port not in (None, 443) or not url.path.strip('/')):
        raise ValueError('Paste a valid HTTPS Google Meet link')
    return value


def link_url(meeting_id, value):
    url = validate_meet_url(value)
    item = meetings.update(meeting_id, meeting_url=url)
    return {'meeting_id': item['id'], 'meeting_url': url, 'calendar_modified': False}


class CalendarEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    calendar_id: str = Field(default='primary', min_length=1, max_length=1024)
    event_id: str = Field(min_length=1, max_length=1024)
    title: str = Field(min_length=1, max_length=240)
    start: str = Field(max_length=64)
    end: str = Field(max_length=64)
    meet_url: str | None = Field(default=None, max_length=2048)
    event_url: str | None = Field(default=None, max_length=4096)

    @field_validator('title', 'calendar_id', 'event_id')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Event identifiers and title must not be blank')
        return value.strip()

    @field_validator('start', 'end')
    @classmethod
    def valid_time(cls, value):
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if 'T' in value and parsed.tzinfo is None:
            raise ValueError('Timed events require a timezone offset')
        return value

    @model_validator(mode='after')
    def valid_window(self):
        start, end = [datetime.fromisoformat(v.replace('Z', '+00:00')) for v in (self.start, self.end)]
        try:
            if end <= start:
                raise ValueError('Event end must be after start')
        except TypeError:
            raise ValueError('Start and end must both be timed or all-day dates')
        return self

    @field_validator('meet_url', 'event_url')
    @classmethod
    def safe_url(cls, value, info):
        if value is None:
            return value
        url = urlparse(value)
        allowed = {'meet.google.com'} if info.field_name == 'meet_url' else {'calendar.google.com', 'www.google.com'}
        if url.scheme != 'https' or url.hostname not in allowed or url.username or url.password or url.port not in (None,443):
            raise ValueError('Use a genuine HTTPS Google Meet or Google Calendar URL')
        if info.field_name == 'event_url' and url.hostname == 'www.google.com' and not url.path.startswith('/calendar/'):
            raise ValueError('Use a Google Calendar event URL')
        return value


def options():
    path = meetings.data_home() / 'calendar-events.json'
    payload = json.loads(path.read_text()) if path.exists() else {'events': [], 'updated_at': None}
    import google_calendar
    payload['connection'] = {key: value for key, value in google_calendar.state().items() if key != 'flow'}
    return payload


def stage(events):
    if len(events) > 100:
        raise ValueError('Stage at most 100 selected event summaries')
    normalized = [CalendarEvent.model_validate(e).model_dump() for e in events]
    if len({(e['calendar_id'], e['event_id']) for e in normalized}) != len(normalized):
        raise ValueError('Duplicate calendar event IDs')
    payload = {'events': normalized, 'updated_at': meetings.now(), 'source': 'user_or_host_supplied_metadata'}
    meetings.atomic_json(meetings.data_home() / 'calendar-events.json', payload)
    return {'count': len(normalized), 'updated_at': payload['updated_at']}


def resolve(calendar_id, event_id):
    event = next((e for e in options()['events'] if e['calendar_id'] == calendar_id and e['event_id'] == event_id), None)
    if event is None:
        raise ValueError('Event not staged; supply event metadata or refresh the calendar selection')
    return CalendarEvent.model_validate(event).model_dump()


def link(meeting_id, event):
    normalized = CalendarEvent.model_validate(event).model_dump()
    meetings.get(meeting_id)  # Validate the ID before any write.
    item = meetings.update(meeting_id, calendar_event=normalized)
    return {'meeting_id': item['id'], 'calendar_event': item['calendar_event'], 'calendar_modified': False}
