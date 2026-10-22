"""Public internet address via a Cloudflare quick tunnel (no account needed).

Runs `cloudflared tunnel --url http://localhost:PORT` and reads the
https://….trycloudflare.com address it prints.
"""

import re
import subprocess
import threading

_URL_RE = re.compile(r"https://[-a-z0-9]+\.trycloudflare\.com")


class TunnelError(Exception):
    pass


def start_tunnel(port, binary="cloudflared", timeout=30):
    """Start the tunnel; return (process, public_url)."""
    try:
        proc = subprocess.Popen(
            [binary, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, errors="replace")
    except FileNotFoundError:
        raise TunnelError(
            f"'{binary}' isn't installed. Get it from "
            "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/")

    found = threading.Event()
    result = {}

    # cloudflared logs to its output for as long as it runs. Keep reading it so
    # it never blocks, and don't show it: the terminal belongs to tsh.
    def read():
        for line in proc.stdout:
            m = _URL_RE.search(line)
            if m and not found.is_set():
                result["url"] = m.group(0)
                found.set()
        found.set()

    threading.Thread(target=read, daemon=True).start()
    found.wait(timeout)
    if "url" not in result:
        proc.terminate()
        raise TunnelError("cloudflared didn't report a public address. "
                          "Check the laptop's internet connection.")
    return proc, result["url"]
