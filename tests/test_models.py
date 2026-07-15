"""
test_models.py — model-layer tests built from REAL istSOS4 payloads
(the example JSONs collected in the models' docstrings).

Run:  pytest test_models.py -v

Import assumes models_reviewed.py sits alongside; change to
`from istsos_client.models import ...` once the package layout exists.

Notes on the fixtures:
  * Sensor's and Observation's docstring examples were missing closing
    braces — completed here, content untouched.
  * Network has no real payload yet (its docstring was a copy of
    Location's), so its test is a skipped placeholder.
  * Fixtures live as Python dicts for now; moving them to
    tests/fixtures/*.json captured straight from the server is the
    natural next step.
"""

from datetime import datetime, timezone

import pytest

from istsos4_client.models import (
    Datastream,
    FeatureOfInterest,
    HistoricalLocation,
    Location,
    Observation,
    ObservedProperty,
    Policy,
    Sensor,
    Thing,
    TimeInterval,
    UnitOfMeasurement,
    User,
)

BASE = "http://localhost:8018/v4/v1.1"

# ---------------------------------------------------------------------------
# Real payloads (from the istSOS4 instance, via the model docstrings)
# ---------------------------------------------------------------------------

SWISS_POINT = {
    "crs": {"type": "name", "properties": {"name": "EPSG:2056"}},
    "type": "Point",
    "coordinates": [2712762.08, 1090801.84],
}

LOCATION_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/Locations(1)",
    "Things@iot.navigationLink": f"{BASE}/Locations(1)/Things",
    "HistoricalLocations@iot.navigationLink": f"{BASE}/Locations(1)/HistoricalLocations",
    "Commit@iot.navigationLink": f"{BASE}/Locations(1)/Commit(2)",
    "name": "Figino",
    "description": "Piattaforma di Figino",
    "encodingType": "application/json",
    "location": SWISS_POINT,
    "properties": None,
}

THING_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/Things(1)",
    "Locations@iot.navigationLink": f"{BASE}/Things(1)/Locations",
    "HistoricalLocations@iot.navigationLink": f"{BASE}/Things(1)/HistoricalLocations",
    "Datastreams@iot.navigationLink": f"{BASE}/Things(1)/Datastreams",
    "Commit@iot.navigationLink": f"{BASE}/Things(1)/Commit(3)",
    "name": "FIGINO",
    "description": "Piattaforma di Figino",
    "properties": None,
}

HISTORICAL_LOCATION_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/HistoricalLocations(1)",
    "Locations@iot.navigationLink": f"{BASE}/HistoricalLocations(1)/Locations",
    "Thing@iot.navigationLink": f"{BASE}/HistoricalLocations(1)/Thing",
    "Commit@iot.navigationLink": f"{BASE}/HistoricalLocations(1)/Commit(3)",
    "time": "2026-07-15T09:46:00Z",
}

SENSOR_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/Sensors(1)",
    "Datastreams@iot.navigationLink": f"{BASE}/Sensors(1)/Datastreams",
    "Commit@iot.navigationLink": f"{BASE}/Sensors(1)/Commit(4)",
    "name": "da7a0c28-7faf-4a33-b8a6-62b8e739d6e8",
    "description": "",
    "encodingType": "application/pdf",
    "metadata": "https://www.soundnine.com/wp-content/uploads/Manuals/R0123-XT-Sensors-V2.pdf",
    "properties": {"serialNumber": "0GG"},
}

OBSERVED_PROPERTY_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/ObservedProperties(1)",
    "Datastreams@iot.navigationLink": f"{BASE}/ObservedProperties(1)/Datastreams",
    "Commit@iot.navigationLink": f"{BASE}/ObservedProperties(1)/Commit(5)",
    "name": "Acceleration",
    "description": "Acceleration",
    "definition": "-",
    "properties": None,
}

DATASTREAM_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/Datastreams(1)",
    "Thing@iot.navigationLink": f"{BASE}/Datastreams(1)/Thing",
    "Sensor@iot.navigationLink": f"{BASE}/Datastreams(1)/Sensor",
    "ObservedProperty@iot.navigationLink": f"{BASE}/Datastreams(1)/ObservedProperty",
    "Observations@iot.navigationLink": f"{BASE}/Datastreams(1)/Observations",
    "Commit@iot.navigationLink": f"{BASE}/Datastreams(1)/Commit(7)",
    "Network@iot.navigationLink": f"{BASE}/Datastreams(1)/Network",
    "name": "ACC_xt_0_4",
    "description": (
        "Datastream to measure acceleration from sensor mounted "
        "on the Figino platform at depth 0_4 m"
    ),
    "unitOfMeasurement": {
        "name": "Meter per second squared",
        "symbol": "m/s²",
    },
    "observationType": "http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement",
    "observedArea": SWISS_POINT,
    "phenomenonTime": "2025-09-23T13:40:00Z/2026-04-30T00:00:00Z",
    "resultTime": "2026-04-28T00:10:00Z/2026-04-30T00:00:00Z",
    "properties": {
        "samplingFrequency": "PT10M",
        "acquisitionFrequency": "PT10M",
    },
}

