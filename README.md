# LAN-Based Classroom Live Polling System

A teacher runs a Python server on their laptop. Students on the same
Wi-Fi/LAN connect from their own laptops, receive live polls the teacher
creates, and vote. The teacher's dashboard shows results updating live.

```
                         CLASSROOM LAN
                              |
                    +-------------------+
                    |   PYTHON SERVER   |
                    | Socket Server     |
                    | Client Handler    |
                    | Poll Manager      |
                    | Vote Processing   |
                    +---------+---------+
                              |
             +----------------+----------------+
             |                |                |
             v                v                v
        Student 1        Student 2        Student 3
          Client           Client           Client

                              ^
                              |
                        Teacher Dashboard
```

## Architecture

```
common/protocol.py   Shared message-type constants, host/port defaults,
                      and the message-framing delimiter. Single source of
                      truth for the wire protocol.

server/server.py     TCP server. Accepts connections, frames newline-
                      delimited JSON, routes messages to PollManager.
                      One thread per connected client.
server/poll_manager.py  Poll/vote business logic + JSON persistence.
server/results.py       Builds the RESULTS message from poll data.
server/teacher_gui.py   Tkinter dashboard: create poll, close poll, live
                         results (polls the server every 2s).

client/client.py     Student app entry point.
client/gui.py         Tkinter UI: connect screen -> active poll -> result.
client/network.py     TCP client: connect/get_poll/submit_vote, same
                       newline-delimited JSON framing as the server.

data/polls.json      Poll data persisted by the server (created at
                      runtime; not committed to git).
tests/test_server_integration.py  End-to-end tests using the real
                       server + real client/teacher network code.
test_backend.py       Standalone script exercising PollManager directly.
```

## Requirements

Python 3.9+ with `tkinter` (bundled with most Python installs; on Linux
you may need `sudo apt install python3-tk`). No third-party packages are
required — see `requirements.txt`.

## Running It

All commands are run from the project root.

**1. Start the server** (on the teacher's laptop):

```
python -m server.server
```

This prints the machine's LAN IP address and the port it's listening on
— that IP is what students will type in. Press `CTRL+C` to stop it.

Optional flags: `python -m server.server --host 0.0.0.0 --port 5000`

**2. Start the teacher dashboard** (same laptop, separate terminal):

```
python -m server.teacher_gui
```

It connects to the server on `127.0.0.1:5000` (they're on the same
machine), so start the server first.

**3. Start a student client** (on each student's laptop):

```
python -m client.client
```

Enter your name, the teacher's LAN IP (shown in the server's banner —
see "Finding your IP" below), and the port (`5000` by default), then
click **Connect**.

## Finding the teacher's LAN IP (Windows)

The server prints its own IP on startup, but if you need to find it
manually:

```
ipconfig
```

Look for **IPv4 Address** under the active Wi-Fi/Ethernet adapter, e.g.
`192.168.1.10`. Students enter that IP and port `5000`.

## Windows Firewall

The first time you run the server, Windows may prompt to allow Python
through the firewall for private networks — accept it, or students on
the LAN won't be able to reach the server. If no prompt appears and
students can't connect, check Windows Defender Firewall settings for a
blocked rule on the port you're using.

## Network Protocol

JSON messages, one per line (newline-delimited — see
`common/protocol.py`). Student and teacher connections speak the same
framing; teacher connections are short-lived (one request per
connection) while a student connection stays open for the whole
session.

| Direction | type | Fields |
|---|---|---|
| Student -> Server | `CONNECT` | `student_name` |
| Server -> Student | `CONNECT_SUCCESS` | `student_id`, `message` |
| Student -> Server | `GET_POLL` | — |
| Server -> Student | `POLL` | `question`, `options` |
| Server -> Student | `NO_POLL` | — |
| Student -> Server | `VOTE` | `student_id`, `option` |
| Server -> Student | `VOTE_SUCCESS` | `message` |
| Teacher -> Server | `CREATE_POLL` | `question`, `options` (>= 2) |
| Server -> Teacher | `POLL_CREATED` | `poll_id`, `message` |
| Teacher -> Server | `CLOSE_POLL` | — |
| Server -> Teacher | `POLL_CLOSED` | `message` |
| Teacher -> Server | `GET_RESULTS` | — |
| Server -> Teacher | `RESULTS` | `results` (dict), `total_votes` |
| Server -> either | `ERROR` | `code`, `message` |

Creating a poll immediately makes it live (the dashboard has no separate
"start" step); only one poll can be active at a time.

## Testing

```
python -m compileall .
python test_backend.py                              # PollManager, standalone
python -m unittest tests.test_server_integration -v  # real server + real client/teacher code
```

## Troubleshooting

- **"Connection refused" / "Connection timed out" on the student side** —
  double-check the IP and port, and that the server is running and on
  the same network. Confirm with `ipconfig` on the teacher's machine.
- **"Port is already in use"** — another server (or a previous run) is
  still bound to that port; stop it, or start this one with `--port`
  pointing at a free one.
- **Teacher dashboard can't reach the server** — start the server
  (`python -m server.server`) before the dashboard.
