"""Helpers for optional submit hooks on async provider queue submissions."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

_ON_SUBMITTED_EXCEPTION_ATTR = "_easy_ai_on_submitted_exception"


def run_on_submitted(
    on_submitted: Callable[[dict[str, Any]], None] | None,
    submission: Mapping[str, Any] | None,
) -> None:
    """Invoke the optional submit callback and mark raised exceptions."""

    if on_submitted is None:
        return
    receipt = dict(submission or {})
    try:
        on_submitted(receipt)
    except BaseException as exc:
        try:
            setattr(exc, _ON_SUBMITTED_EXCEPTION_ATTR, True)
        except Exception:
            pass
        raise


def is_on_submitted_exception(exc: BaseException) -> bool:
    """Return whether the exception came from an `on_submitted` callback."""

    return bool(getattr(exc, _ON_SUBMITTED_EXCEPTION_ATTR, False))