FEATURE_OF_INTEREST_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/FeaturesOfInterest(1)",
    "Observations@iot.navigationLink": f"{BASE}/FeaturesOfInterest(1)/Observations",
    "Commit@iot.navigationLink": f"{BASE}/FeaturesOfInterest(1)/Commit(1)",
    "name": "Figino",
    "description": "Piattaforma di Figino",
    "encodingType": "application/json",
    "feature": SWISS_POINT,
    "properties": None,
}

OBSERVATION_PAYLOAD = {
    "@iot.id": 1,
    "@iot.selfLink": f"{BASE}/Observations(1)",
    "FeatureOfInterest@iot.navigationLink": f"{BASE}/Observations(1)/FeatureOfInterest",
    "Datastream@iot.navigationLink": f"{BASE}/Observations(1)/Datastream",
    "Commit@iot.navigationLink": f"{BASE}/Observations(1)/Commit(1)",
    "phenomenonTime": "2026-04-28T00:10:00Z",
    "resultTime": "2026-04-28T00:10:00Z",
    "result": 18.2960125,
    "resultQuality": 100,
    "validTime": None,
    "parameters": None,
}

USER_PAYLOAD = {
    "id": 1,
    "username": "admin",
    "contact": None,
    "uri": "/Users(1)",
    "role": "administrator",
}

POLICY_PAYLOAD = {
    "schemaname": "sensorthings",
    "tablename": "Location",
    "policyname": "test_sensor_location_update",
    "permissive": "PERMISSIVE",
    "roles": ["sensor1"],
    "cmd": "UPDATE",
    "qual": "true",
    "with_check": "true",
}

SENSORTHINGS_CASES = [
    (Location, LOCATION_PAYLOAD),
    (Thing, THING_PAYLOAD),
    (HistoricalLocation, HISTORICAL_LOCATION_PAYLOAD),
    (Sensor, SENSOR_PAYLOAD),
    (ObservedProperty, OBSERVED_PROPERTY_PAYLOAD),
    (Datastream, DATASTREAM_PAYLOAD),
    (FeatureOfInterest, FEATURE_OF_INTEREST_PAYLOAD),
    (Observation, OBSERVATION_PAYLOAD),
]
CASE_IDS = [cls.__name__ for cls, _ in SENSORTHINGS_CASES]


# ---------------------------------------------------------------------------
# Every SensorThings entity: real payload parses, envelope handled, and
# serialize() never leaks read-only server fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls,payload", SENSORTHINGS_CASES, ids=CASE_IDS)
def test_deserialize_accepts_real_payload(cls, payload):
    entity = cls.deserialize(payload)
    assert entity.iot_id == payload["@iot.id"]
    assert entity.self_link == payload["@iot.selfLink"]


@pytest.mark.parametrize("cls,payload", SENSORTHINGS_CASES, ids=CASE_IDS)
def test_serialize_never_leaks_readonly_fields(cls, payload):
    dumped = cls.deserialize(payload).serialize()
    for key in dumped:
        assert not key.startswith("@iot."), f"leaked envelope field {key}"
        assert "navigationLink" not in key, f"leaked nav link {key}"


# ---------------------------------------------------------------------------
# Entity-specific behavior
# ---------------------------------------------------------------------------


class TestLocation:
    def test_fields(self):
        loc = Location.deserialize(LOCATION_PAYLOAD)
        assert loc.encoding_type == "application/json"
        assert loc.properties is None  # explicit null tolerated
        # legacy CRS member must survive untouched (EPSG:2056 coordinates)
        assert loc.location["crs"]["properties"]["name"] == "EPSG:2056"

    def test_create_payload_shape(self):
        dumped = Location.deserialize(LOCATION_PAYLOAD).serialize()
        assert set(dumped) == {
            "name",
            "description",
            "encodingType",
            "location",
        }


class TestDatastream:
    def test_unit_of_measurement_typed_without_definition(self):
        ds = Datastream.deserialize(DATASTREAM_PAYLOAD)
        assert isinstance(ds.unit_of_measurement, UnitOfMeasurement)
        assert ds.unit_of_measurement.symbol == "m/s²"
        assert ds.unit_of_measurement.definition is None  # absent in istSOS4

    def test_interval_summaries_parsed_but_excluded(self):
        ds = Datastream.deserialize(DATASTREAM_PAYLOAD)
        assert isinstance(ds.phenomenon_time, TimeInterval)
        assert ds.phenomenon_time.start == datetime(
            2025, 9, 23, 13, 40, tzinfo=timezone.utc
        )
        dumped = ds.serialize()
        for readonly in ("observedArea", "phenomenonTime", "resultTime"):
            assert readonly not in dumped

    def test_constructible_without_server_computed_fields(self):
        # R4: with required observedArea/phenomenonTime this raised.
        ds = Datastream(
            name="n",
            description="d",
            observation_type="OM_Measurement",
            unit_of_measurement=UnitOfMeasurement(name="u", symbol="s"),
        )
        assert "name" in ds.serialize()


