import json

import pytest

from istsos4_client.utils import decode_result_quality

CONSTRAINTS = [
    {"type": "flagRange", "column": "result", "min": 1, "max": 100},
    {"type": "flagConstants", "column": "result", "thresh": 0.1, "window": "3h"},
    {"type": "flagZScore", "column": "result", "thresh": 3, "center": False},
]


def test_decode_result_quality():
    expected = [
        {"id": 0, "status": "raw", "description": "data state"},
        {
            "id": 1,
            "status": "passed",
            "description": "flagRange: column=result, min=1, max=100",
        },
        {
            "id": 2,
            "status": "failed",
            "description": "flagConstants: column=result, thresh=0.1, window=3h",
        },
        {
            "id": 3,
            "status": "passed",
            "description": "flagZScore: column=result, thresh=3, center=False",
        },
    ]
    assert decode_result_quality(0b0011101111, CONSTRAINTS) == expected
    assert decode_result_quality("239", json.dumps(CONSTRAINTS)) == expected
    assert decode_result_quality(0b1111101111, CONSTRAINTS) == expected + [
        {"id": 4, "status": "passed", "description": "human review"}
    ]
    assert decode_result_quality(0, []) == [
        {"id": 0, "status": "no data / NaN", "description": "data state"}
    ]
    with pytest.raises(ValueError):
        decode_result_quality(0b11111111, CONSTRAINTS[:1])  # beyond human pair


def test_decode_result_quality_legend():
    decoded = decode_result_quality(0b1110, CONSTRAINTS[:1], legend=True)
    assert decoded[0]["color"] == "#f9a825"  # filled
    assert decoded[1]["color"] == "#2e7d32"  # passed
    colors = ["c0", "orange", "c2", "c3", "#00ff00", "c5", "c6", "c7"]
    decoded = decode_result_quality(
        0b1110, CONSTRAINTS[:1], legend=True, status_colors=colors
    )
    assert decoded[0]["color"] == "orange"  # filled, 2nd in the order
    assert decoded[1]["color"] == "#00ff00"  # passed, 5th in the order
    with pytest.raises(ValueError):
        decode_result_quality(0b1110, legend=True, status_colors=colors[:2])


def test_decode_result_quality_oasi():
    def score(mask, constraints=CONSTRAINTS):
        return [e["id"] for e in decode_result_quality(mask, constraints, oasi=True)]

    assert decode_result_quality(0b11, CONSTRAINTS, legend=True, oasi=True) == [
        {"id": 0, "status": "AQC0", "description": "Raw data", "color": "#9e9e9e"}
    ]
    assert score(0b0010101011) == [1]  # all failed
    assert score(0b0011101111) == [2]  # one failed
    assert score(0b0011111111) == [3]  # all passed
    assert score(0b1011111111) == [6]  # human failed
    assert score(0b1110101011) == [10]  # human passed wins over checks
    assert score(0b0000001111) == [2]  # passed + not executed: suspect
    assert score(0b10, []) == []  # filled, nothing else: unmapped
    assert score(0, []) == []  # no data
