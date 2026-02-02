# Final verification test - mixed formatting and import issues
import nonexistent_module
import os,sys

def broken_function( ):
    x=1+2
    y   =   3+4
    return x+y

class BadClass:
    def __init__(self,name):
        self.name=name
    
    def method_with_issues( self ):
        result=self.name+"test"
        return result