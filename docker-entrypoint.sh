#!/bin/bash
set -e

# Parse environment variables
REPO_URL="${REPO_URL}"
COMMIT_HASH="${COMMIT_HASH}"
AUTH_TOKEN="${AUTH_TOKEN}"
MODULE_PATH="${MODULE_PATH:-}"

# Validate required variables
if [ -z "$REPO_URL" ]; then
    echo "Error: REPO_URL environment variable is required" >&2
    exit 1
fi

if [ -z "$COMMIT_HASH" ]; then
    echo "Error: COMMIT_HASH environment variable is required" >&2
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

# Checkout specific commit
cd "$CLONE_DIR"
echo "Checking out commit $COMMIT_HASH..." >&2
git checkout "$COMMIT_HASH" || {
    echo "Error: Failed to checkout commit $COMMIT_HASH" >&2
    exit 1
}

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

# Add both the bridge-sdk (/app) and cloned repo to Python path
# /app must be first so the bridge-sdk's lib module can be imported by cloned repo code
# /tmp/repo must be included so we can import the module from the cloned repo
# Add venv site-packages if it exists so dependencies are available
if [ -n "$VENV_SITE_PACKAGES" ]; then
    export PYTHONPATH="/app:$CLONE_DIR:$VENV_SITE_PACKAGES:$PYTHONPATH"
else
    export PYTHONPATH="/app:$CLONE_DIR:$PYTHONPATH"
fi

# Export CLONE_DIR so Python script can use it as default base path
export CLONE_DIR="$CLONE_DIR"

# Run the DSL generation command
echo "Generating DSL..." >&2
cd /app
if [ -n "$MODULE_PATH" ]; then
    # Discover steps from a specific module
    python main.py config get-dsl --module "$MODULE_PATH"
else
    # Discover all steps from the cloned repository
    python main.py config get-dsl --base-path "$CLONE_DIR"
fi

