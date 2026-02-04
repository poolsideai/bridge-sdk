#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts."""

import argparse
import asyncio
import importlib
import sys
from typing import Dict, Any, List, Tuple
import json
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[import-not-found,no-redef]

from bridge_sdk.step_function import STEP_REGISTRY, StepFunction
from bridge_sdk.pipeline import Pipeline, PipelineData


def load_config_modules() -> list[str]:
    """Load step modules from [tool.bridge] in pyproject.toml.

    Looks for pyproject.toml in the current working directory and reads
    the modules list from [tool.bridge.modules].

    Example pyproject.toml:
        [tool.bridge]
        modules = ["my_steps", "other_module"]

    Returns:
        List of module paths to scan for steps, or empty list if not configured.
    """
    pyproject_path = Path.cwd() / "pyproject.toml"

    if not pyproject_path.exists():
        return []

    try:
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)

        bridge_config = pyproject.get("tool", {}).get("bridge", {})
        modules = bridge_config.get("modules", [])

        if not isinstance(modules, list):
            print(
                f"Warning: [tool.bridge.modules] should be a list, got {type(modules).__name__}"
            )
            return []

        return modules
    except Exception as e:
        print(f"Warning: Failed to parse pyproject.toml: {e}")
        return []


def get_modules_from_args(args) -> list[str]:
    """Combine --module and --modules args, falling back to config file."""
    modules = []
    if args.modules:
        modules.extend(args.modules)
    if not modules:
        modules = load_config_modules()
    return modules


def discover_steps(module_paths: list[str]) -> Dict[str, StepFunction]:
    """Dynamically discover all functions decorated with @step in the specified modules.

    Args:
        module_paths: List of module paths to import and discover steps from.
                      These must be importable Python modules (i.e., installed packages
                      or modules accessible via PYTHONPATH).

    Note:
        For modules to be importable, either:
        1. Install your project in editable mode: `pip install -e .` or `uv sync`
        2. Add your project to PYTHONPATH: `export PYTHONPATH="${PYTHONPATH}:$(pwd)"`
        3. Use fully qualified module paths from installed packages
    """
    for module_path in module_paths:
        try:
            importlib.import_module(module_path)
        except ImportError as e:
            print(f"Error importing module '{module_path}': {e}")
            print()
            print("Make sure your step modules are importable. Options:")
            print("  1. Install your project: pip install -e . (or uv sync)")
            print('  2. Set PYTHONPATH: export PYTHONPATH="${PYTHONPATH}:$(pwd)"')
            print("  3. Use --modules with fully qualified package paths")
            sys.exit(1)
    return STEP_REGISTRY


def discover_steps_and_pipelines(
    module_paths: list[str],
) -> Tuple[Dict[str, StepFunction], Dict[str, Pipeline]]:
    """Discover steps and pipelines from the specified modules.

    Args:
        module_paths: List of module paths to import and discover from.

    Returns:
        A tuple of (steps_dict, pipelines_dict) where:
        - steps_dict: {step_name: StepFunction}
        - pipelines_dict: {pipeline_name: Pipeline}

    Raises:
        SystemExit: If a module has a Pipeline and contains bare @step functions
            (steps not registered via @pipeline.step).
    """
    pipelines_found: Dict[str, Pipeline] = {}

    for module_path in module_paths:
        steps_before = set(STEP_REGISTRY.keys())

        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            print(f"Error importing module '{module_path}': {e}")
            print()
            print("Make sure your step modules are importable. Options:")
            print("  1. Install your project: pip install -e . (or uv sync)")
            print('  2. Set PYTHONPATH: export PYTHONPATH="${PYTHONPATH}:$(pwd)"')
            print("  3. Use --modules with fully qualified package paths")
            sys.exit(1)

        # Find steps added by this module
        steps_after = set(STEP_REGISTRY.keys())
        new_steps = list(steps_after - steps_before)

        # Find all Pipeline instances in the module (any variable name)
        module_pipelines: List[Pipeline] = []
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue
            attr = getattr(module, attr_name, None)
            if isinstance(attr, Pipeline):
                module_pipelines.append(attr)

        # If module has Pipeline(s), validate no bare @step functions exist
        if module_pipelines:
            module_file = getattr(module, "__file__", None)
            bare_steps = []
            for s in new_steps:
                sf = STEP_REGISTRY[s]
                if sf.step_data.pipeline is not None:
                    continue
                # Only flag steps actually defined in this module's file,
                # not steps pulled in transitively via __init__.py or other imports.
                if module_file and sf.step_data.file_path:
                    if not module_file.endswith(sf.step_data.file_path):
                        continue
                bare_steps.append(s)
            if bare_steps:
                pipeline_names = ", ".join(p.name for p in module_pipelines)
                print(
                    f"Error: Module '{module_path}' defines Pipeline(s) '{pipeline_names}' "
                    f"but has bare @step functions: {', '.join(bare_steps)}"
                )
                print("Use @pipeline.step instead of @step for steps in a pipeline module.")
                sys.exit(1)

            for p in module_pipelines:
                pipelines_found[p.name] = p

    return STEP_REGISTRY, pipelines_found


