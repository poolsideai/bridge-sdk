#!/bin/bash
set -e

# Parse environment variables
REPO_URL="${REPO_URL}"
BRANCH_NAME="${BRANCH_NAME}"
COMMIT_HASH="${COMMIT_HASH:-}"
AUTH_TOKEN="${AUTH_TOKEN}"
MODULE_PATH="${MODULE_PATH:-}"

# Check if DSL_OUTPUT_FILE (or OUTPUT_FILE for backward compatibility) was explicitly provided
DSL_OUTPUT_FILE="${DSL_OUTPUT_FILE:-${OUTPUT_FILE:-}}"
if [ -z "$DSL_OUTPUT_FILE" ]; then
    # No explicit output provided, default will be used by main.py
    echo "No explicit DSL_OUTPUT_FILE or OUTPUT_FILE provided, default will be used" >&2
fi

# Validate required variables
if [ -z "$REPO_URL" ]; then
    echo "Error: REPO_URL environment variable is required" >&2
    exit 1
fi

if [ -z "$BRANCH_NAME" ]; then
    echo "Error: BRANCH_NAME environment variable is required" >&2
    exit 1
fi

if [ -z "$AUTH_TOKEN" ]; then
    echo "Error: AUTH_TOKEN environment variable is required" >&2
    exit 1
fi

# Clone directory
CLONE_DIR="/tmp/repo"

# Configure git to use the auth token
# Handle HTTPS URLs by injecting the token
if [[ "$REPO_URL" == https://* ]]; then
    # Inject token into HTTPS URL
    REPO_URL_WITH_TOKEN="${REPO_URL/https:\/\//https://${AUTH_TOKEN}@}"
elif [[ "$REPO_URL" == http://* ]]; then
    # Inject token into HTTP URL
    REPO_URL_WITH_TOKEN="${REPO_URL/http:\/\//http://${AUTH_TOKEN}@}"
else
    # SSH URL - assume SSH keys are configured or token is not needed
    export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"
    REPO_URL_WITH_TOKEN="$REPO_URL"
fi

# Clone the repository
echo "Cloning repository..." >&2
git clone "$REPO_URL_WITH_TOKEN" "$CLONE_DIR" || {
    echo "Error: Failed to clone repository" >&2
    exit 1
}

# Checkout branch and commit
cd "$CLONE_DIR"
echo "Fetching branch $BRANCH_NAME..." >&2
git fetch origin "$BRANCH_NAME" || {
    echo "Error: Failed to fetch branch $BRANCH_NAME" >&2
    exit 1
}

# Determine which commit to use
if [ -z "$COMMIT_HASH" ]; then
    # Get the latest commit on the branch
    echo "No commit hash provided, getting latest commit on branch $BRANCH_NAME..." >&2
    COMMIT_HASH=$(git rev-parse "origin/$BRANCH_NAME") || {
        echo "Error: Failed to get latest commit on branch $BRANCH_NAME" >&2
        exit 1
    }
    echo "Latest commit on branch: $COMMIT_HASH" >&2
else
    echo "Using provided commit hash: $COMMIT_HASH" >&2
fi

# Checkout the commit
echo "Checking out commit $COMMIT_HASH..." >&2
git checkout "$COMMIT_HASH" || {
    echo "Error: Failed to checkout commit $COMMIT_HASH" >&2
    exit 1
}

# Get commit hash (full) and timestamp
ACTUAL_COMMIT_HASH=$(git rev-parse HEAD)
COMMIT_TIMESTAMP=$(git show -s --format=%ct "$ACTUAL_COMMIT_HASH")

# Export commit information for Python script
export COMMIT_HASH="$ACTUAL_COMMIT_HASH"
export COMMIT_TIMESTAMP="$COMMIT_TIMESTAMP"
echo "Commit hash: $ACTUAL_COMMIT_HASH" >&2
echo "Commit timestamp: $COMMIT_TIMESTAMP" >&2

# Install dependencies from the cloned repository if pyproject.toml exists
VENV_SITE_PACKAGES=""
if [ -f "pyproject.toml" ]; then
    echo "Found pyproject.toml, installing dependencies..." >&2
    if [ -f "uv.lock" ]; then
        echo "Found uv.lock, running 'uv sync --frozen'..." >&2
        uv sync --frozen || {
            echo "Error: Failed to sync dependencies with uv.lock" >&2
            exit 1
        }
    else
        echo "No uv.lock found, running 'uv sync'..." >&2
        uv sync || {
            echo "Error: Failed to sync dependencies" >&2
            exit 1
        }
    fi
    echo "Dependencies installed successfully" >&2
    
    # Find the venv site-packages directory
    # uv creates .venv in the project directory
    if [ -d ".venv" ]; then
        # Find the site-packages directory (Python version may vary)
        # Use absolute path for PYTHONPATH
        VENV_SITE_PACKAGES=$(find "$CLONE_DIR/.venv/lib" -name "site-packages" -type d | head -n 1)
        if [ -n "$VENV_SITE_PACKAGES" ]; then
            echo "Found virtual environment at .venv" >&2
        fi
    fi
else
    echo "No pyproject.toml found, skipping dependency installation" >&2
fi

# Set up Python path
# The cloned repo should use its OWN version of bridge-sdk from its venv
# This ensures version compatibility - the discovery script will use the same version
# We need:
# 1. Cloned repo venv (if exists) - contains bridge-sdk and all dependencies - MUST BE FIRST
# 2. /tmp/repo - cloned repo source code
# 3. /app - bridge-sdk source code (fallback only, for discovery script's own imports)
# 
# By putting venv first, both the cloned repo's code AND the discovery script will
# use the cloned repo's bridge-sdk version, ensuring STEP_REGISTRY is shared correctly
if [ -n "$VENV_SITE_PACKAGES" ]; then
    # Cloned repo has venv with dependencies - use it FIRST so its bridge-sdk version takes precedence
    export PYTHONPATH="$VENV_SITE_PACKAGES:$CLONE_DIR:/app:$PYTHONPATH"
else
    # No venv - rely on system Python (cloned repo should have deps installed system-wide or in its own way)
    # Still put CLONE_DIR first so if bridge-sdk is installed system-wide, it's the one the repo expects
    export PYTHONPATH="$CLONE_DIR:/app:$PYTHONPATH"
fi

# Export CLONE_DIR so Python script can use it as default base path
export CLONE_DIR="$CLONE_DIR"

# Run the DSL generation command
echo "Generating DSL..." >&2
cd /app
# Build command arguments
CMD_ARGS=("config" "get-dsl")
if [ -n "${MODULE_PATH:-}" ]; then
    CMD_ARGS+=("--modules" "$MODULE_PATH")
fi
# Pass --output-file-path if DSL_OUTPUT_FILE is set
if [ -n "$DSL_OUTPUT_FILE" ]; then
    CMD_ARGS+=("--output-file-path" "$DSL_OUTPUT_FILE")
fi
python main.py "${CMD_ARGS[@]}"

