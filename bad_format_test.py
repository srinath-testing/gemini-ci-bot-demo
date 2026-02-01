import os,sys,json

def   badly_formatted_function(  ):
    x=1+2
    y    =    3   +   4
    z=x+y
    return z

class BadClass:
    def __init__(self,a,b):
        self.a=a
        self.b=b
    def bad_method(self):
        return self.a+self.b

if __name__=="__main__":
    obj=BadClass(1,2)
    print(obj.bad_method())