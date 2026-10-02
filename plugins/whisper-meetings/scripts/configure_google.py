#!/usr/bin/env python3
"""Import a private Google Desktop client outside the source tree. No credentials are printed."""
import argparse
import json
import os
from pathlib import Path
import sys


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('client_json',type=Path,help='Desktop client JSON downloaded from Google Cloud')
    args=parser.parse_args()
    try:
        source=json.loads(args.client_json.read_text())
        if 'web' in source:raise ValueError
        data=source.get('installed',source)
        if not data.get('client_id','').endswith('.apps.googleusercontent.com') or not data.get('client_secret'):raise ValueError
    except (OSError,ValueError,AttributeError):
        parser.error('Supply a valid Google Desktop OAuth client JSON with client_id and client_secret.')
    home=Path(os.environ.get('WHISPER_MEETINGS_HOME','~/.local/share/whisper-meetings')).expanduser().resolve()
    home.mkdir(parents=True,exist_ok=True,mode=0o700)
    destination=home/'google-client.json'
    destination.write_text(json.dumps({key:data[key] for key in ('client_id','client_secret')},indent=2)+'\n')
    destination.chmod(0o600)
    print('Google sign-in configured locally. Open the panel and choose Connect Google.')


if __name__=='__main__':main()
