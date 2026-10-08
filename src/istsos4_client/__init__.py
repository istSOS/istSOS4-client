"""Python client for istSOS4 (OGC SensorThings API)."""

__version__ = "0.3.0"

from .client import Client, raise_for_status
from .models import (
    Datastream,
    Entity,
    FeatureOfInterest,
    HistoricalLocation,
    Location,
    Network,
    Observation,
    ObservedProperty,
    Policy,
    Sensor,
    Thing,
    TimeInterval,
    UnitOfMeasurement,
    User,
)
from .utils import decode_result_quality

__all__ = [
    "Client",
    "raise_for_status",
    "Datastream",
    "Entity",
    "FeatureOfInterest",
    "HistoricalLocation",
    "Location",
    "Network",
    "Observation",
    "ObservedProperty",
    "Policy",
    "Sensor",
    "Thing",
    "TimeInterval",
    "UnitOfMeasurement",
    "User",
    "decode_result_quality",
]
