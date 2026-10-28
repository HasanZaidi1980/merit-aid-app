"""Put the backend root on sys.path so tests can `from app import ...`.

pytest adds this file's directory to sys.path under the default import mode, but
doing it explicitly keeps `pytest` working from the repo root as well as from here.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
