"""Minimal client for the RPFM 5 server (JSON over WebSocket).

Starts rpfm_server.exe if nothing is listening. The server exits once its
last session disconnects, so keep one Rpfm instance open for a whole run.
"""
import itertools
import json
import os
import subprocess
import sys
import time

try:
    import websocket
except ImportError:
    sys.exit("The websocket-client package is missing. Run:  python -m pip install -r requirements.txt")

DEFAULT_URL = "ws://127.0.0.1:45127/ws"


class RpfmError(RuntimeError):
    pass


class Rpfm:
    def __init__(self, exe, url=DEFAULT_URL, timeout=1800):
        """`exe` is rpfm_server.exe, started if no server is running yet."""
        self.ws = None
        started = False
        for _ in range(120):
            try:
                self.ws = websocket.create_connection(url, timeout=timeout)
                break
            except ConnectionRefusedError:
                if not started:
                    subprocess.Popen([exe], cwd=os.path.dirname(exe),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    started = True
                time.sleep(0.5)
        if self.ws is None:
            raise RpfmError(f"could not connect to {url}")
        self._ids = itertools.count(1)

    def call(self, data):
        i = next(self._ids)
        self.ws.send(json.dumps({"id": i, "data": data}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == i:
                out = msg["data"]
                if isinstance(out, dict) and "Error" in out:
                    raise RpfmError(f"{_name(data)}: {out['Error']}")
                return out

    def close(self):
        if self.ws is None:
            return
        try:
            self.ws.send(json.dumps({"id": 0, "data": "ClientDisconnecting"}))
        finally:
            self.ws.close()
            self.ws = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _name(data):
    return data if isinstance(data, str) else next(iter(data))


def cell(value):
    """Unwrap a tagged DecodedData cell ({"I64": 5} -> 5)."""
    return next(iter(value.values())) if isinstance(value, dict) else value
