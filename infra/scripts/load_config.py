#!/usr/bin/env python3
"""Config loader for multi-platform deployments."""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed", file=sys.stderr)
    sys.exit(1)


def substitute_env_vars(value):
    """Substitute ${VAR} patterns with environment variables."""
    if isinstance(value, str):
        pattern = r'\$\{([A-Z_][A-Z0-9_]*?)(?::-([^}]+))?\}'
        def replacer(match):
            var_name = match.group(1)
            default_value = match.group(2)
            return os.environ.get(var_name, default_value or f"${{{var_name}}}")
        return re.sub(pattern, replacer, value)
    elif isinstance(value, dict):
        return {k: substitute_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [substitute_env_vars(item) for item in value]
    return value


def load_config(environment, platform, project_root):
    """Load configuration for environment and platform."""
    env_config_path = project_root / "config" / "environments" / f"{environment}.yml"
    
    if not env_config_path.exists():
        print(f"ERROR: Config not found: {env_config_path}", file=sys.stderr)
        sys.exit(1)
    
    with open(env_config_path) as f:
        config = yaml.safe_load(f)
    
    config = substitute_env_vars(config)
    
    if platform not in config:
        print(f"ERROR: Platform '{platform}' not in config", file=sys.stderr)
        sys.exit(1)
    
    return {"environment": environment, "platform": platform, **config[platform]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", "-e", required=True, choices=["dev", "test", "prod"])
    parser.add_argument("--platform", "-p", required=True, choices=["databricks", "fabric", "aws"])
    parser.add_argument("--format", choices=["yaml", "json"], default="yaml")
    args = parser.parse_args()
    
    project_root = Path(__file__).resolve().parents[2]
    config = load_config(args.environment, args.platform, project_root)
    
    if args.format == "json":
        import json
        print(json.dumps(config, indent=2))
    else:
        print(yaml.dump(config, default_flow_style=False))


if __name__ == "__main__":
    main()
