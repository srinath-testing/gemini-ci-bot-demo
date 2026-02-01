#!/usr/bin/env python3
"""Test file to trigger OpenWISP QA workflow recommendations - UPDATED"""

# Intentionally bad formatting to trigger QA failures
def   badly_formatted_function_v2(  ):
    x=1+2+3
    y    =    4   +   5   +   6
    return x,y

class BadlyFormattedClass:
    def __init__(self,param1,param2,param3):
        self.param1=param1
        self.param2=param2
        self.param3=param3
    def method_with_bad_spacing_v2(self):
        result=self.param1+self.param2+self.param3
        return result

if __name__=="__main__":
    obj=BadlyFormattedClass(1,2,3)
    print("Result:",obj.method_with_bad_spacing_v2())