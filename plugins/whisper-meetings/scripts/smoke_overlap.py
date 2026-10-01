"""Optional Mac integration check: two synthetic voices, no microphone capture.

Run with the installed runtime Python after setup.py --diarization.
Uses local macOS Samantha/Daniel voices; removes all generated audio on exit.
This is one controlled fixture, not a benchmark of live-meeting accuracy.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import diarization


def main():
    diarization.require_available()
    phrases = [
        ('Samantha', 'We should prepare the new version for Friday. I will review the installation guide and check the release process. The customer needs a clear explanation of the next steps. Let us review the timeline together.'),
        ('Daniel', 'I suggest testing the microphone and the conference audio first. We need to understand which person is speaking. I can review the documentation on Monday and prepare a detailed report for the team.'),
    ]
    with tempfile.TemporaryDirectory(prefix='whisper-overlap-smoke-') as temporary:
        root = Path(temporary)
        audio = []
        for i, (voice, text) in enumerate(phrases):
            original, normalized = root / f'{i}.aiff', root / f'{i}.wav'
            subprocess.run(['say', '-v', voice, '-o', str(original), text], check=True)
            diarization.convert_track(str(original), normalized)
            with wave.open(str(normalized)) as stream:
                audio.append(np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(np.float32))
        a, b = audio
        gap = np.zeros(16000, dtype=np.float32)
        count = min(len(a), len(b))
        mixed = .6*a[:count] + .6*b[:count]
        fixture = np.concatenate([a, gap, b, gap, mixed, gap, a])
        path = root / 'fixture.wav'
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(np.clip(fixture, -32768, 32767).astype('<i2').tobytes())
        turns = diarization.infer({'imported': str(path)})['imported']
        overlaps = diarization.overlap_intervals(turns)
        start = (len(a)+len(b)+32000)/16000
        end = start + count/16000
        speakers = sorted({turn['speaker_id'] for turn in turns})
        covered = sum(max(0, min(end, hi)-max(start, lo)) for lo, hi in overlaps)
        print(json.dumps({'expected_overlap': [start, end], 'detected_overlap': overlaps,
                          'speakers': speakers, 'turns': turns}, indent=2), flush=True)
        assert len(speakers) == 2, 'Controlled fixture did not resolve two voices'
        assert covered >= .8*(end-start), 'Controlled overlap was not sufficiently detected'
        annotated, _, _ = diarization.annotate([
            {'source': 'imported', 'start': start, 'end': end, 'text': 'Supplied test text'}
        ], {'imported': turns})
        assert annotated[0]['speaker_id'] is None and annotated[0]['overlapping_speech']
        print('PASS: two native voices and overlap; ambiguous text has no single owner')


if __name__ == '__main__':
    main()
