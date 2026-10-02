import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

from meetings import ROOT, data_home, fail_live, get, mark_recording, meeting_capture_binary, now, sync_capture_state, transcribe, update


def run(meeting_id, mode):
    os.umask(0o077)
    if mode == 'live':
        import live
        live.run(meeting_id)
        return
    item = get(meeting_id)
    directory = Path(item["directory"])
    with (directory / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        live_process = None
        try:
            if mode == "capture":
                with (directory / "capture.log").open("ab") as log:
                    command = [str(meeting_capture_binary(item)), str(directory)]
                    # Legacy recordings retain the sources selected by the old version.
                    if item.get('capture_sources', ['microphone', 'system']) == ['microphone']:
                        command.append('--microphone-only')
                    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                    def start_live_worker():
                        try:
                            with (directory / 'live.log').open('ab') as live_log:
                                return subprocess.Popen([sys.executable, str(ROOT / 'worker.py'), meeting_id, 'live'],
                                                        stdin=subprocess.DEVNULL, stdout=live_log, stderr=live_log)
                        except Exception as exc:
                            fail_live(meeting_id, exc)
                            return None
                    announced = False
                    started = time.monotonic()
                    while process.poll() is None:
                        if not announced and (directory / "capture-ready").exists():
                            # Don't overwrite a stop requested while the permission dialog was open.
                            mark_recording(meeting_id)
                            announced = True
                            live_process = start_live_worker()
                        if announced:
                            sync_capture_state(meeting_id)
                            current = get(meeting_id)
                            if live_process and live_process.poll() is not None and current['state'] in {'recording','pausing','paused','resuming'}:
                                if current.get('live_status') != 'failed':
                                    fail_live(meeting_id, 'Live worker exited. Capture continues; enable live transcription to retry.')
                                live_process = None
                            elif live_process is None and current.get('live_transcription') and current.get('live_status') == 'waiting':
                                live_process = start_live_worker()

                        if not announced and (directory / "stop-requested").exists():
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill(); process.wait()
                            update(meeting_id, state="cancelled", stopped_at=now())
                            return
                        if not announced and time.monotonic() - started > 120:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill(); process.wait()
                            raise RuntimeError("Capture startup timed out. Check macOS microphone and system audio permissions, then retry.")
                        time.sleep(0.2)
                if live_process:
                    if live_process.poll() is None:
                        live_process.terminate()
                        try:
                            live_process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            live_process.kill(); live_process.wait()
                    live_process = None
                sync_capture_state(meeting_id)
                current = get(meeting_id)
                if current.get('live_status') != 'failed':
                    update(meeting_id, live_status='stopped')
                tracks = {p.stem: str(p) for p in directory.glob("*.wav")}
                update(meeting_id, tracks=tracks, stopped_at=now())
                if process.returncode:
                    raise RuntimeError((directory / "capture.log").read_text(errors="replace")[-3000:])
                item = get(meeting_id)
                if not item["transcribe_on_stop"]:
                    update(meeting_id, state="recorded")
                    return
            item = get(meeting_id)
            update(meeting_id, state="queued")
            # One model process at a time avoids multiplying model RAM and CPU
            # when several files are imported from different Codex chats.
            with (data_home() / "transcription.lock").open("a") as model_lock:
                fcntl.flock(model_lock, fcntl.LOCK_EX)
                if mode == 'diarize':
                    import json
                    import diarization
                    update(meeting_id, state='diarizing')
                    transcript = json.loads((directory / 'transcript.json').read_text())
                    diarization.process(item, transcript)
                    update(meeting_id, state='ready')
                else:
                    update(meeting_id, state="transcribing")
                    transcribe(item)
        except Exception as error:
            if mode == 'diarize':
                update(meeting_id, state='ready', diarization_status='failed', diarization_error=str(error))
            else:
                update(meeting_id, state="failed", error=str(error))
        finally:
            if live_process and live_process.poll() is None:
                live_process.terminate()
                try:
                    live_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    live_process.kill(); live_process.wait()


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
