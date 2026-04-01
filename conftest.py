"""pytest configuration – ensures the project root is on sys.path so that
test modules can import scraper, analyzer, and main without installing the
package first."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
