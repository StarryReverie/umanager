from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

SizeSystem = Literal["binary", "decimal"]


@dataclass(frozen=True, slots=True)
class SizeParts:
    """人类可读的文件大小表示。

    - `bytes`: 原始字节数
    - `value`: 换算后的数值（已按选择的单位缩放）
    - `unit`: 单位字符串（例如 "B"/"KB"/"MB"/"GB"）
    """

    bytes: int
    value: float
    unit: str


def to_size_parts(
    num_bytes: int | None,
    *,
    system: SizeSystem = "binary",
    decimals: Optional[int] = None,
) -> SizeParts:
    """将字节数转换为“合适”的数值与单位。

    设计目标：
    - 统一 Overview 与 FileManager 的大小展示逻辑
    - 默认采用 1024 进制（与现有代码中 `1024**3` 的行为一致），但单位仍使用 KB/MB/GB 的标记

    参数：
    - `num_bytes`: 字节数；若为 None，视为 0
    - `system`:
        - "binary": 1024 进制
        - "decimal": 1000 进制
    - `decimals`: 小数位；
        - None：自动选择（B 不带小数；<10 用 1 位，其余用 0 位）

    返回：
    - SizeParts(bytes, value, unit)
    """

    raw = 0 if num_bytes is None else int(num_bytes)

    base = 1024 if system == "binary" else 1000
    units = ("B", "KB", "MB", "GB", "TB", "PB", "EB")

    sign = -1 if raw < 0 else 1
    n = abs(raw)

    unit_index = 0
    value = float(n)
    while unit_index < len(units) - 1 and value >= base:
        value /= base
        unit_index += 1

    value *= sign

    if decimals is None:
        if units[unit_index] == "B":
            decimals = 0
        elif abs(value) < 10:
            decimals = 1
        else:
            decimals = 0

    if decimals <= 0:
        value = float(int(round(value, 0)))
    else:
        value = round(value, decimals)

    return SizeParts(bytes=raw, value=value, unit=units[unit_index])


def format_size(
    num_bytes: int | None,
    *,
    system: SizeSystem = "binary",
    decimals: Optional[int] = None,
    sep: str = " ",
) -> str:
    """将字节数格式化为字符串，例如 "1.5 GB"。"""

    parts = to_size_parts(num_bytes, system=system, decimals=decimals)

    if parts.unit == "B":
        return f"{int(parts.value)}{sep}{parts.unit}"

    # 去掉多余的 .0（例如 12.0 GB -> 12 GB）
    text = f"{parts.value}"
    if text.endswith(".0"):
        text = text[:-2]

    return f"{text}{sep}{parts.unit}"
