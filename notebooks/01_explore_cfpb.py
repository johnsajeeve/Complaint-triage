"""
Explore the CFPB API: understand what data looks like before we build a pipeline.

This script:
1. Calls the CFPB API with minimal parameters
2. Fetches a small sample (3 complaints)
3. Prints the raw response
4. Analyzes the structure and key fields
"""

import requests
import json
from datetime import datetime, timedelta

# The CFPB API endpoint (public, no authentication needed)
CFPB_API = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"

def fetch_sample():
    """
    Call the CFPB API and fetch a small sample.
    
    Parameters:
    - size=3 → give us 3 complaints (tiny sample for inspection)
    - has_narrative=true → only complaints where the consumer wrote a description
    - date_received_min/max → only complaints from the last 90 days (recent data)
    """
    
    # Calculate date range: last 90 days
    today = datetime.now()
    ninety_days_ago = today - timedelta(days=90)
    
    date_min = ninety_days_ago.strftime("%Y-%m-%d")
    date_max = today.strftime("%Y-%m-%d")
    
    # Build the query parameters
    params = {
        "size": 3,
        "has_narrative": "true",
        "date_received_min": date_min,
        "date_received_max": date_max,
        "sort": "date_received:asc"
    }
    
    print(f"Calling CFPB API...")
    print(f"URL: {CFPB_API}")
    print(f"Parameters: {params}\n")
    
    # Make the request
    try:
        response = requests.get(CFPB_API, params=params, timeout=30)
        response.raise_for_status()  # Raise an error if the request failed
        data = response.json()  # Parse the response as JSON
        return data
    except Exception as e:
        print(f"ERROR: {e}")
        return None

if __name__ == "__main__":
    # Fetch the data
    data = fetch_sample()
    
    if data is None:
        print("Failed to fetch data")
        exit(1)
    
    # Show the raw response (just first 100 lines to avoid overwhelming output)
    print("=" * 80)
    print("RAW API RESPONSE (formatted JSON):")
    print("=" * 80)
    response_str = json.dumps(data, indent=2)
    lines = response_str.split('\n')[:100]
    print('\n'.join(lines))
    if len(response_str.split('\n')) > 100:
        print(f"... ({len(response_str.split('\n')) - 100} more lines)")
    
    # Now let's inspect what we got
    print("\n" + "=" * 80)
    print("ANALYSIS:")
    print("=" * 80)
    
    if "hits" in data and "hits" in data["hits"]:
        total = data.get("hits", {}).get("total", {}).get("value", 0)
        fetched = len(data["hits"]["hits"])
        print(f"\nTotal complaints in database: {total:,}")
        print(f"Complaints returned in this request: {fetched}")
        
        if fetched > 0:
            first = data["hits"]["hits"][0].get("_source", {})
            
            print(f"\nFirst complaint details:")
            print(f"  Complaint ID: {first.get('complaint_id')}")
            print(f"  Date received: {first.get('date_received')}")
            print(f"  Company: {first.get('company')}")
            print(f"  Product: {first.get('product')}")
            print(f"  Issue: {first.get('issue')}")
            print(f"  State: {first.get('state')}")
            print(f"  Has narrative: {first.get('has_narrative')}")
            
            print(f"\n--- THE NARRATIVE (consumer's own words) ---")
            narrative = first.get('complaint_what_happened', '')
            if narrative:
                print(narrative[:500] + "..." if len(narrative) > 500 else narrative)
            else:
                print("(No narrative)")
            
            print(f"\n--- COMPANY RESPONSE (post-resolution, label only) ---")
            print(f"Response type: {first.get('company_response')}")
            print(f"Timely? {first.get('timely')}")
            print(f"Consumer disputed? {first.get('consumer_disputed')}")