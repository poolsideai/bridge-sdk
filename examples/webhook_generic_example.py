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

"""Example pipeline using a webhook endpoint for a custom monitoring service.

WebhookPipelineAction endpoints (signature verification, idempotency, secrets) are
configured in Console. The SDK declares actions that reference an endpoint
by name and define filtering/transformation logic via CEL.
"""

from pydantic import BaseModel

from bridge_sdk import Pipeline, WebhookPipelineAction


pipeline = Pipeline(
    name="alerting",
    description="Process incoming alerts from a custom monitoring service",
    webhooks=[
        # branch determines where this webhook is indexed from and which
        # version of the pipeline code runs — "staging" here means the
        # webhook is discovered when staging is indexed and events run
        # the staging version of handle_alert.
        WebhookPipelineAction(
            name="custom-alerts",
            branch="staging",
            on='payload.status == "firing" && payload.severity == "critical"',
            transform=(
                '{"handle_alert": {"alert_id": payload.alert_id,'
                ' "service": payload.service,'
                ' "message": payload.message}}'
            ),
            webhook_endpoint="monitoring_alerts",
        ),
    ],
)


class AlertInput(BaseModel):
    alert_id: str
    service: str
    message: str


class AlertResult(BaseModel):
    acknowledged: bool


@pipeline.step
def handle_alert(input_data: AlertInput) -> AlertResult:
    """Process an incoming critical alert."""
    print(f"Alert {input_data.alert_id} from {input_data.service}: {input_data.message}")
    return AlertResult(acknowledged=True)
