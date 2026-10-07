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
STATUS_COLORS = {
    "raw": "#2e7d32",  # green
    "passed": "#2e7d32",
    "filled": "#f9a825",  # amber
    "failed": "#c62828",  # red
    "not executed": "#000000",  # grey
    "no data / NaN": "#9e9e9e",
    "unused": "#616161",  # dark grey
}
# OASI: resultQuality is a plain score, not a bitmask.
OASI_QUALITY = {  # score: (level, status, color)
    0: ("AQC0", "Raw data", "#9e9e9e"),  # grey
    1: ("AQC0", "Corrupted", "#e57373"),  # light red
    2: ("AQC1", "Suspect", "#f9a825"),  # amber
    3: ("AQC1", "Good", "#81c784"),  # light green
    6: ("HQC", "Corrupted", "#b71c1c"),  # dark red
    7: ("HQC", "Extraordinary (no statistics)", "#6a1b9a"),  # purple
    8: ("HQC", "Good (correction applied)", "#00897b"),  # teal
    9: ("HQC", "Good (special event)", "#1565c0"),  # blue
    10: ("HQC", "Good", "#2e7d32"),  # green
}


def decode_result_quality(
    result_quality: int | str,
    constraints: list[dict[str, Any]] | str | None = None,
    legend: bool = False,
    oasi: bool = False,
) -> list[dict[str, Any]]:
    """Decode a resultQuality bitmask into a readable list, one entry per pair.

    ``result_quality`` is an int or numeric string. ``constraints`` is the
    datastream's constraints list, or the same list as a JSON string (N
    entries). ``legend=True`` adds a "color" to each entry.

    The mask is split into 2-bit pairs, starting from the lowest bits:
        pair 0       data state:   11 raw, 10 filled, 00 no data / NaN
        pairs 1..N   constraints:  11 passed, 10 failed, 00 not executed
        pair N+1     human review: same values, omitted when 00
    01 is reserved and decodes as "unused".

    Example with 3 constraints, mask 0b1111101111 = 1007:
        human  c#3  c#2  c#1  data
          11    11   10   11    11
        -> [{"id": 0, "status": "raw", "description": "data state"},
            {"id": 1, "status": "passed",
             "description": "flagRange: column=result, min=1, max=100"},
            {"id": 2, "status": "failed", "description": "flagConstants: ..."},
            {"id": 3, "status": "passed", "description": "flagZScore: ..."},
            {"id": 4, "status": "passed", "description": "human review"}]

    ``oasi=True`` reads ``result_quality`` as an OASI score instead (see
    OASI_QUALITY) and ignores ``constraints``:
        8 -> [{"id": 0, "status": "Good (correction applied)",
               "description": "HQC"}]

    Raises ValueError if the mask is negative, not an integer, or has bits
    set beyond the human pair, or if the OASI score is unknown.
    """
    result_quality = int(result_quality)
    if oasi:
        if result_quality not in OASI_QUALITY:
            raise ValueError(
                f"result_quality {result_quality} is not an OASI score"
            )
        level, status, color = OASI_QUALITY[result_quality]
        entry = {"id": 0, "status": status, "description": level}
        if legend:
            entry["color"] = color
        return [entry]

    if isinstance(constraints, str):
        constraints = json.loads(constraints)
    constraints = constraints or []

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
            entry["color"] = STATUS_COLORS[status]
        decoded.append(entry)
    return decoded


if __name__ == "__main__":
    constraints = [
        {"type": "flagRange", "min": 1, "max": 100},
        {"type": "flagConstants", "thresh": 0.1},
        {"type": "flagZScore", "thresh": 3, "center": False},
    ]
    print(
        json.dumps(
            decode_result_quality(243, constraints, legend=True), indent=2
        )
    )
