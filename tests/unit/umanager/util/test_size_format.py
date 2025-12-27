from umanager.util.size_format import format_size, to_size_parts


def test_to_size_parts_none_is_zero() -> None:
    parts = to_size_parts(None)
    assert parts.bytes == 0
    assert parts.value == 0
    assert parts.unit == "B"


def test_to_size_parts_bytes() -> None:
    parts = to_size_parts(999)
    assert parts.unit == "B"
    assert parts.value == 999


def test_to_size_parts_kb_boundary_binary() -> None:
    parts = to_size_parts(1024)
    assert parts.unit == "KB"
    assert parts.value == 1


def test_to_size_parts_mb_boundary_binary() -> None:
    parts = to_size_parts(1024**2)
    assert parts.unit == "MB"
    assert parts.value == 1


def test_format_size_strips_trailing_dot_zero() -> None:
    assert format_size(12 * 1024**3, decimals=1) == "12 GB"


def test_format_size_small_value_keeps_one_decimal_by_default() -> None:
    # 1.5 KB
    assert format_size(1536) == "1.5 KB"
