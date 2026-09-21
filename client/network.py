"""
client/network.py
Handles TCP socket communication and JSON messaging for the Student Application.

Role in Project:
- Establishes a TCP connection to the teacher's server over the local network (LAN).
- Sends and receives JSON messages using newline delimiters (\\n).
- Manages connection lifecycle (connect, get poll, submit vote, disconnect).
"""

import socket
import json
import threading


class NetworkClient:
    """
    Network client class responsible for all network communication with the teacher's server.
    Keeps socket handling isolated from the GUI so the interface never crashes or freezes.
    """

    def __init__(self):
        self.host = None
        self.port = None
        self.sock = None
        self.student_id = None
        self.student_name = None
        self.is_connected = False
        
        # Buffer to accumulate incoming socket data across recv() calls
        self._buffer = ""
        
        # Lock to ensure thread-safe socket operations
        self._lock = threading.Lock()

    def connect(self, host, port, student_name, timeout=5):
        """
        Connects to the teacher's server and sends the initial CONNECT message.
        
        Parameters:
            host (str): Server IP address (e.g., '192.168.1.15' or '127.0.0.1')
            port (int): Server port number (e.g., 5000)
            student_name (str): The name entered by the student
            timeout (int): Timeout in seconds for socket operations
            
        Returns:
            tuple: (success: bool, message: str)
        """
        with self._lock:
            # If already connected, close the previous socket first
            if self.sock:
                self._close_socket()

            self.host = host
            self.port = port
            self.student_name = student_name
            self._buffer = ""

            try:
                # Create a standard TCP IPv4 streaming socket
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.settimeout(timeout)
                
                # Attempt to connect to the teacher server
                self.sock.connect((self.host, self.port))

                # Step 1: Send the CONNECT message as per the shared protocol
                connect_msg = {
                    "type": "CONNECT",
                    "student_name": self.student_name
                }
                self._send_json_locked(connect_msg)

                # Step 2: Receive the server's response
                response = self._recv_json_locked()
                if not response:
                    self._close_socket()
                    return False, "Server closed the connection without responding."

                msg_type = response.get("type")
                if msg_type == "CONNECT_SUCCESS":
                    # Store student_id assigned by the server (never generate it on the client)
                    self.student_id = response.get("student_id")
                    self.is_connected = True
                    server_msg = response.get("message", "Connected successfully.")
                    return True, server_msg
                
                elif msg_type == "ERROR":
                    err_msg = response.get("message", "Connection was rejected by the server.")
                    self._close_socket()
                    return False, err_msg
                
                else:
                    self._close_socket()
                    return False, f"Unexpected response from server: {response}"

            except socket.timeout:
                self._close_socket()
                return False, f"Connection timed out after {timeout} seconds. Check if server IP and Port are correct."
            except ConnectionRefusedError:
                self._close_socket()
                return False, f"Connection refused at {self.host}:{self.port}. Is the teacher server running?"
            except socket.gaierror:
                self._close_socket()
                return False, f"Invalid server IP address '{self.host}'. Please verify the IP."
            except OSError as e:
                self._close_socket()
                return False, f"Network error: {str(e)}"
            except Exception as e:
                self._close_socket()
                return False, f"Failed to connect: {str(e)}"

    def get_poll(self):
        """
        Requests the current active poll from the server.
        
        Returns:
            tuple: (success: bool, data_or_message: dict or str)
                   If success is True, data_or_message is the poll dict with 'question' and 'options'.
                   If success is False, data_or_message is an error or status string.
        """
        with self._lock:
            if not self.is_connected or not self.sock:
                return False, "Not connected to the server."

            try:
                # Send GET_POLL message
                get_poll_msg = {
                    "type": "GET_POLL"
                }
                self._send_json_locked(get_poll_msg)

                # Receive response
                response = self._recv_json_locked()
                if not response:
                    return False, "Lost connection to the server while fetching poll."

                msg_type = response.get("type")

                # Successful active poll received
                if msg_type == "POLL":
                    question = response.get("question", "")
                    options = response.get("options", [])
                    if not question or not options:
                        return False, "Received an empty poll from the server."
                    return True, response

                # Server reports no active poll is currently open
                elif msg_type in ("NO_ACTIVE_POLL", "NO_POLL"):
                    message = response.get("message", "There is currently no active poll.")
                    return False, message

                elif msg_type == "ERROR":
                    return False, response.get("message", "Server reported an error.")

                else:
                    return False, f"Unexpected server response: {response}"

            except socket.timeout:
                return False, "Timed out waiting for poll data from the server."
            except (ConnectionResetError, BrokenPipeError):
                self._close_socket()
                return False, "Server disconnected unexpectedly."
            except Exception as e:
                return False, f"Error requesting poll: {str(e)}"

    def submit_vote(self, option):
        """
        Submits the student's selected option to the server.
        
        Parameters:
            option (str): The exact text of the selected poll option.
            
        Returns:
            tuple: (success: bool, message: str)
        """
        with self._lock:
            if not self.is_connected or not self.sock:
                return False, "Not connected to the server."

            if not self.student_id:
                return False, "No valid Student ID found. Please reconnect."

            try:
                # Send VOTE message with student_id from server and the exact option string
                vote_msg = {
                    "type": "VOTE",
                    "student_id": self.student_id,
                    "option": option
                }
                self._send_json_locked(vote_msg)

                # Receive response from server
                response = self._recv_json_locked()
                if not response:
                    return False, "Lost connection to the server while submitting vote."

                msg_type = response.get("type")

                if msg_type == "VOTE_SUCCESS":
                    return True, response.get("message", "Vote submitted successfully.")
                elif msg_type == "ERROR":
                    # Could be "You have already voted.", "Invalid option", or "No active poll"
                    return False, response.get("message", "Vote was rejected by the server.")
                else:
                    return False, f"Unexpected response from server: {response}"

            except socket.timeout:
                return False, "Timed out waiting for server to confirm your vote."
            except (ConnectionResetError, BrokenPipeError):
                self._close_socket()
                return False, "Server disconnected while submitting vote."
            except Exception as e:
                return False, f"Error submitting vote: {str(e)}"

    def disconnect(self):
        """
        Gracefully closes the connection to the server.
        """
        with self._lock:
            self._close_socket()

    def _close_socket(self):
        """
        Internal helper to safely shut down and close the socket.
        Must be called while holding self._lock.
        """
        if self.sock:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                # Socket might already be closed or disconnected
                pass
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

        self.is_connected = False
        self.student_id = None
        self._buffer = ""

    def _send_json_locked(self, data):
        """
        Encodes a Python dictionary to a JSON string, appends a newline delimiter (\\n),
        and sends it over the socket.
        Must be called while holding self._lock.
        """
        # Convert dictionary to JSON string and append newline
        message_str = json.dumps(data) + "\n"
        # Send all bytes using UTF-8 encoding
        self.sock.sendall(message_str.encode("utf-8"))

    def _recv_json_locked(self):
        """
        Reads data from the socket until a complete newline-delimited message is received.
        Buffers any remaining data for subsequent calls.
        Must be called while holding self._lock.
        
        Returns:
            dict or None: The parsed JSON message, or None if the connection was closed.
        """
        while "\n" not in self._buffer:
            chunk = self.sock.recv(4096)
            if not chunk:
                # Server closed the connection
                return None
            self._buffer += chunk.decode("utf-8")

        # Split at the first newline character
        line, self._buffer = self._buffer.split("\n", 1)
        line = line.strip()
        
        if not line:
            return None

        # Parse the JSON message
        return json.loads(line)
