"""
server/server.py
Main entry point for the classroom polling TCP server.

How to Run from the Project Root:
    python -m server.server
    (or: python server/server.py)

Optional arguments:
    python -m server.server --host 0.0.0.0 --port 5000

Role in Project:
- Opens a TCP socket and listens for student and teacher connections on
  the LAN.
- Spawns one thread per connected client so a slow or stalled client can
  never block anyone else.
- Speaks newline-delimited JSON (see common/protocol.py) and routes each
  message to the poll manager, never implementing poll/vote logic itself.
- Serializes all access to shared state (the poll manager and the roster
  of connected students) behind a single lock, since many client threads
  can call in concurrently.
"""

import argparse
import json
import logging
import os
import socket
import sys
import threading
import uuid

# Ensure the project root directory is on sys.path so imports work whether
# this file is executed as 'python -m server.server' or 'python server/server.py'.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from common.protocol import (
    CONNECT, CONNECT_SUCCESS, GET_POLL, VOTE, VOTE_SUCCESS,
    CREATE_POLL, POLL_CREATED, CLOSE_POLL, POLL_CLOSED,
    GET_RESULTS, ERROR, DEFAULT_HOST, DEFAULT_PORT, MESSAGE_DELIMITER,
)
from server.poll_manager import PollManager
from server.results import generate_results_message

# Absolute path so the server behaves the same regardless of the directory
# it is launched from.
DEFAULT_DATA_FILE = os.path.join(project_root, "data", "polls.json")

# Defensive cap on a single buffered message. A well-behaved client never
# gets close to this; it exists so a broken or hostile client that never
# sends a newline cannot grow this server's memory without bound.
MAX_MESSAGE_SIZE = 64 * 1024

logger = logging.getLogger("classroom_server")


