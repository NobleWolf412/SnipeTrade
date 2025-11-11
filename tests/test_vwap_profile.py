import pandas as pd

from snipetrade.features.vwap import anchored_vwap
from snipetrade.features.volume_profile import hvn_lvn_levels


def test_anchored_vwap():
    data = pd.DataFrame(
        {
            "high": [101, 102, 103, 104],
            "low": [99, 100, 101, 102],
            "close": [100, 101, 102, 103],
            "volume": [10, 20, 30, 40],
        }
    )
    result = anchored_vwap(data, anchor_idx=1)
    assert "vwap" in result and "std" in result
    assert result["vwap"] > 0
    assert result["std"] >= 0


def test_volume_profile_levels():
    profile = [(100, 50), (101, 25), (102, 75)]
    hvn, lvn = hvn_lvn_levels(profile)
    assert hvn[0] == 102
    assert lvn[0] == 101
