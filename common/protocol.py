"""
common/protocol.py
Single source of truth for the network protocol shared by the server,
the teacher dashboard, and the student client.

Why this file exists:
Message type strings and network defaults used to live as duplicated
literals scattered across client and server files. Keeping them here
means every part of the project agrees on the same values by construction
instead of by convention.
"""

# --- Network defaults --------------------------------------------------
# 0.0.0.0 means "listen on every network interface", so machines elsewhere
# on the LAN can reach this one. Do not change this to 127.0.0.1, or only
# the teacher's own machine will be able to connect.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 5000

# --- Message framing -----------------------------------------------------
# TCP is a byte stream with no built-in concept of "messages". Both sides
# terminate every JSON message with this delimiter so the receiver knows
# exactly where one message ends and the next begins.
MESSAGE_DELIMITER = "\n"

# --- Message types: student <-> server ------------------------------------
CONNECT = "CONNECT"
CONNECT_SUCCESS = "CONNECT_SUCCESS"
GET_POLL = "GET_POLL"
POLL = "POLL"
NO_POLL = "NO_POLL"
VOTE = "VOTE"
VOTE_SUCCESS = "VOTE_SUCCESS"

# --- Message types: teacher <-> server -------------------------------------
CREATE_POLL = "CREATE_POLL"
POLL_CREATED = "POLL_CREATED"
CLOSE_POLL = "CLOSE_POLL"
POLL_CLOSED = "POLL_CLOSED"
GET_RESULTS = "GET_RESULTS"
RESULTS = "RESULTS"

# --- Shared ----------------------------------------------------------------
ERROR = "ERROR"
