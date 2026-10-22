"""python3 -m tshweb TOURNAMENT_FOLDER [options]

Starts tsh in this terminal and serves the score entry page on the local
network, or on the internet with --public.
"""

import argparse
import os
import secrets
import shlex
import socket
import sys
import threading

from . import tournament
from .desk import DEFAULT_TEMPLATE, ScoreDesk
from .driver import Tsh
from .tunnel import TunnelError, start_tunnel
from .web import make_server

# No 0/O or 1/I/L, so codes are easy to read out loud and type.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packets sent; picks the LAN interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main():
    parser = argparse.ArgumentParser(prog="python3 -m tshweb", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="tournament folder containing config.tsh")
    parser.add_argument("--tsh", default="tsh",
                        help="command that starts tsh, run inside the folder (default: tsh)")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--line", action="append", dest="template", metavar="TEXT",
                        help="a line to type into tsh per result; repeat for each line. "
                             "Placeholders: {round} {division} {p1} {s1} {p2} {s2}. "
                             "Default: " + " | ".join(DEFAULT_TEMPLATE))
    parser.add_argument("--public", action="store_true",
                        help="also put the page on the internet through a Cloudflare tunnel, "
                             "so players can use any Wi-Fi or mobile data (needs cloudflared)")
    parser.add_argument("--code", help="tournament code players need (default: a random one)")
    parser.add_argument("--cloudflared", default="cloudflared",
                        help="path to the cloudflared program (default: cloudflared)")
    args = parser.parse_args()

    folder = os.path.abspath(args.folder)
    try:
        divisions = tournament.load_divisions(folder)
        for path in divisions.values():
            tournament.read_players(path)
    except (OSError, ValueError) as e:
        sys.exit(f"Can't read tournament: {e}")

    code = (args.code or "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))).upper()
    tsh = Tsh(shlex.split(args.tsh), folder)
    server = make_server(ScoreDesk(folder, tsh, args.template), code, port=args.port)
    tunnel = None
    if args.public:
        print("Opening public address...")
        try:
            tunnel, public_url = start_tunnel(args.port, args.cloudflared)
        except TunnelError as e:
            sys.exit(f"Can't go public: {e}")

    print(f"Tournament code: {code}")
    if tunnel:
        print(f"Score entry (anywhere):    {public_url}/?code={code}")
    print(f"Score entry (venue Wi-Fi): http://{local_ip()}:{args.port}/?code={code}")
    print(f"Divisions: {', '.join(divisions)}")
    input("Press Enter to start tsh...")

    tsh.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    status = tsh.wait()
    server.shutdown()
    if tunnel:
        tunnel.terminate()
    sys.exit(status)


if __name__ == "__main__":
    main()
