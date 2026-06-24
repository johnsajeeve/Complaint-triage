"""
Fetch complaints from CFPB API and store in Postgres.

This script:
1. Calls the CFPB API with pagination (100 records at a time)
2. Maps CFPB fields to our database schema
3. Inserts them into the complaints table
4. Handles errors and logs progress

IMPORTANT: The CFPB API returns data in this structure:
  data["hits"]["hits"][0]["_source"] = actual complaint record
"""

import os
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from app.database import SessionLocal
from app.models.schema import Complaint

load_dotenv()

# CFPB API endpoint (no authentication needed)
CFPB_API_BASE = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"


def fetch_cfpb_page(date_min: str, date_max: str, frm: int = 0, size: int = 100) -> dict:
    """
    Fetch one page of complaints from the CFPB API.
    
    The API uses Elasticsearch under the hood, so the response structure is:
    {
      "hits": {
        "total": {"value": 15994772},
        "hits": [
          {"_source": {actual complaint data}},
          {"_source": {actual complaint data}},
          ...
        ]
      }
    }
    
    Args:
        date_min: string like "2024-01-01"
        date_max: string like "2024-03-31"
        frm: offset for pagination (0, 100, 200, etc.)
        size: number of records per page (usually 100)
    
    Returns:
        dict with the raw API response, or None if failed
    
    Raises:
        requests.RequestException if the API call fails
    """
    
    params = {
        "date_received_min": date_min,
        "date_received_max": date_max,
        "has_narrative": "true",  # Only complaints with consumer narratives
        "size": size,
        "from": frm,  # Note: API uses "from", not "frm"
        "sort": "date_received:asc"  # Oldest first
    }
    
    try:
        print(f"  Fetching records {frm} to {frm + size}...", end=" ", flush=True)
        
        response = requests.get(CFPB_API_BASE, params=params, timeout=30)
        response.raise_for_status()  # Raise an error if status code is 4xx or 5xx
        
        data = response.json()
        return data
    
    except requests.exceptions.Timeout:
        print(f"✗ TIMEOUT")
        return None
    except requests.exceptions.RequestException as e:
        print(f"✗ ERROR: {e}")
        return None


def store_complaints(raw_complaints: list, db: Session) -> int:
    """
    Store raw complaint records in the database.
    
    Takes the raw JSON from CFPB API and:
    1. Maps CFPB field names to our database schema
    2. Creates Complaint objects
    3. Uses .merge() to insert-or-update (upsert)
    4. Commits all at once (batch = efficient)
    
    Key field mappings:
    - CFPB "timely" (string "Yes"/"No") → our "timely_response" (boolean)
    - CFPB "complaint_what_happened" (may be empty) → check has_narrative first
    - CFPB nested in _source → we extract it before calling this function
    
    Args:
        raw_complaints: list of dicts from CFPB API _source fields
        db: SQLAlchemy session
    
    Returns:
        Number of records inserted
    """
    
    stored = 0
    
    for raw in raw_complaints:
        try:
            # Skip if no narrative (we only want complaints with text)
            if not raw.get("has_narrative", False):
                continue
            
            # Extract the narrative text and strip whitespace
            narrative = raw.get("complaint_what_happened", "").strip()
            if not narrative:
                continue
            
            # Map CFPB field names to our Complaint schema
            complaint = Complaint(
                complaint_id=raw.get("complaint_id"),
                date_received=raw.get("date_received"),  # ISO format, will be parsed
                date_sent_to_company=raw.get("date_sent_to_company"),
                product=raw.get("product"),
                sub_product=raw.get("sub_product"),
                issue=raw.get("issue"),
                sub_issue=raw.get("sub_issue"),
                company=raw.get("company"),
                state=raw.get("state"),
                zip_code=raw.get("zip_code"),
                complaint_what_happened=narrative,
                tags=raw.get("tags"),
                submitted_via=raw.get("submitted_via"),
                company_response=raw.get("company_response"),
                # Convert "Yes"/"No" string from API to boolean
                timely_response=raw.get("timely") == "Yes",
                consumer_disputed=raw.get("consumer_disputed") == True,
                company_public_response=raw.get("company_public_response"),
                narrative_available=True,  # We already filtered for this above
            )
            
            # .merge() = insert if new, update if exists (upsert)
            db.merge(complaint)
            stored += 1
        
        except Exception as e:
            print(f"  ✗ ERROR storing complaint {raw.get('complaint_id')}: {e}")
            continue
    
    # Commit all records at once (much faster than one-by-one commits)
    db.commit()
    return stored


def ingest_date_range(date_min: str, date_max: str, limit_pages: int = None) -> int:
    """
    Ingest all complaints in a date range.
    
    This is the main function. It:
    1. Loops through pages (0-100, 100-200, etc.)
    2. Calls fetch_cfpb_page() for each page
    3. Extracts complaints from the nested API response
    4. Calls store_complaints() for each batch
    5. Keeps going until the API returns no more records
    
    Args:
        date_min: "YYYY-MM-DD"
        date_max: "YYYY-MM-DD"
        limit_pages: for testing, stop after N pages. None = fetch all.
    
    Returns:
        Total number of records ingested
    """
    
    db = SessionLocal()
    
    try:
        print(f"\n{'='*80}")
        print(f"CFPB Data Ingestion: {date_min} to {date_max}")
        print(f"{'='*80}\n")
        
        total_inserted = 0
        page = 0
        page_size = 100
        
        while True:
            # For testing, stop after N pages
            if limit_pages and page >= limit_pages:
                print(f"\n(Stopping after {limit_pages} pages as requested)")
                break
            
            # Calculate offset for this page
            frm = page * page_size
            
            print(f"Page {page + 1} (records {frm}-{frm + page_size - 1})...", end=" ", flush=True)
            
            # Fetch this page from CFPB
            data = fetch_cfpb_page(date_min, date_max, frm=frm, size=page_size)
            
            # Check if the API call succeeded
            if data is None:
                print("✗ API failed, stopping")
                break
            
            # CRITICAL: Extract complaints from nested structure
            # API returns: data["hits"]["hits"][0]["_source"] = actual complaint
            try:
                hits = data.get("hits", {}).get("hits", [])
            except:
                print("✗ Could not parse API response structure")
                break
            
            if not hits:
                print(f"✓ No more records (end of data)")
                break
            
            # Extract the _source field from each hit (that's where the actual data is)
            raw_complaints = [hit.get("_source", {}) for hit in hits]
            
            # Store this batch
            stored = store_complaints(raw_complaints, db)
            total_inserted += stored
            
            print(f"✓ Stored {stored} records (total: {total_inserted})")
            
            page += 1
        
        print(f"\n{'='*80}")
        print(f"✓ Ingestion complete: {total_inserted} total records")
        print(f"{'='*80}\n")
        
        return total_inserted
    
    except Exception as e:
        print(f"\n✗ ERROR during ingestion: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    """
    If you run this file directly (python app/ingestion/fetch_and_store.py),
    it will ingest data from the CFPB API.
    
    For testing: fetches data from the last 90 days, limits to 3 pages (~250-300 records)
    Once you verify it works, set limit_pages=None to fetch more data
    """
    
    # For testing: fetch data from the last 90 days
    today = datetime.now()
    ninety_days_ago = today - timedelta(days=90)
    
    date_min = ninety_days_ago.strftime("%Y-%m-%d")
    date_max = today.strftime("%Y-%m-%d")
    
    # For testing, limit to 3 pages (~300 records)
    # Once you verify it works, set limit_pages=None to fetch all
    ingest_date_range(date_min, date_max, limit_pages=3)