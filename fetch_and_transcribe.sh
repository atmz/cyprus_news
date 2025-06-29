#!/bin/bash

# Set full path for cron/launchd
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

# Activate the virtualenv
source /Users/alext/news2025/venv/bin/activate

# Change to working directory (just in case)
cd /Users/alext/news2025/
# Usage: ./fetch_and_transcribe.sh [optional DDMMYY]
# Example: ./fetch_and_transcribe.sh 250625

set -e

python src/main.py