def cmd_check(args):
    """Handle 'check' command - validate project setup for Bridge SDK."""
    print("Checking Bridge SDK project setup...\n")

    errors = []
    warnings = []

    pyproject_path = Path.cwd() / "pyproject.toml"

    # Check 1: pyproject.toml exists
    if not pyproject_path.exists():
        errors.append("pyproject.toml not found in current directory")
        print("[FAIL] pyproject.toml exists")
    else:
        print("[OK]   pyproject.toml exists")

        try:
            with open(pyproject_path, "rb") as f:
                pyproject = tomllib.load(f)

            # Check 2: [build-system] section exists
            if "build-system" not in pyproject:
                errors.append(
                    "[build-system] section missing from pyproject.toml. "
                    "This is required for your project to be installable."
                )
                print("[FAIL] [build-system] section configured")
            else:
                print("[OK]   [build-system] section configured")

            # Check 3: [tool.bridge] section exists
            bridge_config = pyproject.get("tool", {}).get("bridge", {})
            if not bridge_config:
                errors.append(
                    "[tool.bridge] section missing from pyproject.toml. "
                    'Add it with: [tool.bridge]\\nmodules = ["your_package.steps"]'
                )
                print("[FAIL] [tool.bridge] section configured")
            else:
                print("[OK]   [tool.bridge] section configured")

                # Check 4: modules list is configured
                modules = bridge_config.get("modules", [])
                if not modules:
                    errors.append(
                        "[tool.bridge.modules] is empty. "
                        'Add your step modules: modules = ["your_package.steps"]'
                    )
                    print("[FAIL] [tool.bridge.modules] configured")
                elif not isinstance(modules, list):
                    errors.append(
                        f"[tool.bridge.modules] should be a list, got {type(modules).__name__}"
                    )
                    print("[FAIL] [tool.bridge.modules] configured")
                else:
                    print(f"[OK]   [tool.bridge.modules] configured: {modules}")

                    # Check 5: Each module is importable
                    print()
                    print("Checking module imports...")
                    for module in modules:
                        try:
                            importlib.import_module(module)
                            print(f"[OK]   Can import '{module}'")
                        except ImportError as e:
                            errors.append(
                                f"Cannot import module '{module}': {e}. "
                                "Make sure your project is installed (uv sync or pip install -e .)"
                            )
                            print(f"[FAIL] Can import '{module}'")

                    # Check 6: Steps are registered
                    if STEP_REGISTRY:
                        print()
                        print(f"[OK]   Found {len(STEP_REGISTRY)} step(s):")
                        for step_name in STEP_REGISTRY:
                            print(f"       - {step_name}")
                    else:
                        warnings.append(
                            "No steps found. Make sure your modules contain @step decorated functions."
                        )
                        print()
                        print("[WARN] No steps found in registered modules")

        except Exception as e:
            errors.append(f"Failed to parse pyproject.toml: {e}")
            print(f"[FAIL] pyproject.toml is valid TOML")

    # Summary
    print()
    print("-" * 50)

    if errors:
        print(f"\nFound {len(errors)} error(s):\n")
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}\n")
        sys.exit(1)
    elif warnings:
        print(f"\nSetup OK with {len(warnings)} warning(s):\n")
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning}\n")
        sys.exit(0)
    else:
        print("\nAll checks passed! Your project is ready for Bridge SDK.")
        sys.exit(0)


def cmd_config_get_dsl(args):
    """Handle 'config get-dsl' command."""
    modules = get_modules_from_args(args)
    if not modules:
        print(
            "Error: No modules specified. Use --modules or configure [tool.bridge] in pyproject.toml"
        )
        sys.exit(1)

    # Discover both steps and pipelines
    steps, pipelines = discover_steps_and_pipelines(modules)

    # Build DSL dictionary with steps
    steps_dict = {
        step_name: sf.step_data.model_dump() for (step_name, sf) in steps.items()
    }

    # Build DSL dictionary with pipelines (metadata only)
    pipelines_dict = {
        pname: PipelineData(
            name=p.name, rid=p.rid, description=p.description,
        ).model_dump()
        for pname, p in pipelines.items()
    }

    # Combined output with both steps and pipelines
    dsl_dict: Dict[str, Any] = {
        "steps": steps_dict,
        "pipelines": pipelines_dict,
    }

    dsl_json = json.dumps(dsl_dict, indent=2)

    print(dsl_json)

    # Write to output file
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dsl_json)


