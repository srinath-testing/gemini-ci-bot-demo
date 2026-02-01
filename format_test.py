#!/usr/bin/env python3
"""Test file with intentional formatting violations to trigger CI failure bot"""

import os,sys,json
def bad_function( x,y ):
    result=x+y
    if result>10:
        print("big number")
    else:
        print( "small number" )
    return result

class BadClass:
    def __init__(self,name):
        self.name=name
    def method(self ):
        return f"Hello {self.name}"

# Intentional style violations:
# - Missing spaces around operators
# - Inconsistent spacing in function calls
# - Multiple imports on one line
# - Missing spaces after commas