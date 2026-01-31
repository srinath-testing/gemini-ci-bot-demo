#!/usr/bin/env python3
"""Test file with intentional QA violations to trigger OpenWISP QA bot response"""

import os,sys,json # Bad import formatting - should be separate lines
import requests # Unused import

def badly_formatted_function(x,y,z): # Missing spaces around commas
    # Line too long - this comment is intentionally very long to exceed the maximum line length limit set by flake8 which should trigger a formatting error
    result=x+y+z # Missing spaces around operators
    return result

class   BadlyFormattedClass: # Extra spaces
    def __init__(self):
        pass
    
    def method_with_issues(self):
        data={'key':'value','another_key':'another_value'} # Missing spaces in dict
        return data

# Missing blank line at end of file