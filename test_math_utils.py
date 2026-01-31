#!/usr/bin/env python3
"""Test file that will fail to demonstrate CI failure bot"""
import unittest

class TestMathUtils(unittest.TestCase):
    def test_addition(self):
        """Test basic addition - this will fail intentionally"""
        result = 2 + 2
        self.assertEqual(result, 5)  # Intentionally wrong to trigger failure

    def test_multiplication(self):
        """Test multiplication - this will also fail"""
        result = 3 * 4
        self.assertEqual(result, 13)  # Intentionally wrong

    def test_division(self):
        """Test division - this will pass"""
        result = 10 / 2
        self.assertEqual(result, 5.0)

if __name__ == "__main__":
    unittest.main()