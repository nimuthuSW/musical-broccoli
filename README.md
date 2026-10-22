# musical-broccoli

Score entry for Scrabble tournaments run with [tsh](https://scrabbleplayers.org/w/TSH).
Players enter their game result on their phone, or on a laptop at the venue, and it is
typed straight into tsh running in the director's terminal.

## How it works

- The director starts tsh through this app instead of directly. tsh runs in the same
  terminal and works exactly as before.
- The app also serves a score entry page. With `--public` it's on the internet, so players
  can use any Wi-Fi or mobile data; without it, only devices on the laptop's Wi-Fi can reach
  it. A player picks their name, sees their round and opponent, and enters both scores.
  Both players should be present.
- Players need a tournament code. It's included in the link the app prints, so a player who
  opens that link (or scans it as a QR code) never has to type it.
- The result is typed into tsh as if the director had typed it. If the director is in the
  middle of typing, it waits until they finish the line and pause for a second.
- The app then checks tsh's `.t` file and tells the player whether the score was recorded.

The app only reads the tournament files; tsh is the only thing that writes them.

## Running it

Needs Python 3.8 or later on the director's laptop (macOS or Linux). Nothing to install.

```sh
python3 -m tshweb /path/to/tournament --tsh "perl /path/to/tsh.pl" --public
```

- `/path/to/tournament` is the folder with `config.tsh` and the division `.t` files.
- `--tsh` is the command you normally use to start tsh (run inside that folder).
- `--public` puts the page on the internet (see below). Leave it off to use the venue Wi-Fi only.
- `--code` sets the tournament code. By default a random 6-character code is made each run.
- `--port` changes the web port (default 8080).

It prints the tournament code and the links, for example:

```
Tournament code: ROOK42
Score entry (anywhere):    https://brave-otter-lake.trycloudflare.com/?code=ROOK42
Score entry (venue Wi-Fi): http://192.168.1.20:8080/?code=ROOK42
```

Share the link with players (on a slide, as a QR code, or in a group chat). Press Enter to
start tsh. When you quit tsh, the page and the public address stop too.

### Going public

`--public` uses a free [Cloudflare quick tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/):
no account, and nothing to set up on the venue's router. The laptop only needs internet access.

1. Install `cloudflared` on the director's laptop once
   ([downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/);
   on macOS: `brew install cloudflared`).
2. Start the app with `--public`.

The public address changes every time the app starts, so hand out the new link each event.
Anyone with the link and code can enter a score for any player, so don't post the link
anywhere public. If the laptop loses internet, phones on the venue Wi-Fi can still use the
Wi-Fi link.

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
