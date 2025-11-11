"""Walk-forward aware dataset helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import pandas as pd


@dataclass(frozen=True)
class DatasetWindow:
    """Slice of OHLCV data used for training or testing.

    Attributes
    ----------
    start:
        Inclusive starting timestamp of the window.
    end:
        Inclusive ending timestamp of the window.
    frame:
        Pandas DataFrame slice containing the OHLCV candles.
    """

    start: pd.Timestamp
    end: pd.Timestamp
    frame: pd.DataFrame

    def __post_init__(self) -> None:  # pragma: no cover - defensive guard
        if not isinstance(self.frame.index, pd.DatetimeIndex):
            raise TypeError("DatasetWindow.frame must be indexed by DatetimeIndex")


def _resolve_offset(offset: pd.Timedelta | str | int) -> pd.Timedelta:
    if isinstance(offset, pd.Timedelta):
        return offset
    if isinstance(offset, str):
        return pd.Timedelta(offset)
    if isinstance(offset, int):
        return pd.Timedelta(minutes=offset)
    raise TypeError(f"Unsupported offset type: {type(offset)!r}")


def walk_forward_windows(
    frame: pd.DataFrame,
    *,
    train: pd.Timedelta | str | int,
    test: pd.Timedelta | str | int,
    steps: int,
    anchor: Optional[pd.Timestamp] = None,
    drop_partial: bool = True,
) -> List[Tuple[DatasetWindow, DatasetWindow]]:
    """Create rolling train/test windows for walk-forward analysis.

    Parameters
    ----------
    frame:
        OHLCV dataframe indexed by timestamp.
    train / test:
        Duration for each training and testing segment. Strings such as ``"30d"``
        are accepted and converted to :class:`pandas.Timedelta`.
    steps:
        Number of walk-forward iterations to generate.
    anchor:
        Optional starting timestamp. By default the first index value is used.
    drop_partial:
        When True, windows that do not contain enough candles to fully cover the
        requested duration are skipped.
    """

    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("walk_forward_windows expects a DatetimeIndex")
    if frame.empty:
        return []

    train_delta = _resolve_offset(train)
    test_delta = _resolve_offset(test)

    first_idx = anchor or frame.index.min()
    windows: List[Tuple[DatasetWindow, DatasetWindow]] = []

    for step in range(steps):
        train_start = first_idx + step * test_delta
        train_end = train_start + train_delta
        test_start = train_end
        test_end = test_start + test_delta

        train_slice = frame.loc[(frame.index >= train_start) & (frame.index < train_end)]
        test_slice = frame.loc[(frame.index >= test_start) & (frame.index < test_end)]

        if drop_partial and (train_slice.empty or test_slice.empty):
            continue

        if train_slice.empty or test_slice.empty:
            break

        windows.append(
            (
                DatasetWindow(train_slice.index[0], train_slice.index[-1], train_slice.copy()),
                DatasetWindow(test_slice.index[0], test_slice.index[-1], test_slice.copy()),
            )
        )

    return windows


def expanding_walk_forward(
    frame: pd.DataFrame,
    *,
    initial_train: pd.Timedelta | str | int,
    test: pd.Timedelta | str | int,
    steps: int,
) -> List[Tuple[DatasetWindow, DatasetWindow]]:
    """Walk-forward splits where the training window grows after each step."""

    if not isinstance(frame.index, pd.DatetimeIndex):
        raise TypeError("expanding_walk_forward expects a DatetimeIndex")

    train_delta = _resolve_offset(initial_train)
    test_delta = _resolve_offset(test)

    if frame.empty:
        return []

    start = frame.index.min()
    windows: List[Tuple[DatasetWindow, DatasetWindow]] = []

    for step in range(steps):
        train_start = start
        train_end = start + train_delta + step * test_delta
        test_start = train_end
        test_end = test_start + test_delta

        train_slice = frame.loc[(frame.index >= train_start) & (frame.index < train_end)]
        test_slice = frame.loc[(frame.index >= test_start) & (frame.index < test_end)]

        if train_slice.empty or test_slice.empty:
            break

        windows.append(
            (
                DatasetWindow(train_slice.index[0], train_slice.index[-1], train_slice.copy()),
                DatasetWindow(test_slice.index[0], test_slice.index[-1], test_slice.copy()),
            )
        )

    return windows
