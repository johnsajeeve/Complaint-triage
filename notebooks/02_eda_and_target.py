"""
EDA: Exploratory Data Analysis of CFPB complaints.

Goal: Understand the data before building models.
We'll look at:
1. Basic statistics (how many complaints, date ranges, etc.)
2. Target variable distributions (company_response, timely_response)
3. Data quality issues (missing values, outliers)
4. Temporal patterns (do complaints differ by time?)
5. Construct the Resolution Difficulty Score (our regression target)
"""

import pandas as pd
from datetime import datetime
from app.database import SessionLocal
from app.models.schema import Complaint

def run_eda():
    """Load data from Postgres and analyze it."""
    
    db = SessionLocal()
    
    # Fetch all complaints from database into a pandas DataFrame
    # In a real project with millions of records, you'd do this more efficiently,
    # but for EDA this is fine
    query = db.query(Complaint).all()
    complaints = pd.DataFrame([
        {
            'complaint_id': c.complaint_id,
            'date_received': c.date_received,
            'date_sent_to_company': c.date_sent_to_company,
            'product': c.product,
            'issue': c.issue,
            'company': c.company,
            'state': c.state,
            'narrative_length': len(c.complaint_what_happened.split()) if c.complaint_what_happened else 0,
            'company_response': c.company_response,
            'timely_response': c.timely_response,
            'consumer_disputed': c.consumer_disputed,
        }
        for c in query
    ])
    
    db.close()
    
    print("\n" + "="*80)
    print("EXPLORATORY DATA ANALYSIS")
    print("="*80)
    
    # ===== BASIC STATISTICS =====
    print(f"\n--- DATASET SIZE ---")
    print(f"Total complaints: {len(complaints):,}")
    print(f"Date range: {complaints['date_received'].min()} to {complaints['date_received'].max()}")
    print(f"Time span: {(complaints['date_received'].max() - complaints['date_received'].min()).days} days")
    
    # ===== CATEGORICAL DISTRIBUTIONS =====
    print(f"\n--- PRODUCTS ---")
    print(f"Unique products: {complaints['product'].nunique()}")
    print(f"Top 5 products:")
    print(complaints['product'].value_counts().head())
    
    print(f"\n--- COMPANIES ---")
    print(f"Unique companies: {complaints['company'].nunique()}")
    print(f"Top 5 companies:")
    print(complaints['company'].value_counts().head())
    
    # ===== TARGET VARIABLE ANALYSIS =====
    print(f"\n--- TARGET VARIABLES (what we're predicting) ---")
    
    print(f"\nCompany Response Distribution:")
    print(complaints['company_response'].value_counts(dropna=False))
    print(f"Proportion:")
    print(complaints['company_response'].value_counts(normalize=True, dropna=False))
    
    print(f"\nTimely Response Distribution:")
    timely_yes = complaints['timely_response'].sum()
    timely_no = (~complaints['timely_response']).sum()
    timely_unknown = complaints['timely_response'].isna().sum()
    print(f"  On time: {timely_yes} ({100*timely_yes/len(complaints):.1f}%)")
    print(f"  Late: {timely_no} ({100*timely_no/len(complaints):.1f}%)")
    print(f"  Unknown: {timely_unknown}")
    
    print(f"\nConsumer Disputed Distribution:")
    disputed_yes = complaints['consumer_disputed'].sum()
    disputed_no = (~complaints['consumer_disputed']).sum()
    disputed_unknown = complaints['consumer_disputed'].isna().sum()
    print(f"  Not disputed: {disputed_no} ({100*disputed_no/len(complaints):.1f}%)")
    print(f"  Disputed: {disputed_yes} ({100*disputed_yes/len(complaints):.1f}%)")
    print(f"  Unknown: {disputed_unknown}")
    
    # ===== MISSING VALUES =====
    print(f"\n--- MISSING VALUES (data quality check) ---")
    missing = complaints.isnull().sum()
    missing_pct = 100 * missing / len(complaints)
    has_missing = False
    for col in missing[missing > 0].index:
        print(f"  {col}: {missing[col]} ({missing_pct[col]:.1f}%)")
        has_missing = True
    if not has_missing:
        print("  None! Data is clean.")
    
    # ===== NARRATIVE TEXT ANALYSIS =====
    print(f"\n--- NARRATIVE TEXT ANALYSIS ---")
    print(f"Narrative length statistics (words):")
    print(f"  Mean: {complaints['narrative_length'].mean():.0f}")
    print(f"  Median: {complaints['narrative_length'].median():.0f}")
    print(f"  Min: {complaints['narrative_length'].min()}")
    print(f"  Max: {complaints['narrative_length'].max()}")
    print(f"  Std Dev: {complaints['narrative_length'].std():.0f}")
    
    # ===== TEMPORAL PATTERNS =====
    print(f"\n--- TEMPORAL PATTERNS ---")
    complaints['month'] = pd.to_datetime(complaints['date_received']).dt.to_period('M')
    complaints_per_month = complaints.groupby('month').size()
    print(f"Complaints per month:")
    print(complaints_per_month)
    
    # ===== STATE DISTRIBUTION =====
    print(f"\n--- GEOGRAPHIC DISTRIBUTION ---")
    print(f"Unique states: {complaints['state'].nunique()}")
    print(f"Top 10 states:")
    print(complaints['state'].value_counts().head(10))
    
    return complaints


