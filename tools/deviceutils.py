# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2025 grommunio GmbH

"""Utility helpers for device-related metadata."""

import json
from typing import Any, Optional
from services import ServiceUnavailableError

CONNECTION_KEY = "grommunio-sync:connections"


def _normalize_timestamp(value: Any) -> Optional[int]:
    """Return int timestamp or None for unsupported values."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return int(float(value))
        except ValueError:
            return None
    return None


def _parse_lastconnect_payload(raw: Any) -> Optional[int]:
    """Parse Redis payload and return normalized timestamp."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return _normalize_timestamp(payload.get("starttime"))


def retrieve_lastconnecttime(redis, username: str, device_id: str, fallback: Any = None) -> Optional[int]:
    """Read last connect timestamp for device, returning fallback if unavailable."""
    _fallback = _normalize_timestamp(fallback)
    if not redis:
        return _fallback
    try:
        raw = redis.hget(CONNECTION_KEY, f"{device_id}|-|{username}")
    except ServiceUnavailableError:
        return _fallback
    except Exception:
        return _fallback
    if not raw:
        return _fallback
    candidate = _parse_lastconnect_payload(raw)
    return candidate if candidate is not None else _fallback

