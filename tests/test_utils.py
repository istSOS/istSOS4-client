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


def test_decode_result_quality_oasi():
    assert decode_result_quality("8", oasi=True, legend=True) == [
        {
            "id": 0,
            "status": "Good (correction applied)",
            "description": "HQC",
            "color": "#00897b",
        }
    ]
    assert decode_result_quality(0b11, CONSTRAINTS, oasi=True) == [
        {"id": 0, "status": "Good", "description": "AQC1"}  # not a bitmask
    ]
    with pytest.raises(ValueError):
        decode_result_quality(4, oasi=True)  # gap in the OASI table
