import json
from typing import Any

DATA_STATUS = {
    0b11: "raw",
    0b10: "filled",
    0b00: "no data / NaN",
    0b01: "digital",
}
CONSTRAINT_STATUS = {
    0b11: "passed",
    0b10: "failed",
    0b00: "not executed",
    0b01: "unused",
}
HUMAN_STATUS = {
    0b11: "passed",
    0b10: "failed",
    0b00: "not executed",
    0b01: "unused",
}
# Default legend colors. A custom ``status_colors`` list follows this order.
STATUS_COLORS = {
    "raw": "#9e9e9e",
    "filled": "#f9a825",
    "no data / NaN": "#9e9e9e",
    "digital": "#1565c0",
    "passed": "#2e7d32",
    "failed": "#c62828",
    "not executed": "#000000",
    "unused": "#616161",
}
# OASI score: (level, description, color), mapped from the decoded statuses.
OASI_QUALITY = {
    0: ("AQC0", "raw data", "#9e9e9e"),  # data raw, no check executed
    1: ("AQC0", "corrupted", "#e57373"),  # all checks failed
    2: ("AQC1", "suspect", "#f9a825"),  # at least one check failed
    3: ("AQC1", "good", "#81c784"),  # all checks passed
    6: ("HQC", "corrupted", "#b71c1c"),  # human review failed
    7: ("HQC", "extraordinary (no statistics)", "#6a1b9a"),  # unused
    8: ("HQC", "good (correction applied)", "#00897b"),  # unused
    9: ("HQC", "good (special event)", "#1565c0"),  # unused
    10: ("HQC", "good", "#2e7d32"),  # human review passed
}


def decode_result_quality(
    result_quality: int | str,
    constraints: list[dict[str, Any]] | str | None = None,
    legend: bool = False,
    oasi: bool = False,
    status_colors: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """Decode a resultQuality bitmask into a readable list, one entry per pair.

    ``result_quality`` is an int or numeric string. ``constraints`` is the
    datastream's constraints list, or the same list as a JSON string (N
    entries). ``legend=True`` adds a "color" to each entry.

    The mask is split into 2-bit pairs, starting from the lowest bits:
        pair 0       data state:   11 raw, 10 filled, 00 no data / NaN,
                                   01 digital
        pairs 1..N   constraints:  11 passed, 10 failed, 00 not executed
        pair N+1     human review: same values, omitted when 00
    01 is reserved for constraints and human review and decodes as "unused".

    Example with 3 constraints, mask 0b1111101111 = 1007:
        human  c#3  c#2  c#1  data
          11    11   10   11    11
        -> [{"id": 0, "status": "raw", "description": "data state"},
            {"id": 1, "status": "passed",
             "description": "flagRange: column=result, min=1, max=100"},
            {"id": 2, "status": "failed", "description": "flagConstants: ..."},
            {"id": 3, "status": "passed", "description": "flagZScore: ..."},
            {"id": 4, "status": "passed", "description": "human review"}]

    ``status_colors`` replaces the legend colors. It must have one color per
    status, in this order:
        raw, filled, no data / NaN, digital,
        passed, failed, not executed, unused
    Values are used as given: hex "#2e7d32", a name like "green", or anything
    else your plotting tool understands.

    ``oasi=True`` maps the decoded mask to a single OASI score (see
    OASI_QUALITY): id is the score, status the level, description the label.
    Human review wins over the constraints:
        human passed                         -> 10 HQC  Good
        human failed                         ->  6 HQC  Corrupted
        all constraints passed               ->  3 AQC1 Good
        some constraints failed, or only
        some executed (rest passed)          ->  2 AQC1 Suspect
        all constraints failed               ->  1 AQC0 Corrupted
        data raw, no constraint executed     ->  0 AQC0 Raw data
    Any other combination has no OASI equivalent and returns [].
    The example mask above -> [{"id": 10, "status": "HQC",
                                "description": "Good"}]

    Raises ValueError if the mask is negative, not an integer, or has bits
    set beyond the human pair, or if ``status_colors`` has the wrong length.
    """
    result_quality = int(result_quality)
    if isinstance(constraints, str):
        constraints = json.loads(constraints)
    constraints = constraints or []
    colors = STATUS_COLORS
    if status_colors is not None:
        if len(status_colors) != len(STATUS_COLORS):
            raise ValueError(
                f"status_colors needs {len(STATUS_COLORS)} colors, "
                f"got {len(status_colors)}"
            )
        colors = dict(
            zip(STATUS_COLORS, status_colors)
        )  # i-th color, i-th status

    pair_count = len(constraints) + 2  # data state + constraints + human
    if result_quality < 0 or result_quality >> (2 * pair_count):
        raise ValueError(
            f"result_quality {result_quality} does not fit "
            f"{len(constraints)} constraints"
        )

    decoded = []
    for i in range(pair_count):
        pair = (result_quality >> (2 * i)) & 0b11
        if i == 0:
            status = DATA_STATUS[pair]
            description = "data state"
        elif i <= len(constraints):
            constraint = constraints[i - 1]
            params = ", ".join(
                f"{key}={value}"
                for key, value in constraint.items()
                if key != "type"
            )
            status = CONSTRAINT_STATUS[pair]
            description = f"{constraint['type']}: {params}"
        else:  # human review pair
            if not pair:
                break  # 00 = no human review, leave it out
            status = HUMAN_STATUS[pair]
            description = "human review"

        entry = {"id": i, "status": status, "description": description}
        if legend:
            entry["color"] = colors[status]
        decoded.append(entry)
    if not oasi:
        return decoded

    checks = {entry["status"] for entry in decoded[1 : len(constraints) + 1]}
    human = decoded[-1]["status"] if len(decoded) == pair_count else None
    if human:
        score = {"passed": 10, "failed": 6}.get(human)
    elif checks == {"failed"}:
        score = 1
    elif checks == {"passed"}:
        score = 3
    elif "failed" in checks or checks == {"passed", "not executed"}:
        score = 2
    elif decoded[0]["status"] == "raw" and checks <= {"not executed"}:
        score = 0
    else:
        score = None
    if score is None:
        return []  # no OASI equivalent, same as no data
    level, description, color = OASI_QUALITY[score]
    entry = {"id": score, "status": level, "description": description}
    if legend:
        entry["color"] = color
    return [entry]


if __name__ == "__main__":
    constraints1 = [
        {"type": "flagRange", "min": 1, "max": 100},
        {"type": "flagConstants", "thresh": 0.1},
        {"type": "flagZScore", "thresh": 3, "center": False},
    ]

    print(decode_result_quality(243, constraints1, legend=True, oasi=True))
    print(decode_result_quality(3, legend=True, oasi=True))
    print(decode_result_quality(1007, constraints1, legend=True, oasi=True))
    print(decode_result_quality(751, constraints1, legend=False, oasi=True))
