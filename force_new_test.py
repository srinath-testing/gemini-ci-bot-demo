#!/usr/bin/env python3
# This file has intentional formatting issues to trigger the NEW bot response

import os,sys # Bad import formatting
import json,requests # More bad imports

def test_function(a,b,c): # Missing spaces
    # This line is intentionally very long to exceed the maximum line length limit and trigger flake8 errors that should be caught by the OpenWISP QA tools
    result=a+b+c # No spaces around operators
    return result

# Missing final newline