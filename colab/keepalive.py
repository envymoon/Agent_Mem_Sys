"""Keep a CLI-created Colab runtime assigned while a long job runs in its kernel.

The Colab CLI runs no keep-alive. The web UI pings the runtime's keep-alive endpoint every few minutes; without a
browser, a runtime whose `colab exec` client has disconnected was reclaimed ~20 min later even though its kernel was
still executing (first L4 pilot, 2026-11-26). This sends the same ping, plus a cheap list call, every INTERVAL s.

Run with the CLI's own interpreter (it reuses the CLI's stored OAuth token and session state):
    ~/.local/share/uv/tools/google-colab-cli/bin/python colab/keepalive.py SESSION [INTERVAL]
Exits when the session's assignment is gone. Logs one line per ping.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

from colab_cli.auth import get_credentials
from colab_cli.client import TUN_ENDPOINT, Client, Prod
from colab_cli.state import StateStore


def main() -> None:
    name = sys.argv[1]
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 240
    s = StateStore(None).get(name)
    if s is None:
        sys.exit(f"no local session {name}")
    client = Client(Prod(), get_credentials(None))
    url = urljoin(client.colab_domain, f"{TUN_ENDPOINT}/{s.endpoint}/keep-alive/")
    while True:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        try:
            live = {a.endpoint for a in client.list_assignments()}
        except Exception as e:  # transient API error: keep trying
            print(f"{ts} list failed: {e!r}"[:200], flush=True)
            time.sleep(60)
            continue
        if s.endpoint not in live:
            print(f"{ts} assignment {s.endpoint} gone; exiting", flush=True)
            return
        try:
            client._issue_request(url, headers={"X-Colab-Tunnel": "Google"})
            print(f"{ts} keep-alive ok", flush=True)
        except Exception as e:
            print(f"{ts} keep-alive failed: {e!r}"[:300], flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
