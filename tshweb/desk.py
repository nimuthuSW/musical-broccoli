"""Turns a submitted result into tsh input and checks that tsh recorded it."""

import threading
import time

from . import tournament
from .tournament import MatchError

# What gets typed into tsh for one result. Check this against your tsh version
# and override it with --line if it differs.
DEFAULT_TEMPLATE = [
    "addscore {round} {division}",
    "{p1} {s1} {p2} {s2}",
    "end",
]

MIN_SCORE, MAX_SCORE = -500, 2000

# After an unconfirmed submission, refuse a resubmission of the same game for
# this long, in case tsh is just slow (e.g. the director is busy typing).
RESUBMIT_BLOCK_SECONDS = 60


class ScoreDesk:
    def __init__(self, folder, tsh, template=None, confirm_timeout=10.0):
        self.folder = folder
        self.tsh = tsh
        self.template = template or DEFAULT_TEMPLATE
        self.confirm_timeout = confirm_timeout
        self._pending = {}  # game -> time until which resubmission is refused
        self._lock = threading.Lock()

    def _division(self, name):
        divisions = tournament.load_divisions(self.folder)
        key = str(name).upper()
        if key not in divisions:
            raise MatchError(f"There is no division {name}.")
        return key, divisions[key]

    def divisions(self):
        result = []
        for name, path in tournament.load_divisions(self.folder).items():
            players = tournament.read_players(path)
            result.append({
                "name": name,
                "players": [{"number": p.number, "name": p.name} for p in players],
            })
        return result

    def match(self, division, number):
        division, path = self._division(division)
        rnd, player, opponent = tournament.next_match(tournament.read_players(path), int(number))
        return {
            "division": division,
            "round": rnd,
            "player": {"number": player.number, "name": player.name},
            "opponent": {"number": opponent.number, "name": opponent.name},
        }

    def record(self, division, number, rnd, player_score, opponent_score):
        division, path = self._division(division)
        s1, s2 = int(player_score), int(opponent_score)
        for s in (s1, s2):
            if not MIN_SCORE <= s <= MAX_SCORE:
                raise MatchError(f"{s} doesn't look like a valid score.")
        current, player, opponent = tournament.next_match(
            tournament.read_players(path), int(number))
        if int(rnd) != current:
            raise MatchError(
                f"Round {rnd} is already recorded for {player.name}. "
                "Please see the director if it's wrong.")
        key = (division, current, frozenset((player.number, opponent.number)))
        with self._lock:
            if self._pending.get(key, 0) > time.monotonic():
                raise MatchError(
                    "This game has already been submitted and is being recorded. "
                    "Please see the director if it doesn't show up.")
            self._pending[key] = float("inf")
        recorded = False
        try:
            values = {"division": division, "round": current,
                      "p1": player.number, "s1": s1, "p2": opponent.number, "s2": s2}
            self.tsh.submit([line.format(**values) for line in self.template])
            recorded = self._wait_for_tsh(path, current, player.number, s1, opponent.number, s2)
        finally:
            with self._lock:
                if recorded:
                    del self._pending[key]
                else:
                    self._pending[key] = time.monotonic() + RESUBMIT_BLOCK_SECONDS
        return {"status": "recorded" if recorded else "sent", "round": current,
                "player": player.name, "opponent": opponent.name}

    def _wait_for_tsh(self, path, rnd, p1, s1, p2, s2):
        deadline = time.monotonic() + self.confirm_timeout
        while time.monotonic() < deadline:
            if tournament.is_recorded(path, rnd, p1, s1, p2, s2):
                return True
            time.sleep(0.3)
        return False
