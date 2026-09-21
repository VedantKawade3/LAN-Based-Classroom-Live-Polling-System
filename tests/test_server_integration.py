"""
tests/test_server_integration.py
End-to-end integration tests for the networking layer.

How to Run from the Project Root:
    python -m unittest tests.test_server_integration -v

These tests start a real ClassroomServer on a background thread and talk to
it using the project's actual production client code -- client.network.NetworkClient
for the student side, and TeacherDashboard.send_request (via a real, hidden
Tk root) for the teacher side -- rather than hand-rolled sockets. This
validates the real wire protocol both sides actually use, not a simulation
of it.

Uses only the standard library (unittest), consistent with the project's
"stdlib only" dependency policy.
"""

import json
import os
import socket
import sys
import threading
import time
import tkinter as tk
import unittest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from server.server import ClassroomServer
from client.network import NetworkClient
from server.teacher_gui import TeacherDashboard


def _free_port():
    """Ask the OS for an unused port so parallel test runs never collide."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerIntegrationTestCase(unittest.TestCase):
    """Each test gets its own server instance, port, and data file."""

    def setUp(self):
        self.port = _free_port()
        self.data_file = os.path.join(
            project_root, "data", f"test_polls_{self.port}.json"
        )
        self.server = ClassroomServer(host="127.0.0.1", port=self.port, data_file=self.data_file)

        self.server_thread = threading.Thread(target=self.server.start, daemon=True)
        self.server_thread.start()
        self._wait_until_listening()

        # server/teacher_gui.py talks to a hardcoded host/port; point it at
        # this test's server for the duration of the test.
        import server.teacher_gui as teacher_gui_module
        self._orig_host = teacher_gui_module.SERVER_HOST
        self._orig_port = teacher_gui_module.SERVER_PORT
        teacher_gui_module.SERVER_HOST = "127.0.0.1"
        teacher_gui_module.SERVER_PORT = self.port
        self.teacher_gui_module = teacher_gui_module

    def tearDown(self):
        self.teacher_gui_module.SERVER_HOST = self._orig_host
        self.teacher_gui_module.SERVER_PORT = self._orig_port
        self.server.shutdown()
        self.server_thread.join(timeout=5)
        if os.path.exists(self.data_file):
            os.remove(self.data_file)

    def _wait_until_listening(self, timeout=5):
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=0.2):
                    return
            except OSError:
                time.sleep(0.05)
        self.fail("Server did not start listening in time")

    def _make_teacher(self):
        """Real TeacherDashboard instance backed by a hidden Tk root."""
        root = tk.Tk()
        root.withdraw()
        dashboard = TeacherDashboard(root)
        self.addCleanup(root.destroy)
        return dashboard

    def _make_student(self, name):
        client = NetworkClient()
        self.addCleanup(client.disconnect)
        return client

    # ------------------------------------------------------------------
    def test_full_poll_lifecycle_single_student(self):
        teacher = self._make_teacher()
        student = self._make_student("Alice")

        ok, msg = student.connect("127.0.0.1", self.port, "Alice")
        self.assertTrue(ok, msg)
        self.assertIsNotNone(student.student_id)

        ok, result = student.get_poll()
        self.assertFalse(ok)  # no poll yet

        response = teacher.send_request({
            "type": "CREATE_POLL",
            "question": "Best language?",
            "options": ["Python", "Java"],
        })
        self.assertEqual(response.get("type"), "POLL_CREATED")

        ok, poll = student.get_poll()
        self.assertTrue(ok)
        self.assertEqual(poll["question"], "Best language?")
        self.assertEqual(poll["options"], ["Python", "Java"])

        ok, msg = student.submit_vote("Python")
        self.assertTrue(ok, msg)

        results = teacher.send_request({"type": "GET_RESULTS"})
        self.assertEqual(results["results"]["Python"], 1)
        self.assertEqual(results["total_votes"], 1)

        response = teacher.send_request({"type": "CLOSE_POLL"})
        self.assertEqual(response.get("type"), "POLL_CLOSED")

    def test_duplicate_vote_rejected(self):
        teacher = self._make_teacher()
        student = self._make_student("Bob")
        student.connect("127.0.0.1", self.port, "Bob")
        teacher.send_request({
            "type": "CREATE_POLL", "question": "Q?", "options": ["A", "B"],
        })

        ok1, _ = student.submit_vote("A")
        ok2, msg2 = student.submit_vote("B")

        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertIn("already voted", msg2.lower())

        results = teacher.send_request({"type": "GET_RESULTS"})
        self.assertEqual(results["total_votes"], 1)

    def test_multiple_students_concurrent_voting(self):
        teacher = self._make_teacher()
        teacher.send_request({
            "type": "CREATE_POLL",
            "question": "Pick one",
            "options": ["Python", "Java", "C++"],
        })

        names_and_choices = [
            ("S1", "Python"), ("S2", "Java"), ("S3", "Python"), ("S4", "C++"),
        ]
        clients = []
        for name, _ in names_and_choices:
            c = self._make_student(name)
            ok, msg = c.connect("127.0.0.1", self.port, name)
            self.assertTrue(ok, msg)
            clients.append(c)

        results_holder = {}
        barrier = threading.Barrier(len(clients))

        def vote(client, choice, key):
            barrier.wait(timeout=5)
            results_holder[key] = client.submit_vote(choice)

        threads = [
            threading.Thread(target=vote, args=(c, choice, i))
            for i, (c, (_, choice)) in enumerate(zip(clients, names_and_choices))
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        for key, (ok, msg) in results_holder.items():
            self.assertTrue(ok, f"vote {key} failed: {msg}")

        results = teacher.send_request({"type": "GET_RESULTS"})
        self.assertEqual(results["results"]["Python"], 2)
        self.assertEqual(results["results"]["Java"], 1)
        self.assertEqual(results["results"]["C++"], 1)
        self.assertEqual(results["total_votes"], 4)

    def test_vote_without_active_poll_is_rejected(self):
        student = self._make_student("Cara")
        student.connect("127.0.0.1", self.port, "Cara")

        ok, msg = student.submit_vote("Python")
        self.assertFalse(ok)
        self.assertIn("no active poll", msg.lower())

    def test_invalid_option_is_rejected(self):
        teacher = self._make_teacher()
        student = self._make_student("Dan")
        student.connect("127.0.0.1", self.port, "Dan")
        teacher.send_request({
            "type": "CREATE_POLL", "question": "Q?", "options": ["A", "B"],
        })

        ok, msg = student.submit_vote("Z")
        self.assertFalse(ok)
        self.assertIn("invalid option", msg.lower())

    def test_second_create_poll_rejected_while_one_active(self):
        teacher = self._make_teacher()
        r1 = teacher.send_request({
            "type": "CREATE_POLL", "question": "Q1?", "options": ["A", "B"],
        })
        self.assertEqual(r1.get("type"), "POLL_CREATED")

        r2 = teacher.send_request({
            "type": "CREATE_POLL", "question": "Q2?", "options": ["C", "D"],
        })
        self.assertEqual(r2.get("type"), "ERROR")

    def test_malformed_message_does_not_crash_server(self):
        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as s:
            s.sendall(b"not json at all\n")
            data = s.recv(4096).decode("utf-8")
        self.assertIn("ERROR", data)

        # Server must still be alive and able to serve a normal client.
        student = self._make_student("Eve")
        ok, msg = student.connect("127.0.0.1", self.port, "Eve")
        self.assertTrue(ok, msg)

    def test_spoofed_student_id_is_rejected(self):
        """A vote using a student_id the server never issued must be rejected."""
        teacher = self._make_teacher()
        teacher.send_request({
            "type": "CREATE_POLL", "question": "Q?", "options": ["A", "B"],
        })

        with socket.create_connection(("127.0.0.1", self.port), timeout=2) as s:
            msg = {"type": "VOTE", "student_id": "student_totally_made_up", "option": "A"}
            s.sendall((json.dumps(msg) + "\n").encode())
            buf = ""
            while "\n" not in buf:
                buf += s.recv(4096).decode()

        response = json.loads(buf.strip())
        self.assertEqual(response.get("type"), "ERROR")
        self.assertEqual(response.get("code"), "UNREGISTERED_STUDENT")

        results = teacher.send_request({"type": "GET_RESULTS"})
        self.assertEqual(results["total_votes"], 0)

    def test_disconnect_then_reconnect(self):
        student = self._make_student("Fay")
        ok, _ = student.connect("127.0.0.1", self.port, "Fay")
        self.assertTrue(ok)
        student.disconnect()

        ok, msg = student.connect("127.0.0.1", self.port, "Fay")
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
