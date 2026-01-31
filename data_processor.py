#!/usr/bin/env python3
"""Data processing utilities with intentional import errors for testing CI bot"""

# INTENTIONAL IMPORT ERRORS FOR TESTING
import nonexistent_package  # This package doesn't exist
import pandas_typo as pd  # Should be 'pandas'
from sklearn.nonexistent import FakeModel  # This module doesn't exist in sklearn
import requests_oauthlib  # This package is not installed

import os
import sys

def process_data(data):
    """Process data using imported libraries - will fail due to import errors"""
    # This will fail because of the import errors above
    result = nonexistent_package.process(data)
    df = pd.DataFrame(result)  # pandas_typo will cause NameError
    
    model = FakeModel()  # sklearn.nonexistent doesn't exist
    predictions = model.predict(df)
    
    # Use requests_oauthlib (not installed)
    auth = requests_oauthlib.OAuth1Session()
    
    return predictions

def validate_input(data):
    """Validate input data"""
    if not data:
        raise ValueError("Data cannot be empty")
    return True

if __name__ == "__main__":
    print("Processing data...")
    sample_data = [1, 2, 3, 4, 5]
    result = process_data(sample_data)
    print(f"Result: {result}")