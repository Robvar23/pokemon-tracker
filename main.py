"""Pokémon Tracker – watches Cardmarket card pages and alerts you about listings whose
seller comment mentions your keywords.

  python main.py          start tracking
  python main.py --test   send a test message to Discord / email
"""
import sys

from tracker.runner import run, test_notifications

if __name__ == "__main__":
    if "--test" in sys.argv:
        test_notifications()
    else:
        run()
