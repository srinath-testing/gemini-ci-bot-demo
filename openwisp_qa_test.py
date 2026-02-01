#!/usr/bin/env python3
"""Test file to trigger OpenWISP QA workflow recommendations"""

# Intentionally bad formatting to trigger QA failures
def   badly_formatted_function(  ):
    x=1+2
    y    =    3   +   4
    return x,y

class BadlyFormattedClass:
    def __init__(self,param1,param2):
        self.param1=param1
        self.param2=param2
    def method_with_bad_spacing(self):
        result=self.param1+self.param2
        return result

if __name__=="__main__":
    obj=BadlyFormattedClass(1,2)
    print(obj.method_with_bad_spacing())