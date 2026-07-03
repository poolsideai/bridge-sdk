<!--
Copyright 2026 Poolside, Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Console Repository Sync Action

Sync a git-backed Console repository at a specific commit through the Poolside API, then poll until Console reports the synced repository version is ready.

Use this action when a workflow should push the current GitHub commit into one or more Console repositories after tests, publishing, or release steps finish.

## Inputs

| Name | Required | Default | Description |
| --- | --- | --- | --- |
| `repository_id` | No | `""` | Console repository ID to sync. When omitted, the action discovers repositories whose remote URL matches `https://github.com/${{ github.repository }}`. |
| `token` | Yes | N/A | Bearer token for Poolside API authentication. |
| `api_base_url` | Yes | N/A | Base URL for the Poolside API. |
| `commit_sha` | No | `${{ github.sha }}` | Git commit SHA to sync. |
| `poll_interval` | No | `5` | Seconds between status polls. |
| `poll_timeout` | No | `300` | Maximum seconds to wait for repository sync to complete. |

## Outputs

| Name | Description |
| --- | --- |
| `version_ids` | Comma-separated Console repository version IDs created or reused by the sync. |

## Usage

### Sync an explicit repository ID

```yaml
name: Sync Console repository

on:
  push:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Sync Console repository
        uses: poolsideai/bridge-sdk/action-repo-sync@main
        with:
          repository_id: ${{ vars.CONSOLE_REPOSITORY_ID }}
          token: ${{ secrets.POOLSIDE_SERVICE_ACCOUNT_TOKEN }}
          api_base_url: https://console.poolside.ai/api
```

### Auto-discover repositories from the GitHub remote

When `repository_id` is omitted, the action lists Console repositories and syncs every repository whose remote URL matches the current GitHub repository. It tolerates `https://github.com/org/repo`, `https://github.com/org/repo.git`, and `git@github.com:org/repo.git` forms.

```yaml
name: Sync Console repositories

on:
  push:
    branches: [main]

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Sync all matching Console repositories
        uses: poolsideai/bridge-sdk/action-repo-sync@main
        with:
          token: ${{ secrets.POOLSIDE_SERVICE_ACCOUNT_TOKEN }}
          api_base_url: https://console.poolside.ai/api
          poll_interval: 10
          poll_timeout: 600
```

## Token provisioning

Create a Poolside service account token for CI and grant it the Data Source Admin role through the relevant team in Console. Store the token as a GitHub Actions secret, then pass it through the `token` input. The action masks the token before making API calls.

## Troubleshooting

### `401` or `403` responses

The token is missing, expired, scoped to the wrong Console environment, or the service account does not have the required team role. Verify the secret value and grant the service account the Data Source Admin role through the team that owns the repository.

### `404` responses

The `repository_id` may point to a repository that does not exist in the target Console environment, or `api_base_url` may be pointed at the wrong environment. If using auto-discovery, confirm the repository is registered as a git-backed Console repository.

### Repository version enters `error`

Console accepted the sync request but failed while processing the repository version. The action prints the API-provided error message from `latest_version_info.error`; fix the underlying repository or Console configuration issue, then rerun the workflow.

### Sync is superseded

If another sync starts for the same Console repository while this action is polling, the action logs `superseded by newer sync` and treats the current run as successful. Check the newer workflow run or Console repository version for the final state.
