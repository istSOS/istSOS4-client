# istsos4-client

Python client for [istSOS4](https://github.com/istSOS/istsos4) (OGC SensorThings API).

## Installation

```bash
pip install istsos4-client
```

## Usage

### Connect

```python
from istsos4_client import Client

client = Client("http://localhost:8018/istsos4/v1.1")
```

With authentication:

```python
from istsos4_client import Client
from istsos4_client.auth import BearerTokenAuth

auth = BearerTokenAuth(
    "http://localhost:8018/istsos4/v1.1/Login",
    username="admin",
    password="admin",
)
client = Client("http://localhost:8018/istsos4/v1.1", auth=auth)
```

The token is refreshed automatically before it expires.

### Create entities

```python
from istsos4_client.models import (
    Thing, Sensor, ObservedProperty, Datastream,
    UnitOfMeasurement, Observation,
)

thing = Thing(name="Weather station", description="Station on the roof")
client.post(thing)          # thing.iot_id is set from the response

sensor = Sensor(name="DHT22", encoding_type="application/pdf")
client.post(sensor)

obs_prop = ObservedProperty(
    name="Air temperature",
    description="Temperature of the air",
    definition="http://vocab.nerc.ac.uk/collection/P07/current/CFSN0023/",
)
client.post(obs_prop)

datastream = Datastream(
    name="Air temperature at roof",
    description="Temperature readings",
    unit_of_measurement=UnitOfMeasurement(name="degree Celsius", symbol="°C"),
    observation_type="http://www.opengis.net/def/observationType/OGC-OM/2.0/OM_Measurement",
    thing=thing,            # linked by @iot.id since thing.iot_id is set
    sensor=sensor,
    observed_property=obs_prop,
)
client.post(datastream)
```

Relations accept an `int` id, an entity that was already posted (linked by
id), or an unsaved entity (deep insert):

```python
# Deep insert: creates the Thing together with the Datastream
datastream = Datastream(
    ...,
    thing=Thing(name="New station", description="Created inline"),
)
```

### Post observations

```python
from datetime import datetime, timezone

obs = Observation(
    phenomenon_time=datetime.now(timezone.utc),
    result=21.3,
    datastream=datastream,
)
client.post(obs)
```

istSOS4 supports commit messages for traceability:

```python
client.post(obs, commit_message="Nightly import from field logger")
```

### Read entities

```python
# Single entity by id
thing = client.get(Thing, 1)

# All entities of a type (pagination via @iot.nextLink handled automatically)
things = client.list(Thing)
observations = client.list(Observation)
```

### Time intervals

`phenomenonTime` ranges use the SensorThings `start/end` ISO string encoding,
exposed as a typed object:

```python
from istsos4_client.models import TimeInterval

obs = Observation(
    phenomenon_time=TimeInterval(
        start=datetime(2026, 7, 1, tzinfo=timezone.utc),
        end=datetime(2026, 7, 2, tzinfo=timezone.utc),
    ),
    result=20.1,
    datastream=42,          # plain int id works too
)
```

### Available entities

`Thing`, `Location`, `HistoricalLocation`, `Sensor`, `ObservedProperty`,
`Datastream`, `FeatureOfInterest`, `Observation`, plus istSOS4-specific
`Network`, `User`, and `Policy`.

## License

Apache-2.0
