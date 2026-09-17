import os
from server.poll_manager import PollManager
from server.results import generate_results_message

def run_tests():
    print("--- Starting Backend Tests ---\n")
    
    # Ensure a clean slate for testing
    test_db = "data/test_polls.json"
    if os.path.exists(test_db):
        os.remove(test_db)
        
    pm = PollManager(data_file=test_db)
    
    # 1. Create a poll
    print("1. Creating a poll...")
    poll_id = pm.create_poll("Which language do you prefer?", ["Python", "Java", "C++"])
    print(f"   Created: {poll_id}")
    assert poll_id == "poll_1", "Poll ID should be poll_1"
    
    # 2. Start the poll
    print("\n2. Starting the poll...")
    success, msg = pm.start_poll(poll_id)
    print(f"   Result: {success} - {msg}")
    assert success == True, "Failed to start poll"
    
    # 3. Get the active poll
    print("\n3. Getting active poll...")
    active_poll = pm.get_active_poll()
    print(f"   Result: {active_poll}")
    assert active_poll["type"] == "POLL", "Active poll should be returned"
    
    # 4. Submit a valid vote
    print("\n4. Submitting a valid vote...")
    success, msg = pm.submit_vote("student_101", "Python")
    print(f"   Result: {success} - {msg}")
    assert success == True, "Valid vote should be accepted"
    
    # 5. Try voting twice with the same student ID
    print("\n5. Submitting duplicate vote...")
    success, msg = pm.submit_vote("student_101", "Java")
    print(f"   Result: {success} - {msg}")
    assert success == False, "Duplicate vote should be rejected"
    assert msg == "You have already voted"
    
    # 6. Try an invalid option
    print("\n6. Submitting invalid option...")
    success, msg = pm.submit_vote("student_102", "Ruby")
    print(f"   Result: {success} - {msg}")
    assert success == False, "Invalid option should be rejected"
    assert msg == "Invalid option"
    
    # Valid vote for another option to check counting
    pm.submit_vote("student_103", "Java")
    
    # 7. Get results
    print("\n7. Getting results...")
    poll_data = pm.data["polls"][pm.active_poll_id]
    results_msg = generate_results_message(poll_data)
    print(f"   Result: {results_msg}")
    assert results_msg["total_votes"] == 2, "Total votes should be 2"
    assert results_msg["results"]["Python"] == 1, "Python should have 1 vote"
    assert results_msg["results"]["Java"] == 1, "Java should have 1 vote"
    
    # 8. Close the poll
    print("\n8. Closing the poll...")
    success, msg = pm.close_poll()
    print(f"   Result: {success} - {msg}")
    assert success == True, "Failed to close poll"
    
    # 9. Try voting after closing the poll
    print("\n9. Voting after close...")
    success, msg = pm.submit_vote("student_104", "C++")
    print(f"   Result: {success} - {msg}")
    assert success == False, "Vote should be rejected when no active poll"
    assert msg == "No active poll"
    
    # 10. Verify data is correctly saved to JSON
    print("\n10. Verifying JSON data...")
    pm2 = PollManager(data_file=test_db)
    saved_data = pm2.data["polls"]["poll_1"]
    print(f"   Saved Status: {saved_data['status']}")
    assert saved_data["status"] == "CLOSED", "Saved status should be CLOSED"
    assert saved_data["results"]["Python"] == 1, "Saved python votes should be 1"
    
    print("\n--- All Tests Passed! ---")
    
    # Clean up test database
    if os.path.exists(test_db):
        os.remove(test_db)

if __name__ == "__main__":
    run_tests()
