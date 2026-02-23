# Copyright 2026 Poolside, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Example pipeline triggered by webhooks.

This module shows how to:
1. Define webhooks on a Pipeline to trigger it from external events
2. Use CEL filter expressions to match specific webhook payloads
3. Use CEL transform expressions to extract step inputs from payloads
4. Handle multiple webhook providers on the same pipeline
"""

from typing import Annotated

from pydantic import BaseModel

from bridge_sdk import Pipeline, Webhook, WebhookProvider, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient


# =============================================================================
# Pipeline Definition with Webhooks
# =============================================================================
# Webhooks are declared at pipeline creation time. They are discovered during
# indexing and start disabled — the user configures a signing secret and
# enables the webhook via the API or UI.
#
# Each webhook has:
#   - filter:    CEL expression returning bool (should this event trigger?)
#   - transform: CEL expression returning map(string, dyn) keyed by step name
#                (what inputs should each step receive?)
#
# CEL expressions can reference:
#   - payload: the parsed JSON body of the webhook request
#   - headers: HTTP headers as map(string, string)

pipeline = Pipeline(
    name="issue_triage",
    description="Triage incoming issues from Linear and GitHub",
    webhooks=[
        # Linear: trigger when an issue is created with the "autofix" label.
        # branch determines which version of the pipeline code runs — here
        # we use "main" so webhooks fire against the mainline pipeline.
        Webhook(
            branch="main",
            filter=(
                'payload.type == "Issue"'
                ' && payload.action == "create"'
                ' && payload.data.labels.exists(l, l.name == "autofix")'
            ),
            name="linear-autofix",
            provider=WebhookProvider.LINEAR,
            transform=(
                '{"fetch_issue": {"issue_id": payload.data.id, "title": payload.data.title}}'
            ),
        ),
        # GitHub: trigger on pull request opened against main.
        # Using a different branch ("production") means this webhook uses
        # the pipeline code from the production branch, which is useful for
        # deploying stable vs. development versions of the same pipeline.
        Webhook(
            branch="production",
            filter=(
                'headers["x-github-event"] == "pull_request"'
                ' && payload.action == "opened"'
                ' && payload.pull_request.base.ref == "main"'
            ),
            name="github-pr-opened",
            provider=WebhookProvider.GITHUB,
            transform=(
                '{"fetch_issue": {"issue_id": payload.pull_request.head.sha,'
                ' "title": payload.pull_request.title}}'
            ),
        ),
    ],
)


# =============================================================================
# Models
# =============================================================================


class FetchIssueInput(BaseModel):
    issue_id: str
    title: str


class IssueDetails(BaseModel):
    issue_id: str
    title: str
    description: str


class TriageResult(BaseModel):
    session_id: str
    priority: str


# =============================================================================
# Steps
# =============================================================================
# The transform expressions above map webhook payloads into step inputs.
# For example, the Linear webhook maps payload.data.id → fetch_issue.issue_id.


@pipeline.step
def fetch_issue(input_data: FetchIssueInput) -> IssueDetails:
    """Fetch full issue details from the source system."""
    return IssueDetails(
        issue_id=input_data.issue_id,
        title=input_data.title,
        description="(fetched from API)",
    )


@pipeline.step(metadata={"type": "agent"})
def triage_issue(
    issue: Annotated[IssueDetails, step_result(fetch_issue)],
) -> TriageResult:
    """Use an agent to triage the issue and assign priority."""
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent(
            prompt=(
                f"Triage the following issue and respond with a priority "
                f"(critical/high/medium/low).\n\n"
                f"Title: {issue.title}\n"
                f"Description: {issue.description}"
            ),
            agent_name="Malibu",
        )
        return TriageResult(session_id=session_id, priority=res)
