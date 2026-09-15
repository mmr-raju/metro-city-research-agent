"""Launch the real Streamlit CLI and verify localhost health, then stop our process."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx


def test_headless_streamlit_server():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.headless=true",
         f"--server.port={port}", "--server.address=127.0.0.1", "--browser.gatherUsageStats=false"],
        cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        deadline = time.monotonic() + 25
        with httpx.Client(trust_env=False, timeout=1) as client:
            while time.monotonic() < deadline:
                assert process.poll() is None, "Streamlit exited before becoming healthy"
                try:
                    response = client.get(f"http://127.0.0.1:{port}/_stcore/health")
                    if response.status_code == 200:
                        assert response.text == "ok"
                        return
                except httpx.RequestError:
                    pass
                time.sleep(0.2)
        raise AssertionError("Streamlit did not become healthy within 25 seconds")
    finally:
        process.terminate()
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate(timeout=5)
