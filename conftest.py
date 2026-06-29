import sys
import os

# Ensure project root is on the path so `from src.X import Y` works in tests
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
