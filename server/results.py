def generate_results_message(poll_data):
    """
    Generates the standardized RESULTS JSON message from poll data.
    Calculates total_votes dynamically based on the current results.
    """
    # Handle empty or invalid data gracefully
    if not poll_data or "results" not in poll_data:
        return {
            "type": "RESULTS",
            "results": {},
            "total_votes": 0
        }
        
    results_dict = poll_data["results"]
    
    # Calculate the total votes by summing the counts of all options
    total_votes = sum(results_dict.values())
    
    return {
        "type": "RESULTS",
        "results": results_dict,
        "total_votes": total_votes
    }