class TestObservation:
    def test_fields(self):
        obs = Observation.deserialize(OBSERVATION_PAYLOAD)
        assert obs.result == pytest.approx(18.2960125)
        assert obs.result_quality == 100
        assert obs.valid_time is None  # explicit null tolerated
        assert isinstance(
            obs.phenomenon_time, datetime
        )  # instant, not interval

    def test_create_payload(self):
        obs = Observation(
            phenomenon_time=datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc),
            result=21.4,
            datastream=3,
        )
        dumped = obs.serialize()
        assert dumped["Datastream"] == {"@iot.id": 3}
        assert dumped["result"] == 21.4
        assert dumped["phenomenonTime"].startswith("2026-07-14T10:00:00")


class TestHistoricalLocation:
    def test_time_parsed(self):
        hl = HistoricalLocation.deserialize(HISTORICAL_LOCATION_PAYLOAD)
        assert hl.time == datetime(2026, 7, 15, 9, 46, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Admin entities: different envelope
# ---------------------------------------------------------------------------


class TestUser:
    def test_plain_id_envelope(self):
        user = User.deserialize(USER_PAYLOAD)
        assert user.iot_id == 1  # from "id", not "@iot.id"
        assert user.role == "administrator"

    def test_id_not_leaked_on_dump(self):
        dumped = User.deserialize(USER_PAYLOAD).serialize()
        assert "id" not in dumped and "@iot.id" not in dumped


class TestPolicy:
    def test_rls_expressions_are_strings(self):
        pol = Policy.deserialize(POLICY_PAYLOAD)
        assert pol.qual == "true" and isinstance(pol.qual, str)
        # a REAL policy expression must also validate:
        pol2 = Policy.deserialize(
            {**POLICY_PAYLOAD, "qual": '("network_id" = 5)'}
        )
        assert pol2.qual == '("network_id" = 5)'

    def test_snake_case_kept_on_wire(self):
        dumped = Policy.deserialize(POLICY_PAYLOAD).serialize()
        assert "with_check" in dumped
        assert "withCheck" not in dumped


# ---------------------------------------------------------------------------
# TimeInterval value type
# ---------------------------------------------------------------------------


class TestTimeInterval:
    def test_parse(self):
        ti = TimeInterval.model_validate(DATASTREAM_PAYLOAD["phenomenonTime"])
        assert ti.start == datetime(2025, 9, 23, 13, 40, tzinfo=timezone.utc)
        assert ti.end == datetime(2026, 4, 30, 0, 0, tzinfo=timezone.utc)

    def test_roundtrip_is_semantically_stable(self):
        # NOT string equality: 'Z' parses in, '+00:00' may come out.
        ti = TimeInterval.model_validate(DATASTREAM_PAYLOAD["phenomenonTime"])
        again = TimeInterval.model_validate(ti.model_dump())
        assert again == ti


# ---------------------------------------------------------------------------
# Relation serialization: link vs deep insert vs expanded reads
# ---------------------------------------------------------------------------


class TestRelations:
    def test_link_by_int(self):
        ds = Datastream(
            name="n",
            description="d",
            observation_type="t",
            unit_of_measurement=UnitOfMeasurement(name="u", symbol="s"),
            thing=42,
        )
        assert ds.serialize()["Thing"] == {"@iot.id": 42}

    def test_link_by_entity_with_id_reuses_instead_of_duplicating(self):
        existing = Location.deserialize(LOCATION_PAYLOAD)  # iot_id == 1
        thing = Thing(name="n", description="d", locations=[existing])
        assert thing.serialize()["Locations"] == [{"@iot.id": 1}]

    def test_deep_insert_for_fresh_entity(self):
        fresh = Location(
            name="USI rooftop",
            description="east corner",
            location={"type": "Point", "coordinates": [8.95, 46.0]},
        )
        dumped = Thing(
            name="n", description="d", locations=[fresh]
        ).serialize()["Locations"][0]
        assert dumped["encodingType"] == "application/json"
        assert "@iot.id" not in dumped  # it IS new

    def test_mixed_list(self):
        fresh = Location(
            name="x",
            description="y",
            location={"type": "Point", "coordinates": [0, 0]},
        )
        dumped = Thing(
            name="n", description="d", locations=[5, fresh]
        ).serialize()["Locations"]
        assert dumped[0] == {"@iot.id": 5}
        assert dumped[1]["name"] == "x"

    def test_expanded_read_deserializes_typed(self):
        payload = {**THING_PAYLOAD, "Locations": [LOCATION_PAYLOAD]}
        thing = Thing.deserialize(payload)  # $expand=Locations
        assert isinstance(thing.locations[0], Location)
        assert thing.locations[0].iot_id == 1
        # and re-serializing links rather than re-embedding:
        assert thing.serialize()["Locations"] == [{"@iot.id": 1}]
