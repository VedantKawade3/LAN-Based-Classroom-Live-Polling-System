import json
import os

class PollManager:
    def __init__(self, data_file="data/polls.json"):
        """
        Initializes the PollManager.
        Loads existing polls from the JSON file and prepares the state.
        """
        self.data_file = data_file
        self.data = {"polls": {}}
        self.active_poll_id = None
        self.current_voters = set() # Keeps track of who voted in the current poll
        
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
        self._load_data()

    def _load_data(self):
        """Loads poll data from the JSON file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    self.data = json.load(f)
            except json.JSONDecodeError:
                # File is corrupted or empty, start fresh
                self.data = {"polls": {}}
        else:
            self._save_data()

    def _save_data(self):
        """Saves current poll data back to the JSON file."""
        with open(self.data_file, "w") as f:
            json.dump(self.data, f, indent=4)

    def create_poll(self, question, options):
        """
        Creates a new poll, initializes votes to 0, and saves to JSON.
        Returns the new poll_id.
        """
        if not question or not options:
            return None

        # Generate a simple, unique poll ID (e.g., poll_1, poll_2)
        poll_id = f"poll_{len(self.data['polls']) + 1}"
        
        # Initialize vote counts for each option to 0
        results = {option: 0 for option in options}
        
        self.data["polls"][poll_id] = {
            "question": question,
            "options": options,
            "status": "CLOSED", # New polls start as CLOSED until started
            "results": results
        }
        
        self._save_data()
        return poll_id

    def start_poll(self, poll_id):
        """Starts a specific poll, making it ACTIVE and ready for votes."""
        if poll_id not in self.data["polls"]:
            return False, "Poll does not exist"
            
        if self.active_poll_id:
            return False, "Another poll is already active. Close it first."

        # Make the poll active
        self.active_poll_id = poll_id
        self.data["polls"][poll_id]["status"] = "ACTIVE"
        
        # Clear the voters set for the new active poll
        self.current_voters = set()
        
        self._save_data()
        return True, "Poll started successfully"

    def close_poll(self):
        """Closes the currently active poll."""
        if not self.active_poll_id:
            return False, "No active poll to close"
            
        poll_id = self.active_poll_id
        self.data["polls"][poll_id]["status"] = "CLOSED"
        
        # Clear the active poll state in memory
        self.active_poll_id = None
        self.current_voters = set()
        
        self._save_data()
        return True, "Poll closed successfully"

    def get_active_poll(self):
        """
        Returns the active poll's question and options for the client.
        If no poll is active, returns a NO_POLL JSON structure.
        """
        if not self.active_poll_id:
            return {"type": "NO_POLL"}
            
        poll_data = self.data["polls"][self.active_poll_id]
        return {
            "type": "POLL",
            "question": poll_data["question"],
            "options": poll_data["options"]
        }

    def submit_vote(self, student_id, option):
        """
        Validates and records a student's vote.
        Prevents duplicate votes using the current_voters set.
        """
        if not self.active_poll_id:
            return False, "No active poll"
            
        if student_id in self.current_voters:
            return False, "You have already voted"
            
        poll_data = self.data["polls"][self.active_poll_id]
        
        if option not in poll_data["results"]:
            return False, "Invalid option"
            
        # Record the valid vote
        poll_data["results"][option] += 1
        
        # Add student to the voters set to prevent duplicates
        self.current_voters.add(student_id)
        
        # Save to JSON to persist the new vote count
        self._save_data()
        
        return True, "Vote submitted successfully"
