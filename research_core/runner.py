"""Generic research module runner."""

from __future__ import annotations

import argparse

from research_core.framework.registry import ModuleRegistry

# Ensure built-in modules are registered.
import research_core.modules.discovery.module  # noqa: F401


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading AI Research Core runner")
    parser.add_argument(
        "--module",
        default="edge_discovery",
        choices=ModuleRegistry.list_modules(),
        help="Registered research module id",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for CSV and summary outputs",
    )
    args = parser.parse_args()

    module = ModuleRegistry.get(args.module)
    if module is None:
        raise SystemExit(f"Unknown module: {args.module}")

    result = module.run(args.output_dir)
    print(result.to_dict())


if __name__ == "__main__":
    main()