async def cmd_run_step(args):
    """Handle 'run' command to execute a step."""
    # 1. Discover steps from the modules
    modules = get_modules_from_args(args)
    if not modules:
        print(
            "Error: No modules specified. Use --modules or configure [tool.bridge] in pyproject.toml"
        )
        sys.exit(1)
    steps = discover_steps(modules)
    step_name = args.step

    # 2. Find the step by name
    if step_name not in steps:
        print(steps)
        print(f"Error: Step '{args.step}' not found in modules '{modules}'")
        print(f"Available steps: {', '.join(steps.keys())}")
        sys.exit(1)

    # Parse results JSON
    try:
        if args.results_file:
            # Read from file
            with open(args.results_file, "r") as f:
                cached_results = json.load(f)
        elif args.results:
            # Parse from command line
            cached_results = json.loads(args.results)
        else:
            print("Error: Either --results or --results-file must be provided")
            sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing results JSON: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"Error: Results file not found: {args.results_file}")
        sys.exit(1)

    # 3. Get the step function
    step = steps[step_name]

    # === Step 1: Resolution ===
    # Combine --input and --results into the final resolved input
    # Priority: --input values take precedence over --results
    try:
        input_data = json.loads(args.input) if args.input else {}
    except json.JSONDecodeError as e:
        print(f"Error parsing input JSON: {e}")
        sys.exit(1)

    resolved_input = dict(input_data)  # Start with explicit input

    # Fill in params from step results (same logic as on_invoke_step)
    for param_name, dep_step_name in step.step_data.params_from_step_results.items():
        # Only fill from results if not already provided in input
        if param_name not in resolved_input and dep_step_name in cached_results:
            resolved_input[param_name] = cached_results[dep_step_name]

    # === Step 2: Validation ===
    # Check that all required params are present in resolved input
    missing_params = []
    for param_name, dep_step_name in step.step_data.params_from_step_results.items():
        if param_name not in resolved_input:
            missing_params.append(f"{param_name} (from step: {dep_step_name})")

    if missing_params:
        raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")

    # 5. Call the step function
    try:
        result = await step.on_invoke_step(input=args.input, step_results=args.results)
        print(f"Step '{args.step}' executed successfully")
        print(f"Result: {result}")

        # Write result to output file if specified
        if args.output_file:
            output_path = Path(args.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # result is already a JSON string from on_invoke_step
            output_path.write_text(result)
            print(f"Result written to {output_path}")
    except Exception as e:
        print(f"Error executing step '{args.step}': {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="CLI for discovering and running Steps"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'check' command
    check_parser = subparsers.add_parser(
        "check", help="Validate project setup for Bridge SDK"
    )
    check_parser.set_defaults(func=cmd_check)

    # 'config get-dsl' command
    config_parser = subparsers.add_parser("config", help="Configuration commands")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    get_dsl_parser = config_subparsers.add_parser(
        "get-dsl", help="Get DSL for discovered steps"
    )
    get_dsl_parser.add_argument(
        "--modules",
        nargs="+",
        help="Module paths to discover steps from (e.g., --modules examples my_steps)",
    )
    get_dsl_parser.add_argument(
        "--output-file",
        default="/tmp/config_get_dsl/dsl.json",
        help="Path to write the DSL JSON file (default: /tmp/config_get_dsl/dsl.json)",
    )
    get_dsl_parser.set_defaults(func=cmd_config_get_dsl)

    # 'run' command
    run_parser = subparsers.add_parser("run", help="Run a specific step")
    run_parser.add_argument("--step", required=True, help="Name of the step to run")
    run_parser.add_argument(
        "--results", help='Json of cached results. e.g. {"Step1": "abc"}'
    )
    run_parser.add_argument(
        "--results-file", help="Path to JSON file containing cached results"
    )
    run_parser.add_argument("--input", required=True, help="Input to the step")
    run_parser.add_argument(
        "--modules",
        nargs="+",
        help="Module paths to discover steps from (e.g., --modules examples my_steps)",
    )
    run_parser.add_argument("--output-file", help="Path to write the step result to")
    run_parser.set_defaults(func=cmd_run_step)

    args = parser.parse_args()

    # Check if a command was provided
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Execute the command
    if asyncio.iscoroutinefunction(args.func):
        asyncio.run(args.func(args))
    else:
        args.func(args)


if __name__ == "__main__":
    main()
