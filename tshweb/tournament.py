"""Read-only access to a tsh tournament folder (config.tsh and division .t files).

tsh owns these files while it runs; this module only ever reads them.
"""

import os
import re
from dataclasses import dataclass, field

# "Lastname, Firstname   1500 3 7 2" -> name, rating, opponent numbers
_PLAYER_RE = re.compile(r"^(?P<name>.*?\S)\s+(?P<rating>-?\d+)(?P<opps>(?:\s+\d+)*)\s*$")


class MatchError(Exception):
    """A player can't enter a score right now (bye, no pairing, mismatch...)."""


@dataclass
class Player:
    number: int
    name: str
    rating: int
    opponents: list = field(default_factory=list)
    scores: list = field(default_factory=list)


def load_divisions(folder):
    """Map division name -> .t file path, from the folder's config.tsh."""
    config = os.path.join(folder, "config.tsh")
    if not os.path.exists(config):
        raise FileNotFoundError(f"No config.tsh in {folder}")
    divisions = {}
    with open(config, encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.split("#", 1)[0].split()
            if len(parts) >= 3 and parts[0].lower() == "division":
                divisions[parts[1].upper()] = os.path.join(folder, parts[2])
    if not divisions:
        raise ValueError(f"No 'division' lines in {config}")
    return divisions


def read_players(path):
    """Parse a .t file. Player numbers follow line order, starting at 1."""
    players = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            sections = line.split(";")
            m = _PLAYER_RE.match(sections[0])
            if not m:
                raise ValueError(f"Can't read player line in {path}: {line!r}")
            scores = sections[1].split() if len(sections) > 1 else []
            players.append(Player(
                number=len(players) + 1,
                name=m.group("name"),
                rating=int(m.group("rating")),
                opponents=[int(n) for n in m.group("opps").split()],
                scores=[int(s) for s in scores if re.fullmatch(r"-?\d+", s)],
            ))
    return players


def find(players, number):
    if 1 <= number <= len(players):
        return players[number - 1]
    raise MatchError(f"There is no player {number} in this division.")


def next_match(players, number):
    """Return (round, player, opponent) for the next score this player owes."""
    player = find(players, number)
    rnd = len(player.scores) + 1
    if rnd > len(player.opponents):
        raise MatchError(f"{player.name} has no pairing for round {rnd} yet.")
    opp_number = player.opponents[rnd - 1]
    if opp_number == 0:
        raise MatchError(f"{player.name} has a bye in round {rnd}. Nothing to enter.")
    opponent = find(players, opp_number)
    if len(opponent.scores) != len(player.scores):
        raise MatchError(
            f"Scores for {player.name} and {opponent.name} don't line up. "
            "Please see the director.")
    return rnd, player, opponent


def is_recorded(path, rnd, p1, s1, p2, s2):
    """True once the .t file holds this result for both players."""
    try:
        players = read_players(path)
        a, b = find(players, p1), find(players, p2)
    except (OSError, ValueError, MatchError):
        return False
    return (len(a.scores) >= rnd and a.scores[rnd - 1] == s1
            and len(b.scores) >= rnd and b.scores[rnd - 1] == s2)
