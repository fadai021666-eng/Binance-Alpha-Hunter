"""统一的 JSON 输出渲染。"""
from __future__ import annotations

import json


def render(payload: dict, raw: bool) -> str:
    if raw:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return json.dumps(payload, ensure_ascii=False, indent=2)
