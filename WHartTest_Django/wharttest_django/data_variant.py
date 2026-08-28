from __future__ import annotations

import os
import subprocess
from pathlib import Path

_VALID_VARIANTS = {"ce", "pe", "dev", "github", "pro"}
_AUTO_VARIANT = "auto"


def _normalize_variant(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().lower()
    if normalized in _VALID_VARIANTS or normalized == _AUTO_VARIANT:
        return normalized

    return None


def get_branch_data_variant(base_dir: Path) -> str:
    explicit_variant = _normalize_variant(os.environ.get("POSTGRES_DB_VARIANT"))
    if explicit_variant and explicit_variant != _AUTO_VARIANT:
        return explicit_variant

    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            cwd=base_dir,
        ).decode().strip()
    except Exception:
        branch = ""

    if branch.endswith("-ce"):
        return "ce"
    if branch.endswith("-pe"):
        return "pe"
    if branch.endswith("-github"):
        return "github"
    if branch.endswith("-pro"):
        return "pro"
    return "dev"


def build_postgres_db_name(variant: str) -> str:
    if variant == "dev":
        return "wharttest_dev"
    if variant in {"ce", "pe"}:
        return f"wharttest_{variant}"
    return f"wharttest_dev_{variant}"


def get_postgres_db_name(base_dir: Path) -> str:
    explicit_variant = _normalize_variant(os.environ.get("POSTGRES_DB_VARIANT"))
    if explicit_variant:
        return build_postgres_db_name(get_branch_data_variant(base_dir))

    explicit_db = os.environ.get("POSTGRES_DB")
    if explicit_db:
        return explicit_db

    return build_postgres_db_name(get_branch_data_variant(base_dir))


def get_sqlite_db_path(base_dir: Path) -> str:
    explicit_variant = _normalize_variant(os.environ.get("POSTGRES_DB_VARIANT"))
    explicit_path = os.environ.get("DATABASE_PATH")
    if explicit_path and not explicit_variant:
        return explicit_path

    variant = get_branch_data_variant(base_dir)
    filename = "db.sqlite3" if variant == "dev" else f"db_{variant}.sqlite3"
    return str((base_dir.parent / "data" / filename).resolve())


def get_checkpoint_sqlite_path(base_dir: Path) -> str:
    explicit_variant = _normalize_variant(os.environ.get("POSTGRES_DB_VARIANT"))
    explicit_path = os.environ.get("LANGGRAPH_CHECKPOINT_SQLITE_PATH")
    if explicit_path and not explicit_variant:
        return explicit_path

    variant = get_branch_data_variant(base_dir)
    filename = (
        "chat_history.sqlite" if variant == "dev" else f"chat_history_{variant}.sqlite"
    )
    return str((base_dir.parent / "data" / filename).resolve())
