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

"""Example pipeline using a generic HMAC webhook provider.

Generic providers (generic_hmac_sha1, generic_hmac_sha256) work with any
service that signs requests with an HMAC. Unlike named providers (github,
linear, etc.), generic providers require an idempotency_key expression so
Bridge can deduplicate deliveries.
"""

from pydantic import BaseModel

from bridge_sdk import Pipeline, Webhook, WebhookProvider


pipeline = Pipeline(
    name="alerting",
    description="Process incoming alerts from a custom monitoring service",
    webhooks=[
        # branch selects which git branch's pipeline code to run when the
        # webhook fires — "staging" here means alerts are processed by the
        # staging version of handle_alert, not the production one.
        Webhook(
            branch="staging",
            filter='payload.status == "firing" && payload.severity == "critical"',
            idempotency_key='payload.alert_id + "/" + payload.timestamp',
            name="custom-alerts",
            provider=WebhookProvider.GENERIC_HMAC_SHA256,
            transform=(
                '{"handle_alert": {"alert_id": payload.alert_id,'
                ' "service": payload.service,'
                ' "message": payload.message}}'
            ),
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
