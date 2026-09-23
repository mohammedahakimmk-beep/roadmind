#!/bin/bash
# Launch RoadMind (dev). Make sure .venv has RoadMind installed: see README.
cd "$(dirname "$0")"
exec .venv/bin/python -m roadmind "$@"