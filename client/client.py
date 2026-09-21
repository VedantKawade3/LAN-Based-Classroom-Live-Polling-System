"""
client/client.py
Main entry point for the Student Application.

How to Run from the Project Root:
    python -m client.client

Description:
- Initializes the Tkinter root window.
- Instantiates the StudentGUI.
- Starts the main application event loop (mainloop).
"""

import sys
import os
import tkinter as tk

# Ensure the project root directory is in sys.path so imports work
# whether executed as 'python -m client.client' or 'python client/client.py'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from client.gui import StudentGUI


def main():
    """
    Main function to launch the Student Application GUI.
    """
    # Create the Tkinter root application window
    root = tk.Tk()

    # Instantiate the student GUI interface
    app = StudentGUI(root)

    # Start the Tkinter GUI event loop
    root.mainloop()


if __name__ == "__main__":
    main()
