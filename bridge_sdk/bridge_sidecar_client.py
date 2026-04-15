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

"""Compatibility shim for the legacy sidecar client module name."""

import warnings

from bridge_sdk.bridge_execution_client import (
    BridgeExecutionClient,
    BridgeSidecarClient,
)

warnings.warn(
    "bridge_sdk.bridge_sidecar_client is deprecated; use bridge_sdk.bridge_execution_client",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["BridgeExecutionClient", "BridgeSidecarClient"]
