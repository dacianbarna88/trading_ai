#!/usr/bin/env python3
"""Canonical paths for regenerable TAE reports — never write these into repo root."""

from __future__ import annotations

from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
GENERATED_REPORTS_DIR = PROJECT_DIR / "runtime_outputs" / "generated_reports"


def generated_reports_dir() -> Path:
    GENERATED_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return GENERATED_REPORTS_DIR


def generated_report(name: str) -> Path:
    """Return absolute path under runtime_outputs/generated_reports/<name>."""
    return generated_reports_dir() / name
