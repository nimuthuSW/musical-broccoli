# musical-broccoli

Score entry for Scrabble tournaments run with [tsh](https://scrabbleplayers.org/w/TSH).
Players enter their game result on their phone, or on a laptop at the venue, and it is
typed straight into tsh running in the director's terminal.

## How it works

- The director starts tsh through this app instead of directly. tsh runs in the same
  terminal and works exactly as before.
- The app also serves a score entry page on the venue Wi-Fi. A player picks their name,
  sees their round and opponent, and enters both scores. Both players should be present.
- The result is typed into tsh as if the director had typed it. If the director is in the
  middle of typing, it waits until they finish the line and pause for a second.
- The app then checks tsh's `.t` file and tells the player whether the score was recorded.

The app only reads the tournament files; tsh is the only thing that writes them.

## Running it

Needs Python 3.8 or later on the director's laptop (macOS or Linux). Nothing to install.

```sh
python3 -m tshweb /path/to/tournament --tsh "perl /path/to/tsh.pl"
```

- `/path/to/tournament` is the folder with `config.tsh` and the division `.t` files.
- `--tsh` is the command you normally use to start tsh (run inside that folder).
- `--port` changes the web port (default 8080).

It prints the address for the score entry page (for example `http://192.168.1.20:8080/`).
Players' phones must be on the same Wi-Fi as the laptop. Press Enter to start tsh.

## Checking the tsh input

For each result the app types these lines into tsh:

```
addscore {round} {division}
{p1} {s1} {p2} {s2}
end
```

**Check this against your tsh version before a tournament.** If your tsh expects
something different, pass each line with `--line`, for example:

```sh
python3 -m tshweb ./tournament --tsh tsh \
  --line "addscore {round} {division}" --line "{p1} {s1} {p2} {s2}" --line "end"
```

If a player sees "Sent to the director, but not confirmed yet", the lines were typed but
the score didn't show up in the `.t` file within 10 seconds. Look at the tsh terminal to
see why.

## Tests

```sh
python3 -m unittest discover -s tests
```

The tests use a small stand-in for tsh (`tests/fake_tsh.py`).
