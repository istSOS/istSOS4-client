from datetime import datetime
from typing import Any, ClassVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel


class TimeInterval(BaseModel):
    """SensorThings encodes time ranges as 'startISO/endISO' strings."""

    start: datetime
    end: datetime

    @model_validator(mode="before")
    @classmethod
    def _split_iso_pair(cls, v: Any) -> Any:
        if isinstance(v, str):
            start, end = v.split("/", 1)
            return {"start": start, "end": end}
        return v

    @model_serializer
    def _join_iso_pair(self) -> str:
        return f"{self.start.isoformat()}/{self.end.isoformat()}"


class UnitOfMeasurement(BaseModel):
    name: str
    symbol: str
    definition: str | None = None  # absent in real istSOS4 payloads


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Entity(BaseModel):
    """Common base — the istSOSComponent."""

    model_config = ConfigDict(
        populate_by_name=True,  # Python code uses snake_case names
        extra="ignore",  # nav links, versioning fields, ... dropped
        alias_generator=to_camel,  # phenomenon_time <-> phenomenonTime
    )

    ENDPOINT: ClassVar[str]

    # Read-only server fields: parsed from GETs, never sent back.
    iot_id: int | None = Field(None, alias="@iot.id", exclude=True)
    self_link: str | None = Field(None, alias="@iot.selfLink", exclude=True)

    def serialize(self) -> dict[str, Any]:
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    @classmethod
    def deserialize(cls, data: dict[str, Any]) -> "Entity":
        return cls.model_validate(data)


def _link_or_embed(value: Any) -> Any:
    """How relation fields serialize:
    42                         -> {"@iot.id": 42}   shallow link
    Entity with iot_id set     -> {"@iot.id": ...}  shallow link (reuse!)
    Entity without iot_id      -> nested JSON       deep insert
    """
    if isinstance(value, int):
        return {"@iot.id": value}
    if isinstance(value, Entity):
        if value.iot_id is not None:
            return {"@iot.id": value.iot_id}
        return value.serialize()
    return value


# ---------------------------------------------------------------------------
# istSOS4 admin entities (NOT SensorThings — different JSON envelope)
# ---------------------------------------------------------------------------


class User(Entity):
    """{"id": 1, "username": "admin", "contact": null,
    "uri": "/Users(1)", "role": "administrator"}"""

    ENDPOINT: ClassVar[str] = "/Users"

    iot_id: int | None = Field(None, alias="id", exclude=True)
    username: str
    contact: str | None = None
    uri: str | None = None
    role: str


class Policy(Entity):
    ENDPOINT: ClassVar[str] = "/Policies"

    schemaname: str
    tablename: str
    policyname: str
    permissive: str
    roles: list[str]
    cmd: str
    qual: str = "true"
    with_check: str = Field("true", alias="with_check")


# ---------------------------------------------------------------------------
# SensorThings entities + Network
# ---------------------------------------------------------------------------


class Network(Entity):
    ENDPOINT: ClassVar[str] = "/Networks"

    name: str


class Location(Entity):
    ENDPOINT: ClassVar[str] = "/Locations"

    name: str
    description: str
    encoding_type: str = "application/json"
    location: dict[str, Any]
    properties: dict[str, Any] | None = None


class Thing(Entity):
    ENDPOINT: ClassVar[str] = "/Things"

    name: str
    description: str
    properties: dict[str, Any] | None = None
    locations: list[int | Location] | None = Field(None, alias="Locations")

    @field_serializer("locations")
    def _rel(self, v: Any) -> Any:
        return v if v is None else [_link_or_embed(item) for item in v]


class HistoricalLocation(Entity):
    """Server-generated when a Thing's Locations change; read-mostly.
    Relations modelled so $expand=Thing,Locations deserializes into
    typed objects instead of being silently dropped."""

    ENDPOINT: ClassVar[str] = "/HistoricalLocations"

    time: datetime
    thing: int | Thing | None = Field(None, alias="Thing")
    locations: list[int | Location] | None = Field(None, alias="Locations")

    @field_serializer("thing")
    def _rel_one(self, v: Any) -> Any:
        return _link_or_embed(v)

    @field_serializer("locations")
    def _rel_many(self, v: Any) -> Any:
        return v if v is None else [_link_or_embed(item) for item in v]


class Sensor(Entity):
    ENDPOINT: ClassVar[str] = "/Sensors"

    name: str
    description: str | None = None
    encoding_type: str
    metadata: str | None = None
    properties: dict[str, Any] | None = None


class ObservedProperty(Entity):
    ENDPOINT: ClassVar[str] = "/ObservedProperties"

    name: str
    description: str
    definition: str
    properties: dict[str, Any] | None = None


class Datastream(Entity):
    ENDPOINT: ClassVar[str] = "/Datastreams"

    name: str
    description: str
    unit_of_measurement: UnitOfMeasurement
    observation_type: str
    properties: dict[str, Any] | None = None
    observed_area: dict[str, Any] | None = Field(None, exclude=True)
    phenomenon_time: TimeInterval | None = Field(None, exclude=True)
    result_time: TimeInterval | None = Field(None, exclude=True)
    thing: int | Thing | None = Field(None, alias="Thing")
    sensor: int | Sensor | None = Field(None, alias="Sensor")
    observed_property: int | ObservedProperty | None = Field(
        None, alias="ObservedProperty"
    )
    network: int | Network | None = Field(None, alias="Network")

    @field_serializer("thing", "sensor", "observed_property", "network")
    def _rel(self, v: Any) -> Any:
        return _link_or_embed(v)


class FeatureOfInterest(Entity):
    ENDPOINT: ClassVar[str] = "/FeaturesOfInterest"

    name: str
    description: str
    encoding_type: str = "application/json"
    feature: dict[str, Any]
    properties: dict[str, Any] | None = None


class Observation(Entity):
    ENDPOINT: ClassVar[str] = "/Observations"

    phenomenon_time: datetime | TimeInterval
    result: Any = None
    result_time: datetime | None = None
    result_quality: Any = None
    valid_time: TimeInterval | None = None
    parameters: dict[str, Any] | None = None
    datastream: int | Datastream | None = Field(None, alias="Datastream")
    feature_of_interest: int | FeatureOfInterest | None = Field(
        None, alias="FeatureOfInterest"
    )

    @field_serializer("datastream", "feature_of_interest")
    def _rel(self, v: Any) -> Any:
        return _link_or_embed(v)
