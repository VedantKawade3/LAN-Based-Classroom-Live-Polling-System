import tkinter as tk
from tkinter import messagebox
import socket
import json

SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000

class TeacherDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("CLASSROOM POLLING - TEACHER")
        self.root.geometry("450x550")
        
        self.setup_ui()
        self.update_results()
        
    def send_request(self, data):
        """Send a JSON request to the server and return the response."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)  # Timeout so the GUI doesn't freeze
                s.connect((SERVER_HOST, SERVER_PORT))
                s.sendall(json.dumps(data).encode('utf-8'))
                response = s.recv(4096).decode('utf-8')
                return json.loads(response)
        except Exception:
            return None
            
    def setup_ui(self):
        # --- Question Input ---
        tk.Label(self.root, text="Question:").pack(anchor='w', padx=20, pady=(15, 0))
        self.question_entry = tk.Entry(self.root, width=50)
        self.question_entry.pack(padx=20, pady=5)
        
        # --- Options Input ---
        self.option_entries = []
        for i in range(4):
            tk.Label(self.root, text=f"Option {i+1}:").pack(anchor='w', padx=20)
            entry = tk.Entry(self.root, width=50)
            entry.pack(padx=20, pady=2)
            self.option_entries.append(entry)
            
        # --- Buttons ---
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="CREATE POLL", width=15, bg="lightblue", command=self.create_poll).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="CLOSE POLL", width=15, bg="lightcoral", command=self.close_poll).pack(side=tk.LEFT, padx=10)
        
        # --- Live Results Area ---
        tk.Label(self.root, text="LIVE RESULTS", font=("Helvetica", 12, "bold")).pack(pady=10)
        
        self.results_text = tk.Text(self.root, height=10, width=45, state=tk.DISABLED, font=("Courier", 10))
        self.results_text.pack(padx=20, pady=5)
        
    def create_poll(self):
        question = self.question_entry.get().strip()
        # Only include options that are not empty strings
        options = [entry.get().strip() for entry in self.option_entries if entry.get().strip()]
        
        if not question:
            messagebox.showwarning("Input Error", "Please enter a question.")
            return
        if len(options) < 2:
            messagebox.showwarning("Input Error", "Please enter at least 2 options.")
            return
            
        request = {
            "type": "CREATE_POLL",
            "question": question,
            "options": options
        }
        
        response = self.send_request(request)
        if response:
            messagebox.showinfo("Success", "Poll created successfully!")
        else:
            messagebox.showerror("Connection Error", "Failed to connect to the server. Is it running?")
            
    def close_poll(self):
        request = {
            "type": "CLOSE_POLL"
        }
        response = self.send_request(request)
        if response:
            messagebox.showinfo("Success", "Poll closed successfully!")
            # Clear results on the screen
            self.display_results({"results": {}, "total_votes": 0})
        else:
            messagebox.showerror("Connection Error", "Failed to connect to the server. Is it running?")
            
    def update_results(self):
        """Periodically ping the server for live results."""
        request = {
            "type": "GET_RESULTS"
        }
        response = self.send_request(request)
        
        if response and response.get("type") == "RESULTS":
            self.display_results(response)
        elif response is None:
            # Server might be offline
            self.display_offline()
            
        # Refresh every 2 seconds (2000 ms)
        self.root.after(2000, self.update_results)
        
    def display_results(self, data):
        """Update the Text widget with the latest results."""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        
        results = data.get("results", {})
        total_votes = data.get("total_votes", 0)
        
        if not results:
            self.results_text.insert(tk.END, "No active poll...\n")
        else:
            for option, count in results.items():
                # Format to align numbers nicely
                self.results_text.insert(tk.END, f"{option:<25} {count}\n")
                
            self.results_text.insert(tk.END, f"\n{'-'*30}\nTotal Votes: {total_votes}")
            
        self.results_text.config(state=tk.DISABLED)
        
    def display_offline(self):
        """Display an offline message if the server cannot be reached."""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(tk.END, "Cannot connect to server...\n(Waiting for server to start)")
        self.results_text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = TeacherDashboard(root)
    root.mainloop()
