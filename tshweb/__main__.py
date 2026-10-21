"""python3 -m tshweb TOURNAMENT_FOLDER [options]

Starts tsh in this terminal and serves the score entry page on the local network.
"""

import argparse
import os
import shlex
import socket
import sys
import threading

from . import tournament
from .desk import DEFAULT_TEMPLATE, ScoreDesk
from .driver import Tsh
from .web import make_server


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
    args = parser.parse_args()

    folder = os.path.abspath(args.folder)
    try:
        divisions = tournament.load_divisions(folder)
        for path in divisions.values():
            tournament.read_players(path)
    except (OSError, ValueError) as e:
        sys.exit(f"Can't read tournament: {e}")

    tsh = Tsh(shlex.split(args.tsh), folder)
    server = make_server(ScoreDesk(folder, tsh, args.template), port=args.port)
    print(f"Score entry page: http://{local_ip()}:{args.port}/")
    print(f"Divisions: {', '.join(divisions)}")
    input("Press Enter to start tsh...")

    tsh.start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    code = tsh.wait()
    server.shutdown()
    sys.exit(code)


if __name__ == "__main__":
    main()