def construct_resolution_difficulty_score(complaints_df):
    """
    Construct the regression target: Resolution Difficulty Score.
    
    This is the MOST IMPORTANT PART. We're transparent about how we build this.
    
    Formula:
    - Start at 0 (easy case)
    - Add points for company_response type (0-50 points)
    - Add points for timeliness (0-30 points)
    - Add points for consumer dispute (0-20 points)
    - Total range: 0-100
    
    Reasoning:
    - "Closed with monetary relief" = company solved it → low difficulty (0)
    - "Closed with explanation" = company explained but didn't help → medium (40)
    - "In progress" / "Untimely" = unresolved → high difficulty (50-100)
    - Consumer disputed = company response wasn't satisfactory → add 20
    - Late response = harder problem → add 30
    
    This is transparent and defensible, unlike just using company_response directly.
    """
    
    scores = []
    
    for idx, row in complaints_df.iterrows():
        score = 0
        
        # COMPONENT 1: Company Response Type (0-50 points)
        response = row['company_response']
        if response == 'Closed with monetary relief':
            response_score = 0  # Best outcome
        elif response == 'Closed with non-monetary relief':
            response_score = 20
        elif response == 'Closed with explanation':
            response_score = 40
        else:  # In progress, untimely, etc.
            response_score = 50  # Worst outcome
        
        score += response_score
        
        # COMPONENT 2: Timeliness (0-30 points)
        if row['timely_response'] == True:
            timeliness_score = 0  # On time
        elif row['timely_response'] == False:
            timeliness_score = 30  # Late
        else:
            timeliness_score = 15  # Unknown, assume middle
        
        score += timeliness_score
        
        # COMPONENT 3: Consumer Dispute (0-20 points)
        if row['consumer_disputed'] == True:
            dispute_score = 20  # Consumer didn't accept it
        elif row['consumer_disputed'] == False:
            dispute_score = 0  # Consumer was satisfied
        else:
            dispute_score = 10  # Unknown, assume middle
        
        score += dispute_score
        
        scores.append(score)
    
    complaints_df['difficulty_score'] = scores
    
    # Analyze the constructed target
    print(f"\n" + "="*80)
    print("RESOLUTION DIFFICULTY SCORE DISTRIBUTION")
    print("="*80)
    print(f"\nStatistics (0-100 scale, higher = harder to resolve):")
    print(f"  Mean: {complaints_df['difficulty_score'].mean():.1f}")
    print(f"  Median: {complaints_df['difficulty_score'].median():.1f}")
    print(f"  Std Dev: {complaints_df['difficulty_score'].std():.1f}")
    print(f"  Min: {complaints_df['difficulty_score'].min()}")
    print(f"  Max: {complaints_df['difficulty_score'].max()}")
    
    print(f"\nValue counts:")
    print(complaints_df['difficulty_score'].value_counts().sort_index())
    
    return complaints_df


if __name__ == "__main__":
    # Run EDA
    complaints = run_eda()
    
    # Construct and analyze target
    complaints = construct_resolution_difficulty_score(complaints)
    
    # Save for next step
    complaints.to_csv('data/complaints_with_target.csv', index=False)
    print(f"\n✓ Saved to data/complaints_with_target.csv")