def get_local_ip():
    """
    Best-effort discovery of this machine's LAN-facing IPv4 address, using
    only the standard library and without depending on internet access.

    The UDP "connect" below never actually transmits a packet -- connecting
    a UDP socket just asks the OS to pick which local interface/address it
    would use to route to that destination, which works purely from the
    local routing table even if 8.8.8.8 is unreachable.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        pass
    finally:
        sock.close()

    # Fallback: ask the hostname for its addresses and pick the first
    # non-loopback IPv4 one.
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                return ip
    except OSError:
        pass

    return "127.0.0.1"


class ClassroomServer:
    """
    Threaded TCP server for the LAN classroom polling app.

    Owns the network layer only: accepting connections, framing messages,
    and routing them. All poll/vote business logic lives in PollManager;
    this class never duplicates it.
    """

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, data_file=DEFAULT_DATA_FILE):
        self.host = host
        self.port = port
        self.poll_manager = PollManager(data_file=data_file)

        # Guards self.poll_manager, self.students, and self.client_sockets.
        # PollManager itself has no internal locking, so every call into it
        # from this server must happen while holding this lock.
        self.lock = threading.Lock()

        self.students = {}          # student_id -> student_name (session roster)
        self.client_sockets = set() # open connections, for clean shutdown

        self.server_socket = None
        self._running = False

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------
    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if sys.platform == "win32":
            # On Windows, SO_REUSEADDR is far more permissive than on
            # POSIX: it can let a second process silently bind the same
            # port an existing server is actively listening on, instead of
            # failing with "address in use". SO_EXCLUSIVEADDRUSE is the
            # Windows-recommended option that actually prevents that.
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            # On Linux/macOS, SO_REUSEADDR lets the server restart quickly
            # after a crash without waiting out a lingering TIME_WAIT socket.
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((self.host, self.port))
        except OSError as e:
            # EADDRINUSE on Linux/macOS is errno 98; WSAEADDRINUSE on Windows is 10048.
            if e.errno in (98, 10048):
                logger.error(f"Could not start server: port {self.port} is already in use.")
            else:
                logger.error(f"Could not start server: {e}")
            self.server_socket.close()
            self.server_socket = None
            sys.exit(1)

        self.server_socket.listen(5)
        # A timeout on the listening socket lets the accept loop wake up
        # periodically and check self._running, so Ctrl+C is handled
        # promptly instead of blocking forever inside accept().
        self.server_socket.settimeout(1.0)
        self._running = True

        self._print_banner()
        logger.info(f"Server started on {self.host}:{self.port}")
        logger.info("Waiting for clients... (Press CTRL+C to stop)")

        try:
            while self._running:
                try:
                    conn, addr = self.server_socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                with self.lock:
                    self.client_sockets.add(conn)

                threading.Thread(
                    target=self._handle_client, args=(conn, addr), daemon=True
                ).start()
        except KeyboardInterrupt:
            logger.info("Shutdown requested (CTRL+C).")
        finally:
            self.shutdown()

    def shutdown(self):
        if not self._running:
            return
        self._running = False

        with self.lock:
            sockets_to_close = list(self.client_sockets)
            self.client_sockets.clear()

        for conn in sockets_to_close:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass

        if self.server_socket:
            try:
                self.server_socket.close()
            except OSError:
                pass
            self.server_socket = None

        logger.info("Server stopped.")

    def _print_banner(self):
        local_ip = get_local_ip()
        width = 50
        print("=" * width)
        print(" LAN CLASSROOM POLLING SERVER".center(width))
        print("=" * width)
        print(f" Server IP : {local_ip}")
        print(f" Port      : {self.port}")
        print("=" * width)
        print(" Students should connect using the IP address above.")
        print(" (If the server and student are on the same machine,")
        print("  127.0.0.1 also works.)")
        print("=" * width)

    # ------------------------------------------------------------------
    # Per-client handling
    # ------------------------------------------------------------------
    def _handle_client(self, conn, addr):
        client_label = f"{addr[0]}:{addr[1]}"
        logger.info(f"Client connected: {client_label}")
        buffer = ""

        try:
            while self._running:
                try:
                    chunk = conn.recv(4096)
                except (ConnectionResetError, OSError):
                    break

                if not chunk:
                    # Peer closed the connection (e.g. the student clicked
                    # Disconnect, or the teacher dashboard's one-shot
                    # request finished).
                    break

                buffer += chunk.decode("utf-8", errors="replace")

                if len(buffer) > MAX_MESSAGE_SIZE:
                    logger.warning(f"Message from {client_label} exceeded size limit; closing connection.")
                    self._send_json(conn, self._error("MESSAGE_TOO_LARGE", "Message too large."))
                    return

                while MESSAGE_DELIMITER in buffer:
                    line, buffer = buffer.split(MESSAGE_DELIMITER, 1)
                    line = line.strip()
                    if not line:
                        continue
                    response = self._process_line(line, client_label)
                    self._send_json(conn, response)
        except Exception:
            logger.exception(f"Unexpected error while handling client {client_label}")
        finally:
            with self.lock:
                self.client_sockets.discard(conn)
            try:
                conn.close()
            except OSError:
                pass
            logger.info(f"Client disconnected: {client_label}")

    def _process_line(self, line, client_label):
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON from {client_label}: {line!r}")
            return self._error("INVALID_JSON", "Invalid message received.")

        if not isinstance(msg, dict):
            return self._error("INVALID_MESSAGE", "Message must be a JSON object.")

        msg_type = msg.get("type")

        if msg_type == CONNECT:
            return self._handle_connect(msg, client_label)
        elif msg_type == GET_POLL:
            return self._handle_get_poll()
        elif msg_type == VOTE:
            return self._handle_vote(msg)
        elif msg_type == CREATE_POLL:
            return self._handle_create_poll(msg)
        elif msg_type == CLOSE_POLL:
            return self._handle_close_poll()
        elif msg_type == GET_RESULTS:
            return self._handle_get_results()
        else:
            logger.warning(f"Unknown request type '{msg_type}' from {client_label}")
            return self._error("UNKNOWN_TYPE", "Unknown request type.")

    # ------------------------------------------------------------------
    # Message handlers -- these route to PollManager; no poll/vote logic
    # is duplicated here.
    # ------------------------------------------------------------------
    def _handle_connect(self, msg, client_label):
        name = msg.get("student_name")
        if not isinstance(name, str) or not name.strip():
            return self._error("INVALID_NAME", "Student name cannot be empty.")
        name = name.strip()

        student_id = f"student_{uuid.uuid4().hex[:8]}"
        with self.lock:
            self.students[student_id] = name

        logger.info(f"Student registered: {name} ({student_id}) from {client_label}")
        return {
            "type": CONNECT_SUCCESS,
            "student_id": student_id,
            "message": f"Welcome, {name}! Connected to the classroom session.",
        }

    def _handle_get_poll(self):
        with self.lock:
            return self.poll_manager.get_active_poll()

    def _handle_vote(self, msg):
        student_id = msg.get("student_id")
        option = msg.get("option")

        if not isinstance(student_id, str) or not student_id:
            return self._error("INVALID_STUDENT_ID", "Missing or invalid student ID. Please reconnect.")
        if not isinstance(option, str) or not option:
            return self._error("INVALID_OPTION", "Missing or invalid option.")

        with self.lock:
            # Don't trust a client-supplied ID blindly -- it must be one we
            # actually issued via CONNECT.
            if student_id not in self.students:
                return self._error("UNREGISTERED_STUDENT", "Unknown student ID. Please reconnect.")
            student_name = self.students[student_id]
            success, message = self.poll_manager.submit_vote(student_id, option)

        if success:
            logger.info(f"Vote accepted: student={student_name} option={option}")
            return {"type": VOTE_SUCCESS, "message": message}

        logger.info(f"Vote rejected: student={student_name} option={option} reason={message}")
        return self._error(self._vote_error_code(message), message)

    @staticmethod
    def _vote_error_code(message):
        return {
            "No active poll": "NO_ACTIVE_POLL",
            "You have already voted": "ALREADY_VOTED",
            "Invalid option": "INVALID_OPTION",
        }.get(message, "VOTE_REJECTED")

    def _handle_create_poll(self, msg):
        question = msg.get("question")
        options = msg.get("options")

        if not isinstance(question, str) or not question.strip():
            return self._error("INVALID_QUESTION", "Poll question cannot be empty.")

        if not isinstance(options, list):
            return self._error("INVALID_OPTIONS", "Poll options must be a list.")
        clean_options = [o.strip() for o in options if isinstance(o, str) and o.strip()]
        if len(clean_options) < 2:
            return self._error("INVALID_OPTIONS", "Poll must have at least 2 valid options.")

        with self.lock:
            if self.poll_manager.active_poll_id:
                return self._error(
                    "POLL_ALREADY_ACTIVE",
                    "A poll is already active. Close it before creating a new one.",
                )

            poll_id = self.poll_manager.create_poll(question.strip(), clean_options)
            started, start_message = self.poll_manager.start_poll(poll_id)

        if not started:
            return self._error("POLL_START_FAILED", start_message)

        logger.info(f"Poll created: {poll_id} - '{question.strip()}'")
        return {"type": POLL_CREATED, "poll_id": poll_id, "message": "Poll created and is now live."}

    def _handle_close_poll(self):
        with self.lock:
            success, message = self.poll_manager.close_poll()

        if success:
            logger.info("Poll closed.")
            return {"type": POLL_CLOSED, "message": message}
        return self._error("NO_ACTIVE_POLL", message)

    def _handle_get_results(self):
        with self.lock:
            active_id = self.poll_manager.active_poll_id
            poll_data = self.poll_manager.data["polls"][active_id] if active_id else None
            return generate_results_message(poll_data)

    # ------------------------------------------------------------------
    # Wire helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _error(code, message):
        return {"type": ERROR, "code": code, "message": message}

    @staticmethod
    def _send_json(conn, data):
        try:
            payload = (json.dumps(data) + MESSAGE_DELIMITER).encode("utf-8")
            conn.sendall(payload)
        except OSError:
            # Peer is already gone; the recv loop will notice and clean up.
            pass


def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="LAN Classroom Live Polling Server")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host/interface to bind (default: {DEFAULT_HOST})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default: {DEFAULT_PORT})")
    args = parser.parse_args()

    configure_logging()

    server = ClassroomServer(host=args.host, port=args.port)
    server.start()


if __name__ == "__main__":
    main()
