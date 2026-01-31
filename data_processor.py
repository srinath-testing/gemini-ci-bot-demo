#!/usr/bin/env python3
"""Data processing utilities with intentional import errors"""

# These imports will fail - demonstrating import error analysis
import nonexistent_package  # This package doesn't exist
import pandas_typo as pd  # Typo in pandas import
from sklearn.nonexistent import FakeModel  # Non-existent sklearn module
import requests_oauthlib  # Package not installed in CI

def process_data(data):
    """Process data using various libraries"""
    # This will fail due to import errors above
    df = pd.DataFrame(data)
    model = FakeModel()
    
    # Use nonexistent package
    result = nonexistent_package.process(df)
    
    return result

def fetch_authenticated_data(url):
    """Fetch data with OAuth - will fail due to missing dependency"""
    auth = requests_oauthlib.OAuth1Session()
    response = auth.get(url)
    return response.json()

if __name__ == "__main__":
    # This will trigger import errors
    sample_data = [1, 2, 3, 4, 5]
    processed = process_data(sample_data)
    print(f"Processed: {processed}")