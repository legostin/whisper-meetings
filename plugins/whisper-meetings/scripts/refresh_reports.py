"""Reformat existing local Markdown reports; audio, JSON and hashes stay intact."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import meetings


def main():
    refreshed = 0
    for path in (meetings.data_home() / 'meetings').glob('*/analysis.json'):
        item = json.loads((path.parent / 'meeting.json').read_text())
        item['directory'] = str(path.parent)
        meetings.write_report(item, json.loads(path.read_text()))
        refreshed += 1
    print(f'Reformatted {refreshed} local Markdown reports; original JSON/audio preserved.')


if __name__ == '__main__':
    main()
