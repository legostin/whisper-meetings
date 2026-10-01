import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

from meetings import capture_binary, data_home, get, mark_recording, now, transcribe, update


def run(meeting_id, mode):
    os.umask(0o077)
    item = get(meeting_id)
    directory = Path(item["directory"])
    with (directory / "worker.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            if mode == "capture":
                with (directory / "capture.log").open("ab") as log:
                    process = subprocess.Popen([str(capture_binary()), str(directory)], stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                    announced = False
                    started = time.monotonic()
                    while process.poll() is None:
                        if not announced and (directory / "capture-ready").exists():
                            # Don't overwrite a stop requested while the permission dialog was open.
                            mark_recording(meeting_id)
                            announced = True
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


if __name__ == "__main__":
    run(sys.argv[1], sys.argv[2])
