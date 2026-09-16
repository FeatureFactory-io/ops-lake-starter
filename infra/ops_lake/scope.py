from pathlib import Path

import yaml

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "lake-scope-contract.yaml"


def load_scope_contract() -> dict:
    """
    Load the Lake Scope Contract YAML.

    :return: contract dict. Example: {"org": "YOUR_ORG", "views": ["github_commits"]}
    :raises FileNotFoundError: if docs/lake-scope-contract.yaml is missing
    :raises ValueError: if required keys are absent
    """
    if not CONTRACT_PATH.exists():
        raise FileNotFoundError(f"Lake Scope Contract missing: {CONTRACT_PATH}")
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        contract = yaml.safe_load(handle) or {}
    required = ("org", "host", "sources", "ci", "views", "buckets", "athena_database", "athena_workgroup")
    missing = [key for key in required if key not in contract]
    if missing:
        raise ValueError(f"Lake Scope Contract missing keys: {missing}")
    if contract["ci"] not in {"github_actions", "gitlab_ci"}:
        raise ValueError(f"ci must be github_actions XOR gitlab_ci, got {contract['ci']}")
    return contract
