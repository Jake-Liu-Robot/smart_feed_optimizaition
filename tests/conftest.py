"""
Pytest configuration: add project root to sys.path
so 'from smart_feed_v9.xxx import ...' works.
"""
import sys
import os

# Project root (code/)
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)
