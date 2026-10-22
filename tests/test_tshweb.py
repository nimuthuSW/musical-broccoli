import json
import os
import shutil
import stat
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from tshweb import tournament
from tshweb.desk import ScoreDesk
from tshweb.driver import Tsh
from tshweb.tournament import MatchError
from tshweb.tunnel import TunnelError, start_tunnel
from tshweb.web import make_server

FAKE_TSH = os.path.join(os.path.dirname(__file__), "fake_tsh.py")

CONFIG = "# test tournament\ndivision a a.t\n"
A_T = """\
Adams, Ann        1800 2 3 4; 410 380
Brown, Bob        1700 1 4 3; 350 402
Clark, Cal        1600 4 1 2; 390 415
Davis, Dee        1500 3 2 1; 401 360
"""


class TournamentFolder(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        with open(os.path.join(self.folder, "config.tsh"), "w") as f:
            f.write(CONFIG)
        self.t_file = os.path.join(self.folder, "a.t")
        with open(self.t_file, "w") as f:
            f.write(A_T)

    def tearDown(self):
        shutil.rmtree(self.folder)


class TournamentTest(TournamentFolder):
    def test_reads_divisions_and_players(self):
        self.assertEqual(tournament.load_divisions(self.folder), {"A": self.t_file})
        players = tournament.read_players(self.t_file)
        self.assertEqual([p.name for p in players],
                         ["Adams, Ann", "Brown, Bob", "Clark, Cal", "Davis, Dee"])
        self.assertEqual(players[0].opponents, [2, 3, 4])
        self.assertEqual(players[0].scores, [410, 380])
        self.assertEqual(players[0].rating, 1800)

    def test_next_match_is_first_round_without_a_score(self):
        rnd, player, opponent = tournament.next_match(tournament.read_players(self.t_file), 1)
        self.assertEqual((rnd, player.number, opponent.number), (3, 1, 4))

    def test_no_pairing_yet(self):
        with open(self.t_file, "w") as f:
            f.write("Adams, Ann 1800 2; 400\nBrown, Bob 1700 1; 350\n")
        with self.assertRaisesRegex(MatchError, "no pairing for round 2"):
            tournament.next_match(tournament.read_players(self.t_file), 1)

    def test_bye(self):
        with open(self.t_file, "w") as f:
            f.write("Adams, Ann 1800 0\n")
        with self.assertRaisesRegex(MatchError, "bye"):
            tournament.next_match(tournament.read_players(self.t_file), 1)


class EndToEndTest(TournamentFolder):
    """Real pseudo-terminal, fake tsh, real HTTP server."""

    def setUp(self):
        super().setUp()
        self.tsh = Tsh([sys.executable, FAKE_TSH], self.folder, interactive=False,
                       idle_seconds=0, line_delay=0.05)
        self.tsh.start()
        self.desk = ScoreDesk(self.folder, self.tsh, confirm_timeout=5)
        self.server = make_server(self.desk, "ABC234", host="127.0.0.1", port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tsh.submit(["quit"])
        self.tsh.wait()
        super().tearDown()

    def request(self, path, body=None, code="abc234"):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, headers={
            "Content-Type": "application/json", "X-Access-Code": code})
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.load(res)
        except urllib.error.HTTPError as e:
            return e.code, json.load(e)

    def test_score_reaches_tsh_and_round_advances(self):
        status, match = self.request("/api/match?division=a&player=4")
        self.assertEqual(status, 200)
        self.assertEqual((match["round"], match["opponent"]["name"]), (3, "Adams, Ann"))

        status, result = self.request("/api/score", {
            "division": "A", "player": 4, "round": 3,
            "player_score": 433, "opponent_score": 377})
        self.assertEqual((status, result["status"]), (200, "recorded"))

        players = tournament.read_players(self.t_file)
        self.assertEqual(players[3].scores, [401, 360, 433])
        self.assertEqual(players[0].scores, [410, 380, 377])

        # Same game again, from the other player: already recorded.
        status, result = self.request("/api/score", {
            "division": "A", "player": 1, "round": 3,
            "player_score": 377, "opponent_score": 433})
        self.assertEqual(status, 409)
        self.assertIn("no pairing for round 4", result["error"])

    def test_rejects_stale_round_and_bad_score(self):
        status, result = self.request("/api/score", {
            "division": "A", "player": 1, "round": 2,
            "player_score": 400, "opponent_score": 300})
        self.assertEqual(status, 409)
        self.assertIn("already recorded", result["error"])

        status, result = self.request("/api/score", {
            "division": "A", "player": 1, "round": 3,
            "player_score": 99999, "opponent_score": 300})
        self.assertEqual(status, 409)

    def test_wrong_code_is_refused(self):
        status, result = self.request("/api/divisions", code="WRONG1")
        self.assertEqual(status, 401)
        status, result = self.request("/api/score", {
            "division": "A", "player": 4, "round": 3,
            "player_score": 433, "opponent_score": 377}, code="")
        self.assertEqual(status, 401)
        self.assertEqual(len(tournament.read_players(self.t_file)[3].scores), 2)

    def test_page_and_divisions(self):
        with urllib.request.urlopen(self.base + "/") as res:
            self.assertIn(b"Score entry", res.read())
        status, divisions = self.request("/api/divisions")
        self.assertEqual(divisions[0]["name"], "A")
        self.assertEqual(len(divisions[0]["players"]), 4)


class TunnelTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def fake_cloudflared(self, output):
        path = os.path.join(self.dir, "cloudflared")
        with open(path, "w") as f:
            f.write(f"#!/bin/sh\nprintf '{output}'\nsleep 30\n")
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
        return path

    def test_reads_public_address(self):
        binary = self.fake_cloudflared(
            "INF Requesting new quick Tunnel\\n"
            "INF |  https://brave-otter-lake.trycloudflare.com  |\\n")
        proc, url = start_tunnel(8080, binary, timeout=5)
        proc.terminate()
        proc.wait()
        self.assertEqual(url, "https://brave-otter-lake.trycloudflare.com")

    def test_missing_program(self):
        with self.assertRaisesRegex(TunnelError, "isn't installed"):
            start_tunnel(8080, os.path.join(self.dir, "nope"))

    def test_no_address(self):
        binary = self.fake_cloudflared("ERR failed to connect\\n")
        with self.assertRaisesRegex(TunnelError, "didn't report"):
            start_tunnel(8080, binary, timeout=1)


if __name__ == "__main__":
    unittest.main()
