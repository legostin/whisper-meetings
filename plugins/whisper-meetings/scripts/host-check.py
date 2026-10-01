"""Read the plugin inventory through Codex without creating a chat or agent turn."""
import json
from pathlib import Path
import selectors
import subprocess
import tempfile
import time

root = Path(__file__).resolve().parents[3]
with tempfile.TemporaryFile(mode="w+") as log:
    process = subprocess.Popen(["codex", "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=log, text=True, bufsize=1)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)

    def send(value):
        process.stdin.write(json.dumps(value) + "\n")
        process.stdin.flush()

    def receive(identity):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if selector.select(1):
                line = process.stdout.readline()
                if not line:
                    break
                value = json.loads(line)
                if value.get("id") == identity:
                    if "error" in value:
                        raise RuntimeError(value["error"])
                    return value["result"]
        raise TimeoutError("Codex plugin inventory timed out")

    try:
        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "whisper-plugin-check", "version": "0.1.0"}, "capabilities": {"experimentalApi": True}}})
        receive(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "plugin/read", "params": {"pluginName": "whisper-meetings", "marketplacePath": str(root / ".agents/plugins/marketplace.json")}})
        detail = receive(2)["plugin"]
        assert "whisper_meetings" in detail["mcpServers"], detail["mcpServers"]
        assert detail["skills"][0]["enabled"]
        print(json.dumps({"mcpServers": detail["mcpServers"], "skills": [s["name"] for s in detail["skills"]]}, indent=2))
    finally:
        process.terminate()
        process.wait(timeout=10)
