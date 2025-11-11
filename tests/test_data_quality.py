import pandas as pd

from snipetrade.data.quality import check_quality, enforce_quality


def test_quality_detects_duplicates():
    index = pd.to_datetime([
        "2024-01-01T00:00Z",
        "2024-01-01T01:00Z",
        "2024-01-01T01:00Z",
        "2024-01-01T02:00Z",
    ])
    frame = pd.DataFrame(
        {"open": [1, 2, 2, 3], "high": [1, 2, 2, 3], "low": [1, 2, 2, 3], "close": [1, 2, 2, 3], "volume": 1},
        index=index,
    )
    report = check_quality(frame)
    assert report.fixes["deduplicated"] == 1

    cleaned = enforce_quality(frame)
    assert cleaned.index.is_monotonic_increasing
    assert cleaned.index.is_unique
