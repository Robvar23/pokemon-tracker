#!/bin/bash
# Sends a test message to Discord / email using config.json.
cd "$(dirname "$0")"
./run-mac.command --test
read -r -p "Press Enter to close..."
