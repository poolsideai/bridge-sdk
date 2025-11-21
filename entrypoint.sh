#!/bin/bash
set -e

# Default output file path (can be overridden with OUTPUT_FILE env var)
export OUTPUT_FILE="${OUTPUT_FILE:-/tmp/step_result.json}"

# Execute the main script with all passed arguments
exec uv run python main.py "$@"

