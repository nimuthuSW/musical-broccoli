"""A tiny stand-in for tsh, used by the tests.

Understands only the default score-entry lines: "addscore ROUND DIV", then
"P1 S1 P2 S2" lines, then "end". Writes scores to the division's .t file.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tshweb import tournament  # noqa: E402


def write_score(path, rnd, number, score):
    with open(path) as f:
        lines = [l.rstrip("\n") for l in f if l.strip()]
    head, _, rest = lines[number - 1].partition(";")
    scores = rest.split()
    if len(scores) != rnd - 1:
        raise ValueError(f"player {number} has {len(scores)} scores, not {rnd - 1}")
    lines[number - 1] = f"{head.rstrip()}; {' '.join(scores + [str(score)])}"
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    divisions = tournament.load_divisions(os.getcwd())
    mode = None
    while True:
        try:
            line = input("[%s] " % (f"{mode[1]} R{mode[0]}" if mode else "tsh")).split()
        except EOFError:
            return
        if not line:
            continue
        if line[0] == "quit":
            return
        if mode is None:
            if line[0] == "addscore":
                mode = (int(line[1]), line[2].upper())
            else:
                print("Unknown command")
        elif line[0] == "end":
            mode = None
        else:
            p1, s1, p2, s2 = map(int, line)
            path = divisions[mode[1]]
            write_score(path, mode[0], p1, s1)
            write_score(path, mode[0], p2, s2)
            print(f"Recorded {p1} {s1} {p2} {s2}")


if __name__ == "__main__":
    main()
