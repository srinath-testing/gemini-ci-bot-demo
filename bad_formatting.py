def bad_function():
     print(  "This has terrible formatting"  )
    x=1+2+3+4+5+6+7+8+9+10+11+12+13+14+15+16+17+18+19+20+21+22+23+24+25+26+27+28+29+30
    return x

class BadClass:
  def __init__(self):
      self.value=42

  def method(self):
        return "bad indentation"

def another_bad_function( ):
    if True:
     print("inconsistent indentation")
    else:
      print( "more spacing issues" )# Test comment
# Trigger workflow failure