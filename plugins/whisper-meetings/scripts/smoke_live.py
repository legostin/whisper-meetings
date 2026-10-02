"""Real offline provisional ASR worker smoke; synthetic file only, no devices."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN))
import meetings


def main():
    fixture = Path(sys.argv[1]).resolve(strict=True)
    installed_home = meetings.data_home()
    with tempfile.TemporaryDirectory(prefix='whisper-live-smoke-') as temporary:
        os.environ['WHISPER_MEETINGS_HOME'] = temporary
        os.environ['HF_HUB_OFFLINE'] = '1'
        root = Path(temporary)
        (root / 'models').symlink_to(installed_home / 'models', target_is_directory=True)
        original_spawn = meetings.spawn
        meetings.spawn = lambda *_: None
        item = meetings.create('Synthetic live speech', 'capture', 'small', 'ru', False, live_transcription=True)
        meetings.spawn = original_spawn
        meetings.update(item['id'], state='recording')
        chunks = Path(item['directory']) / 'live-chunks'
        chunks.mkdir()
        from faster_whisper.audio import decode_audio
        import numpy as np
        import wave
        samples = decode_audio(str(fixture), sampling_rate=16000)
        with wave.open(str(chunks / 'microphone-000000.wav'), 'wb') as out:
            out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000)
            out.writeframes((samples * 32767).astype(np.int16).tobytes())
        duration = len(samples) / 16000
        meetings.atomic_json(chunks / 'microphone-000000.json', {'source': 'microphone', 'start': 0, 'end': duration})
        process = subprocess.Popen([sys.executable, str(PLUGIN / 'worker.py'), item['id'], 'live'])
        try:
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                status = meetings.get(item['id'])
                if status.get('live_error'):
                    raise RuntimeError(status['live_error'])
                if status.get('live_segment_count'):
                    break
                if process.poll() is not None:
                    raise RuntimeError('Live worker exited without text')
                time.sleep(0.3)
            else:
                raise TimeoutError('Provisional transcription timed out')
            draft = meetings.read_live_transcript(item['id'])
            assert draft['provisional'] and 'sha256' not in draft
            assert draft['languages']['microphone']['language'] == 'ru'
            text = ' '.join(s['text'] for s in draft['segments'])
            assert 'пятниц' in text.lower() and 'понедельник' in text.lower(), text
            # Read on another connection while capture remains active.
            assert meetings.get(item['id'])['state'] == 'recording'
            assert not (Path(item['directory']) / 'transcript.json').exists()
            meetings.update(item['id'], state='stopping')
            process.wait(timeout=10)
            assert meetings.read_live_transcript(item['id'])['segments'] == draft['segments']
            print('PASS: actual offline Russian live worker, durable provisional text during active recording, clean stop; no microphone opened')
            print(text)
        finally:
            if process.poll() is None:
                process.terminate(); process.wait(timeout=10)


if __name__ == '__main__':
    main()
