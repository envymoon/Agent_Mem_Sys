"""Keep a CLI-created Colab runtime assigned while a long job runs in its kernel.

The Colab CLI runs no keep-alive. The web UI pings the runtime's keep-alive endpoint every few minutes; without a
browser, a runtime whose `colab exec` client has disconnected was reclaimed ~20 min later even though its kernel was
still executing (first L4 pilot, 2026-11-26). This sends the same ping, plus a cheap list call, every INTERVAL s.

Run with the CLI's own interpreter (it reuses the CLI's stored OAuth token):
    ~/.local/share/uv/tools/google-colab-cli/bin/python colab/keepalive.py SESSION [INTERVAL]
    ~/.local/share/uv/tools/google-colab-cli/bin/python colab/keepalive.py --endpoint ENDPOINT [INTERVAL]
The first form reads the endpoint from the CLI's local session state. The second is for running on the Colab VM
itself (cli_bootstrap.py starts it there): Claude's container is paused between turns, which kills any keep-alive
running there, so the VM pings for itself with a Colab-scoped token uploaded by Claude.
Exits when the assignment is gone. Logs one line per ping.
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
    args = sys.argv[1:]
    if args[0] == "--endpoint":
        endpoint = args[1]
        args = args[2:]
    else:
        s = StateStore(None).get(args[0])
        if s is None:
            sys.exit(f"no local session {args[0]}")
        endpoint = s.endpoint
        args = args[1:]
    interval = float(args[0]) if args else 240
    client = Client(Prod(), get_credentials(None))
    url = urljoin(client.colab_domain, f"{TUN_ENDPOINT}/{endpoint}/keep-alive/")
    while True:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        try:
            live = {a.endpoint for a in client.list_assignments()}
        except Exception as e:  # transient API error: keep trying
            print(f"{ts} list failed: {e!r}"[:200], flush=True)
            time.sleep(60)
            continue
        if endpoint not in live:
            print(f"{ts} assignment {endpoint} gone; exiting", flush=True)
            return
        try:
            client._issue_request(url, headers={"X-Colab-Tunnel": "Google"})
            print(f"{ts} keep-alive ok", flush=True)
        except Exception as e:
            print(f"{ts} keep-alive failed: {e!r}"[:300], flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
