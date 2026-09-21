"""
client/gui.py
Contains the Tkinter graphical user interface for the Student Application.

Role in Project:
- Provides Screen 1: Server Connection (Name, IP, Port).
- Provides Screen 2: Active Poll View (Question, Radio-button options, Submit).
- Provides Screen 3: Vote Confirmation & Server Feedback.
- Runs all network calls on background threads to keep the UI completely responsive.
- Uses root.after() to safely update widgets from background threads.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading

# Import the NetworkClient from our network module
from client.network import NetworkClient


class StudentGUI:
    """
    Main Tkinter GUI manager for the Student Application.
    Manages switching between Connection, Poll, and Confirmation screens.
    """

    def __init__(self, root):
        self.root = root
        self.root.title("LAN Classroom Live Polling — Student")
        self.root.geometry("520x620")
        self.root.minsize(480, 560)
        self.root.configure(bg="#F4F6F9")

        # Network client instance (all socket logic stays inside this class)
        self.network = NetworkClient()

        # State tracking
        self.current_poll = None
        self.selected_option = tk.StringVar(value="")

        # Intercept window close button (X) to ensure clean socket disconnect
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Setup top persistent status bar
        self._setup_top_bar()

        # Main content container frame (swapped between screens)
        self.content_container = tk.Frame(self.root, bg="#F4F6F9")
        self.content_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))

        # Show Screen 1 by default
        self.show_connection_screen()

    # =========================================================================
    # Persistent Top Header Bar
    # =========================================================================
    def _setup_top_bar(self):
        """Creates a header showing connection status and student information."""
        self.top_bar = tk.Frame(self.root, bg="#1E293B", height=50)
        self.top_bar.pack(fill=tk.X, side=tk.TOP)

        self.title_label = tk.Label(
            self.top_bar,
            text="LAN Live Polling",
            font=("Segoe UI", 13, "bold"),
            bg="#1E293B",
            fg="#FFFFFF"
        )
        self.title_label.pack(side=tk.LEFT, padx=15, pady=12)

        self.user_badge = tk.Label(
            self.top_bar,
            text="Not Connected",
            font=("Segoe UI", 9),
            bg="#334155",
            fg="#94A3B8",
            padx=10,
            pady=3
        )
        self.user_badge.pack(side=tk.RIGHT, padx=15, pady=12)

    def _update_user_badge(self, text, is_connected=False):
        """Helper to update the top user status badge."""
        if is_connected:
            self.user_badge.config(
                text=text,
                bg="#15803D",  # Green
                fg="#FFFFFF"
            )
        else:
            self.user_badge.config(
                text=text,
                bg="#334155",
                fg="#94A3B8"
            )

    def _clear_content(self):
        """Destroys existing widgets inside the main container before switching screens."""
        for widget in self.content_container.winfo_children():
            widget.destroy()

    # =========================================================================
    # SCREEN 1: Connection Screen
    # =========================================================================
    def show_connection_screen(self):
        """Builds Screen 1: Connect to Teacher Server."""
        self._clear_content()
        self._update_user_badge("Not Connected", is_connected=False)

        card = tk.Frame(self.content_container, bg="#FFFFFF", padx=25, pady=25, relief=tk.RIDGE, bd=1)
        card.pack(fill=tk.BOTH, expand=True, pady=10)

        heading = tk.Label(
            card,
            text="Connect to Classroom",
            font=("Segoe UI", 16, "bold"),
            bg="#FFFFFF",
            fg="#0F172A"
        )
        heading.pack(anchor="w", pady=(0, 5))

        subtext = tk.Label(
            card,
            text="Enter your student name and teacher server IP address.",
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            fg="#64748B"
        )
        subtext.pack(anchor="w", pady=(0, 20))

        # 1. Student Name Input
        tk.Label(card, text="Your Full Name:", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#334155").pack(anchor="w", pady=(5, 2))
        self.name_entry = tk.Entry(card, font=("Segoe UI", 11), relief=tk.SOLID, bd=1)
        self.name_entry.pack(fill=tk.X, pady=(0, 12), ipady=5)
        self.name_entry.focus_set()

        # 2. Server IP Address Input
        tk.Label(card, text="Teacher Server IP:", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#334155").pack(anchor="w", pady=(5, 2))
        self.ip_entry = tk.Entry(card, font=("Segoe UI", 11), relief=tk.SOLID, bd=1)
        self.ip_entry.insert(0, "127.0.0.1")  # Useful default for local testing
        self.ip_entry.pack(fill=tk.X, pady=(0, 12), ipady=5)

        # 3. Server Port Input
        tk.Label(card, text="Server Port:", font=("Segoe UI", 10, "bold"), bg="#FFFFFF", fg="#334155").pack(anchor="w", pady=(5, 2))
        self.port_entry = tk.Entry(card, font=("Segoe UI", 11), relief=tk.SOLID, bd=1)
        self.port_entry.insert(0, "5000")  # Default server port
        self.port_entry.pack(fill=tk.X, pady=(0, 20), ipady=5)

        # 4. Status Message Label (shows errors, progress, or hints)
        self.conn_status_label = tk.Label(
            card,
            text="",
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            fg="#DC2626",
            wraplength=400,
            justify=tk.LEFT
        )
        self.conn_status_label.pack(fill=tk.X, pady=(0, 15))

        # 5. Connect Button
        self.connect_btn = tk.Button(
            card,
            text="Connect to Session",
            font=("Segoe UI", 11, "bold"),
            bg="#2563EB",
            fg="#FFFFFF",
            activebackground="#1D4ED8",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.handle_connect_click
        )
        self.connect_btn.pack(fill=tk.X, ipady=8)

    def handle_connect_click(self):
        """Validates inputs and spawns a background thread to connect."""
        name = self.name_entry.get().strip()
        ip = self.ip_entry.get().strip()
        port_str = self.port_entry.get().strip()

        # Basic input validation: Name and IP cannot be empty
        if not name:
            self.conn_status_label.config(text="Please enter your name.", fg="#DC2626")
            return
        if not ip:
            self.conn_status_label.config(text="Please enter the teacher's server IP.", fg="#DC2626")
            return
        if not port_str:
            self.conn_status_label.config(text="Please enter the server port.", fg="#DC2626")
            return

        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError()
        except ValueError:
            self.conn_status_label.config(text="Port must be a valid number between 1 and 65535.", fg="#DC2626")
            return

        # Disable button and display connecting message
        self.connect_btn.config(state=tk.DISABLED, text="Connecting...")
        self.conn_status_label.config(text="Connecting to teacher server...", fg="#2563EB")

        # Run connection on a background thread so the GUI does not freeze
        threading.Thread(
            target=self._async_connect,
            args=(ip, port, name),
            daemon=True
        ).start()

    def _async_connect(self, host, port, name):
        """Worker thread for network connect."""
        success, message = self.network.connect(host, port, name)

        if success:
            # Safely schedule GUI update on main thread
            self.root.after(0, self._on_connect_success, name, message)
        else:
            self.root.after(0, self._on_connect_failure, message)

    def _on_connect_success(self, student_name, message):
        """Callback on successful connection."""
        student_id = self.network.student_id or "Registered"
        self._update_user_badge(f"{student_name} ({student_id})", is_connected=True)
        # Fetch the active poll immediately
        self.fetch_active_poll()

    def _on_connect_failure(self, error_message):
        """Callback on failed connection."""
        self.connect_btn.config(state=tk.NORMAL, text="Connect to Session")
        self.conn_status_label.config(text=error_message, fg="#DC2626")

    # =========================================================================
    # SCREEN 2: Active Poll Screen
    # =========================================================================
    def fetch_active_poll(self):
        """Requests active poll on a background thread."""
        self._clear_content()

        # Loading card while fetching
        loading_card = tk.Frame(self.content_container, bg="#FFFFFF", padx=25, pady=25, relief=tk.RIDGE, bd=1)
        loading_card.pack(fill=tk.BOTH, expand=True, pady=10)

        tk.Label(
            loading_card,
            text="Checking for Active Poll...",
            font=("Segoe UI", 14, "bold"),
            bg="#FFFFFF",
            fg="#0F172A"
        ).pack(pady=40)

        threading.Thread(target=self._async_fetch_poll, daemon=True).start()

    def _async_fetch_poll(self):
        """Worker thread for GET_POLL."""
        success, result = self.network.get_poll()
        self.root.after(0, self._on_poll_received, success, result)

    def _on_poll_received(self, success, result):
        """Callback after poll request returns."""
        if success:
            # result is poll data dictionary: {"question": "...", "options": [...]}
            self.current_poll = result
            self.show_active_poll_screen(result)
        else:
            # result is a string status (e.g. "There is currently no active poll." or error)
            self.show_no_poll_screen(result)

    def show_no_poll_screen(self, message):
        """Shows screen when no active poll is running on the server."""
        self._clear_content()

        card = tk.Frame(self.content_container, bg="#FFFFFF", padx=25, pady=30, relief=tk.RIDGE, bd=1)
        card.pack(fill=tk.BOTH, expand=True, pady=10)

        tk.Label(
            card,
            text="No Active Poll",
            font=("Segoe UI", 16, "bold"),
            bg="#FFFFFF",
            fg="#0F172A"
        ).pack(pady=(10, 8))

        tk.Label(
            card,
            text=message,
            font=("Segoe UI", 11),
            bg="#FFFFFF",
            fg="#64748B",
            wraplength=420,
            justify=tk.CENTER
        ).pack(pady=(0, 25))

        # Button to check again if teacher launched a poll
        refresh_btn = tk.Button(
            card,
            text="🔄 Refresh / Check for Poll",
            font=("Segoe UI", 11, "bold"),
            bg="#2563EB",
            fg="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.fetch_active_poll
        )
        refresh_btn.pack(fill=tk.X, ipady=8, pady=(0, 10))

        # Disconnect button
        disconnect_btn = tk.Button(
            card,
            text="Disconnect",
            font=("Segoe UI", 10),
            bg="#E2E8F0",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.handle_disconnect
        )
        disconnect_btn.pack(fill=tk.X, ipady=6)

    def show_active_poll_screen(self, poll_data):
        """Builds Screen 2: Displays active poll question and options."""
        self._clear_content()
        self.selected_option.set("")  # Reset chosen option

        card = tk.Frame(self.content_container, bg="#FFFFFF", padx=25, pady=25, relief=tk.RIDGE, bd=1)
        card.pack(fill=tk.BOTH, expand=True, pady=10)

        # Header tag
        poll_tag = tk.Label(
            card,
            text="ACTIVE POLL",
            font=("Segoe UI", 9, "bold"),
            bg="#DBEAFE",
            fg="#1E40AF",
            padx=8,
            pady=3
        )
        poll_tag.pack(anchor="w", pady=(0, 10))

        # Question text
        question_text = poll_data.get("question", "Question not available")
        question_lbl = tk.Label(
            card,
            text=question_text,
            font=("Segoe UI", 14, "bold"),
            bg="#FFFFFF",
            fg="#0F172A",
            wraplength=420,
            justify=tk.LEFT
        )
        question_lbl.pack(anchor="w", pady=(0, 15))

        tk.Label(
            card,
            text="Select your answer:",
            font=("Segoe UI", 10, "bold"),
            bg="#FFFFFF",
            fg="#64748B"
        ).pack(anchor="w", pady=(0, 10))

        # Options Container Frame
        options_frame = tk.Frame(card, bg="#FFFFFF")
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        options = poll_data.get("options", [])
        for opt in options:
            opt_container = tk.Frame(options_frame, bg="#F8FAFC", relief=tk.SOLID, bd=1, padx=10, pady=8)
            opt_container.pack(fill=tk.X, pady=4)

            rb = tk.Radiobutton(
                opt_container,
                text=opt,
                value=opt,
                variable=self.selected_option,
                font=("Segoe UI", 11),
                bg="#F8FAFC",
                activebackground="#F8FAFC",
                highlightthickness=0,
                cursor="hand2"
            )
            rb.pack(anchor="w")

        # Validation / Status message label
        self.poll_status_label = tk.Label(
            card,
            text="",
            font=("Segoe UI", 10),
            bg="#FFFFFF",
            fg="#DC2626",
            wraplength=420,
            justify=tk.LEFT
        )
        self.poll_status_label.pack(fill=tk.X, pady=(0, 10))

        # Action Buttons Container
        actions_frame = tk.Frame(card, bg="#FFFFFF")
        actions_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Submit Vote Button
        self.submit_btn = tk.Button(
            actions_frame,
            text="Submit Vote",
            font=("Segoe UI", 11, "bold"),
            bg="#16A34A",  # Green
            fg="#FFFFFF",
            activebackground="#15803D",
            activeforeground="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.handle_submit_vote
        )
        self.submit_btn.pack(fill=tk.X, ipady=8, pady=(0, 8))

        # Secondary Actions (Refresh & Disconnect)
        sub_actions = tk.Frame(actions_frame, bg="#FFFFFF")
        sub_actions.pack(fill=tk.X)

        refresh_btn = tk.Button(
            sub_actions,
            text="🔄 Refresh",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.fetch_active_poll
        )
        refresh_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4), ipady=4)

        disconnect_btn = tk.Button(
            sub_actions,
            text="Disconnect",
            font=("Segoe UI", 9),
            bg="#E2E8F0",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.handle_disconnect
        )
        disconnect_btn.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(4, 0), ipady=4)

    def handle_submit_vote(self):
        """Validates selection and sends vote on a background thread."""
        chosen = self.selected_option.get().strip()

        # Constraint: Do not allow submission without selecting an option
        if not chosen:
            self.poll_status_label.config(text="Please select one option before submitting.", fg="#DC2626")
            return

        # Disable submit button while request is being processed
        self.submit_btn.config(state=tk.DISABLED, text="Submitting Vote...")
        self.poll_status_label.config(text="Sending vote to server...", fg="#2563EB")

        # Run network operation in background thread
        threading.Thread(
            target=self._async_submit_vote,
            args=(chosen,),
            daemon=True
        ).start()

    def _async_submit_vote(self, option):
        """Worker thread for VOTE."""
        success, message = self.network.submit_vote(option)
        self.root.after(0, self._on_vote_response, success, message, option)

    def _on_vote_response(self, success, message, chosen_option):
        """Callback when vote submission returns."""
        # Screen 3: Vote Response Screen
        self.show_vote_response_screen(success, message, chosen_option)

    # =========================================================================
    # SCREEN 3: Vote Response & Confirmation Screen
    # =========================================================================
    def show_vote_response_screen(self, success, message, chosen_option):
        """Builds Screen 3: Shows server vote confirmation or rejection."""
        self._clear_content()

        card = tk.Frame(self.content_container, bg="#FFFFFF", padx=25, pady=30, relief=tk.RIDGE, bd=1)
        card.pack(fill=tk.BOTH, expand=True, pady=10)

        # Configure styling based on success or rejection
        if success:
            icon_text = "✔"
            icon_color = "#16A34A"  # Green
            header_text = "Vote Submitted!"
            badge_bg = "#DCFCE7"
            badge_fg = "#166534"
        else:
            icon_text = "✖"
            icon_color = "#DC2626"  # Red
            header_text = "Submission Failed"
            badge_bg = "#FEE2E2"
            badge_fg = "#991B1B"

        # Large icon
        tk.Label(
            card,
            text=icon_text,
            font=("Segoe UI", 36, "bold"),
            bg="#FFFFFF",
            fg=icon_color
        ).pack(pady=(10, 5))

        # Title
        tk.Label(
            card,
            text=header_text,
            font=("Segoe UI", 16, "bold"),
            bg="#FFFFFF",
            fg="#0F172A"
        ).pack(pady=(0, 10))

        # Server message badge
        msg_box = tk.Label(
            card,
            text=message,
            font=("Segoe UI", 11, "bold"),
            bg=badge_bg,
            fg=badge_fg,
            padx=12,
            pady=8,
            wraplength=380,
            justify=tk.CENTER
        )
        msg_box.pack(fill=tk.X, pady=(0, 20))

        # Selected Option Summary
        summary_frame = tk.Frame(card, bg="#F8FAFC", padx=15, pady=12, relief=tk.SOLID, bd=1)
        summary_frame.pack(fill=tk.X, pady=(0, 25))

        tk.Label(
            summary_frame,
            text="Your Selected Choice:",
            font=("Segoe UI", 9, "bold"),
            bg="#F8FAFC",
            fg="#64748B"
        ).pack(anchor="w")

        tk.Label(
            summary_frame,
            text=f'"{chosen_option}"',
            font=("Segoe UI", 12, "bold"),
            bg="#F8FAFC",
            fg="#1E293B"
        ).pack(anchor="w", pady=(3, 0))

        # Action Buttons
        check_next_btn = tk.Button(
            card,
            text="🔄 Check for Next Poll",
            font=("Segoe UI", 11, "bold"),
            bg="#2563EB",
            fg="#FFFFFF",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.fetch_active_poll
        )
        check_next_btn.pack(fill=tk.X, ipady=8, pady=(0, 10))

        disconnect_btn = tk.Button(
            card,
            text="Disconnect",
            font=("Segoe UI", 10),
            bg="#E2E8F0",
            fg="#334155",
            relief=tk.FLAT,
            cursor="hand2",
            command=self.handle_disconnect
        )
        disconnect_btn.pack(fill=tk.X, ipady=6)

    # =========================================================================
    # Disconnect & Window Closing
    # =========================================================================
    def handle_disconnect(self):
        """Disconnects from server and returns to connection screen."""
        threading.Thread(target=self.network.disconnect, daemon=True).start()
        self.show_connection_screen()

    def on_closing(self):
        """Clean shutdown handler when student closes the application window."""
        try:
            self.network.disconnect()
        except Exception:
            pass
        self.root.destroy()
