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

"""Client for Bridge agent execution transports."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

import grpc
from typing import Any, Optional

from bridge_sdk.models import ContentPartInput, to_proto_content_part
from bridge_sdk.proto import bridge_sidecar_pb2, bridge_sidecar_pb2_grpc

_DEFAULT_AGENT_NAME = "agent_1003_cc_v2_rc-fp8-tpr"
_TRANSPORT_ENV_VAR = "BRIDGE_SDK_AGENT_TRANSPORT"
_API_BASE_URL_ENV_VAR = "BRIDGE_SDK_API_BASE_URL"
_API_TOKEN_ENV_VAR = "BRIDGE_SDK_API_TOKEN"
_SANDBOX_ID_ENV_VAR = "BRIDGE_SDK_SANDBOX_ID"
_SANDBOX_DEFINITION_ID_ENV_VAR = "BRIDGE_SDK_SANDBOX_DEFINITION_ID"
_SESSIONS_ASYNC_ENV_VAR = "BRIDGE_SDK_SESSIONS_ASYNC"
_SESSIONS_WAIT_TIMEOUT_SECONDS_ENV_VAR = "BRIDGE_SDK_SESSIONS_WAIT_TIMEOUT_SECONDS"
_SESSIONS_POLL_INTERVAL_SECONDS_ENV_VAR = "BRIDGE_SDK_SESSIONS_POLL_INTERVAL_SECONDS"
_STEP_RUNTIME_TRANSPORT_ENV_VAR = "BRIDGE_EXECUTION_TRANSPORT"
_STEP_RUNTIME_API_BASE_URL_ENV_VAR = "BRIDGE_EXECUTION_API_BASE_URL"
_STEP_RUNTIME_API_TOKEN_ENV_VAR = "BRIDGE_EXECUTION_API_TOKEN"
_STEP_RUNTIME_SANDBOX_ID_ENV_VAR = "BRIDGE_EXECUTION_SANDBOX_ID"
_TERMINAL_SESSION_STATES = {"finished", "failed", "cancelled", "canceled", "invalid"}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as err:
        raise ValueError(f"{name} must be a number, got {raw!r}") from err



class BridgeExecutionClient:
    """Client for starting agent execution via configured transport."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 50052,
        *,
        agent_transport: Optional[str] = None,
        api_base_url: Optional[str] = None,
        api_token: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        sandbox_definition_id: Optional[str] = None,
        sessions_async: Optional[bool] = None,
        sessions_wait_timeout_seconds: Optional[float] = None,
        sessions_poll_interval_seconds: Optional[float] = None,
    ):
        """
        Initialize the Bridge client.

        Args:
            host: The hostname of the Bridge service
            port: The port of the Bridge service
            agent_transport: Agent transport backend. Allowed values are
                "sidecar" (default) and "sessions".
            api_base_url: Core API base URL for sessions transport.
            api_token: Core API bearer token for sessions transport.
            sandbox_id: Existing sandbox ID for sessions transport.
            sandbox_definition_id: Sandbox definition ID for sessions transport.
            sessions_async: When true, sessions transport returns immediately after
                session scheduling. When false, waits for the session to reach a
                terminal state before returning.
            sessions_wait_timeout_seconds: Max seconds to wait for terminal state
                when sessions_async is false.
            sessions_poll_interval_seconds: Poll interval, in seconds, for terminal
                state checks when sessions_async is false.
        """
        self.address = f"{host}:{port}"
        self.channel: Optional[grpc.Channel] = None
        self.stub: Optional[bridge_sidecar_pb2_grpc.BridgeSidecarServiceStub] = None
        self.agent_transport = (
            (agent_transport or os.getenv(_TRANSPORT_ENV_VAR, "sidecar"))
            .strip()
            .lower()
        )
        if self.agent_transport not in ("sidecar", "sessions"):
            raise ValueError(
                f"invalid agent transport {self.agent_transport!r}; expected 'sidecar' or 'sessions'"
            )
        self.api_base_url = (
            (api_base_url or os.getenv(_API_BASE_URL_ENV_VAR, "")).strip()
        )
        self.api_token = (api_token or os.getenv(_API_TOKEN_ENV_VAR, "")).strip()
        self.sandbox_id = (sandbox_id or os.getenv(_SANDBOX_ID_ENV_VAR, "")).strip()
        self.sandbox_definition_id = (
            sandbox_definition_id or os.getenv(_SANDBOX_DEFINITION_ID_ENV_VAR, "")
        ).strip()
        self.sessions_async = bool(sessions_async) if sessions_async is not None else False
        self.sessions_wait_timeout_seconds = (
            float(sessions_wait_timeout_seconds)
            if sessions_wait_timeout_seconds is not None
            else 600.0
        )
        self.sessions_poll_interval_seconds = (
            float(sessions_poll_interval_seconds)
            if sessions_poll_interval_seconds is not None
            else 1.0
        )
        if self.agent_transport == "sessions":
            if sessions_async is None:
                self.sessions_async = _env_bool(_SESSIONS_ASYNC_ENV_VAR, False)
            if sessions_wait_timeout_seconds is None:
                self.sessions_wait_timeout_seconds = _env_float(
                    _SESSIONS_WAIT_TIMEOUT_SECONDS_ENV_VAR, 600.0
                )
            if sessions_poll_interval_seconds is None:
                self.sessions_poll_interval_seconds = _env_float(
                    _SESSIONS_POLL_INTERVAL_SECONDS_ENV_VAR, 1.0
                )
        if self.sessions_wait_timeout_seconds <= 0:
            raise ValueError("sessions_wait_timeout_seconds must be greater than 0")
        if self.sessions_poll_interval_seconds <= 0:
            raise ValueError("sessions_poll_interval_seconds must be greater than 0")

    @classmethod
    def from_step_runtime(
        cls,
        *,
        sessions_async: Optional[bool] = None,
        sessions_wait_timeout_seconds: Optional[float] = None,
        sessions_poll_interval_seconds: Optional[float] = None,
    ) -> "BridgeExecutionClient":
        """Construct a sessions client from Bridge step-runtime environment variables."""
        transport = os.getenv(_STEP_RUNTIME_TRANSPORT_ENV_VAR, "sessions").strip().lower()
        if transport != "sessions":
            raise ValueError(
                f"unsupported {_STEP_RUNTIME_TRANSPORT_ENV_VAR}={transport!r}; expected 'sessions'"
            )

        api_base_url = (
            os.getenv(_STEP_RUNTIME_API_BASE_URL_ENV_VAR)
            or os.getenv(_API_BASE_URL_ENV_VAR, "")
        ).strip()
        api_token = (
            os.getenv(_STEP_RUNTIME_API_TOKEN_ENV_VAR)
            or os.getenv(_API_TOKEN_ENV_VAR, "")
        ).strip()
        sandbox_id = (
            os.getenv(_STEP_RUNTIME_SANDBOX_ID_ENV_VAR)
            or os.getenv(_SANDBOX_ID_ENV_VAR, "")
        ).strip()

        if not api_base_url:
            raise RuntimeError(
                f"missing {_STEP_RUNTIME_API_BASE_URL_ENV_VAR} in step runtime environment"
            )
        if not api_token:
            raise RuntimeError(
                f"missing {_STEP_RUNTIME_API_TOKEN_ENV_VAR} in step runtime environment"
            )
        if not sandbox_id:
            raise RuntimeError(
                f"missing {_STEP_RUNTIME_SANDBOX_ID_ENV_VAR} in step runtime environment"
            )

        return cls(
            agent_transport="sessions",
            api_base_url=api_base_url,
            api_token=api_token,
            sandbox_id=sandbox_id,
            sessions_async=sessions_async,
            sessions_wait_timeout_seconds=sessions_wait_timeout_seconds,
            sessions_poll_interval_seconds=sessions_poll_interval_seconds,
        )

    def connect(self):
        """Establish connection to the Bridge service."""
        if self.agent_transport == "sessions":
            return
        self.channel = grpc.insecure_channel(self.address)
        self.stub = bridge_sidecar_pb2_grpc.BridgeSidecarServiceStub(self.channel)

    def close(self):
        """Close the connection to the Bridge service."""
        if self.channel:
            self.channel.close()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def start_agent(
        self,
        prompt: str,
        agent_name: Optional[str] = None,
        directory: Optional[str] = None,
        continue_from: Optional[bridge_sidecar_pb2.ContinueFrom] = None,
        content_parts: Optional[list[ContentPartInput]] = None,
    ) -> tuple[str, str, str]:
        """
        Start an agent with the given prompt.

        Args:
            prompt: The prompt to provide to the agent
            agent_name: Name of the agent to use (defaults to "agent_1003_cc_v2_rc-fp8-tpr")
            directory: Working directory for the agent
            continue_from: Optional continuation details from a previous run
            content_parts: Optional multimodal content parts (text, images). Each item
                can be a dict like ``{"type": "text", "text": "..."}``,
                ``{"type": "image_url", "image_url": {"url": "..."}}``,
                a ``TextContentPart``/``ImageURLContentPart`` model, or a proto
                ``ContentPart`` message directly. These parts are sent after
                the prompt. Use ContentParts only to control the order, e.g. to put an image first.

        Returns:
            Tuple of (agent_name, session_id, exit_result)
        """
        if agent_name is None:
            agent_name = _DEFAULT_AGENT_NAME

        if self.agent_transport == "sessions":
            if content_parts:
                raise ValueError(
                    "content_parts are not supported with sessions transport"
                )
            if directory:
                raise ValueError(
                    "directory is not supported with sessions transport"
                )
            return self._start_agent_via_sessions_api(
                prompt=prompt,
                agent_name=agent_name,
                continue_from=continue_from,
            )

        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        proto_parts = [to_proto_content_part(p) for p in content_parts] if content_parts else []

        request = bridge_sidecar_pb2.StartAgentRequest(
            prompt=prompt,
            agent_name=agent_name,
            directory=directory or "",
            continue_from=continue_from,
            content_parts=proto_parts,
        )
        response = self.stub.StartAgent(request)

        return (
            response.run_detail.agent_name,
            response.run_detail.session_id,
            response.exit_result,
        )

    def _start_agent_via_sessions_api(
        self,
        *,
        prompt: str,
        agent_name: str,
        continue_from: Optional[bridge_sidecar_pb2.ContinueFrom],
    ) -> tuple[str, str, str]:
        self._validate_sessions_config()

        agent_id = self._resolve_agent_id(agent_name)
        payload: dict[str, Any] = {
            "type": "remote",
            "prompt": prompt,
        }
        if self.sandbox_id:
            payload["sandbox_id"] = self.sandbox_id
        if self.sandbox_definition_id:
            payload["sandbox_definition_id"] = self.sandbox_definition_id
        if continue_from is not None:
            payload["continue_from"] = self._map_continue_from_for_sessions(
                continue_from
            )

        response = self._sessions_request_json(
            "POST", f"/v0/agents/{agent_id}/sessions", body=payload
        )
        session_id = response.get("id")
        if not isinstance(session_id, str) or not session_id:
            raise RuntimeError("sessions API did not return a valid session id")
        if self.sessions_async:
            return agent_name, session_id, "scheduled"

        terminal_state = self._wait_for_terminal_session_state(session_id)
        return agent_name, session_id, self._exit_result_for_terminal_state(terminal_state)

    def _validate_sessions_config(self) -> None:
        if not self.api_base_url:
            raise RuntimeError(
                f"sessions transport requires {_API_BASE_URL_ENV_VAR} or api_base_url"
            )
        if not self.api_token:
            raise RuntimeError(
                f"sessions transport requires {_API_TOKEN_ENV_VAR} or api_token"
            )
        if bool(self.sandbox_id) == bool(self.sandbox_definition_id):
            raise RuntimeError(
                "sessions transport requires exactly one of sandbox_id or sandbox_definition_id"
            )

    def _resolve_agent_id(self, agent_name: str) -> str:
        agents = self._sessions_request_json("GET", "/v0/agents", query={"name": agent_name})
        if not isinstance(agents, list):
            raise RuntimeError("unexpected list-agents response shape")

        exact_matches = [
            agent
            for agent in agents
            if isinstance(agent, dict) and agent.get("name") == agent_name
        ]
        if not exact_matches:
            raise RuntimeError(f"agent {agent_name!r} not found")
        if len(exact_matches) > 1:
            raise RuntimeError(f"agent lookup for {agent_name!r} is ambiguous")

        agent_id = exact_matches[0].get("id")
        if not isinstance(agent_id, str) or not agent_id:
            raise RuntimeError(f"agent {agent_name!r} has no id")
        return agent_id

    def _map_continue_from_for_sessions(
        self, continue_from: bridge_sidecar_pb2.ContinueFrom
    ) -> dict[str, str]:
        previous_run_detail = continue_from.previous_run_detail
        previous_session_id = previous_run_detail.session_id
        if not previous_session_id:
            raise ValueError("continue_from.previous_run_detail.session_id is required")

        strategy_field = continue_from.WhichOneof("compaction_strategy")
        if strategy_field == "compaction":
            raise ValueError(
                "continue_from compaction is not supported for sessions transport in this phase"
            )

        return {
            "previous_session_id": previous_session_id,
            "strategy": "no_compaction",
        }

    def _wait_for_terminal_session_state(self, session_id: str) -> str:
        deadline = time.monotonic() + self.sessions_wait_timeout_seconds
        last_state = "unknown"

        while True:
            response = self._sessions_request_json("GET", f"/v0/sessions/{session_id}")
            if not isinstance(response, dict):
                raise RuntimeError("unexpected get-session response shape")

            state = response.get("state")
            if isinstance(state, str):
                normalized_state = state.strip().lower()
                if normalized_state:
                    last_state = normalized_state
                if normalized_state in _TERMINAL_SESSION_STATES:
                    return normalized_state

            now = time.monotonic()
            if now >= deadline:
                raise RuntimeError(
                    f"timed out waiting for session {session_id} to reach terminal state "
                    f"after {self.sessions_wait_timeout_seconds:.1f}s (last_state={last_state})"
                )

            time.sleep(min(self.sessions_poll_interval_seconds, deadline - now))

    def _exit_result_for_terminal_state(self, state: str) -> str:
        return "success" if state == "finished" else "failure"

    def _sessions_request_json(
        self,
        method: str,
        path: str,
        *,
        query: Optional[dict[str, str]] = None,
        body: Optional[dict[str, Any]] = None,
    ) -> Any:
        if not self.api_base_url:
            raise RuntimeError("api_base_url is required for sessions transport")
        if not self.api_token:
            raise RuntimeError("api_token is required for sessions transport")

        base = self.api_base_url.rstrip("/")
        url = f"{base}{path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        raw_body: Optional[bytes] = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_token}",
        }
        if body is not None:
            raw_body = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url=url,
            data=raw_body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read().decode("utf-8")
        except urllib.error.HTTPError as err:
            raw = err.read()
            details = raw.decode("utf-8", errors="replace") if raw else str(err)
            raise RuntimeError(
                f"sessions API request failed ({method} {path}): {err.code} {details}"
            ) from err
        except urllib.error.URLError as err:
            raise RuntimeError(
                f"sessions API request failed ({method} {path}): {err.reason}"
            ) from err

        if not payload:
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError as err:
            raise RuntimeError(
                f"sessions API returned invalid JSON for {method} {path}"
            ) from err


BridgeSidecarClient = BridgeExecutionClient

__all__ = ["BridgeExecutionClient", "BridgeSidecarClient"]
