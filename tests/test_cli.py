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

"""CLI tests for file-based payload arguments."""

import argparse
import asyncio
import json
from typing import Annotated

import pytest

from bridge_sdk import EVAL_REGISTRY, STEP_REGISTRY, step, step_result
from bridge_sdk.cli import cmd_run_eval, cmd_run_step


@pytest.fixture(autouse=True)
def clear_registries():
    STEP_REGISTRY.clear()
    EVAL_REGISTRY.clear()
    yield
    STEP_REGISTRY.clear()
    EVAL_REGISTRY.clear()


def test_cmd_run_step_uses_input_and_results_files(tmp_path, monkeypatch):
    @step(name="sum_step")
    def sum_step(input_data: dict[str, int], dep_total: Annotated[int, step_result("dep")]) -> int:
        return input_data["value"] + dep_total

    monkeypatch.setattr("bridge_sdk.cli.get_modules_from_args", lambda _args: ["test.module"])
    monkeypatch.setattr(
        "bridge_sdk.cli.discover_steps_and_pipelines",
        lambda _modules: (STEP_REGISTRY, {}),
    )

    input_file = tmp_path / "input.json"
    results_file = tmp_path / "results.json"
    output_file = tmp_path / "output.json"
    input_file.write_text('{"input_data": {"value": 5}}')
    results_file.write_text('{"dep": 7}')

    args = argparse.Namespace(
        step="sum_step",
        results=None,
        results_file=str(results_file),
        input=None,
        input_file=str(input_file),
        modules=["test.module"],
        output_file=str(output_file),
    )

    asyncio.run(cmd_run_step(args))

    assert json.loads(output_file.read_text()) == 12


def test_cmd_run_eval_uses_context_file(tmp_path, monkeypatch):
    class FakeEval:
        def __init__(self):
            self.contexts: list[str] = []

        async def on_invoke_eval(self, context: str) -> str:
            self.contexts.append(context)
            return '{"metrics": {}, "result": {"type": "boolean", "boolean_value": true}}'

    fake_eval = FakeEval()
    EVAL_REGISTRY["echo_eval"] = fake_eval

    monkeypatch.setattr("bridge_sdk.cli.get_modules_from_args", lambda _args: ["test.module"])
    monkeypatch.setattr(
        "bridge_sdk.cli.discover_steps_and_pipelines",
        lambda _modules: (STEP_REGISTRY, {}),
    )

    context_file = tmp_path / "context.json"
    output_file = tmp_path / "output.json"
    expected_context = json.dumps({"hello": "world", "count": 3})
    context_file.write_text(expected_context)

    args = argparse.Namespace(
        eval="echo_eval",
        context=None,
        context_file=str(context_file),
        modules=["test.module"],
        output_file=str(output_file),
    )

    asyncio.run(cmd_run_eval(args))

    assert fake_eval.contexts == [expected_context]
    assert output_file.exists()
