from snipetrade.orderflow.book_features import book_imbalance, best_spread_bps, queue_offset


def test_book_imbalance():
    orderbook = {
        "bids": [(100.0, 5.0), (99.5, 3.0)],
        "asks": [(100.5, 4.0), (101.0, 2.0)],
    }
    imbalance = book_imbalance(orderbook, depth=2)
    assert round(imbalance, 4) == round((8 - 6) / 14, 4)


def test_best_spread_bps():
    orderbook = {
        "bids": [(100.0, 5.0)],
        "asks": [(100.5, 4.0)],
    }
    spread = best_spread_bps(orderbook)
    assert round(spread, 2) == round((100.5 - 100.0) / 100.25 * 10_000, 2)


def test_queue_offset():
    offset_long = queue_offset(100.0, 100.5, 0.1, "LONG")
    assert 0 <= offset_long <= 0.1
    offset_short = queue_offset(100.0, 100.5, 0.1, "SHORT")
    assert -0.1 <= offset_short <= 0
