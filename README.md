# istsos4-client

Python client for [istSOS4](https://github.com/istSOS/istsos4) (OGC SensorThings API).

## Installation

```bash
pip install istsos4-client
```

Requires Python 3.10+.

## Usage

### Connect

```python
from istsos4_client import Client

client = Client("http://localhost:8018/istsos4/v1.1")
```

With authentication (logs in at `<base_url>/Login`):

```python
client = Client(
    "http://localhost:8018/istsos4/v1.1",
    username="admin",
    password="admin",
)
```

The bearer token is fetched and refreshed automatically. Login uses the
same timeout and retries as every other request.

Requests that fail with a connection error, a timeout or a 408, 429, 502,
503 or 504 response are retried, by default 3 times, 1 second apart:

```python
client = Client(url, max_retries=5, retry_delay=2.0)  # max_retries=0 disables it
```

The client keeps connections open for reuse. Close them with `client.close()`,
or use it as a context manager:

```python
with Client(url) as client:
    ...
```

### Create entities

```python
from istsos4_client import (
    Thing, Sensor, ObservedProperty, Datastream,
    UnitOfMeasurement, Observation,
)

thing = client.post(Thing(name="Weather station", description="Station on the roof"))
thing.iot_id                # set from the response

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

Batches go to `/BulkObservations` as one `dataArray` per datastream, split
into as many requests as the server's row limit needs. Returns how many
observations were sent:

```python
sent = client.bulk_observations([obs1, obs2, obs3])
sent = client.bulk_observations(observations, force=True)  # adds ?force=true
```

### Read entities

```python
# Single entity by id
thing = client.get(Thing, 1)

# Embed a related entity instead of just a link
obs = client.get(Observation, 7, expand="Datastream")
obs.datastream.properties   # a full Datastream, not None

# All entities of a type (pagination via @iot.nextLink handled automatically)
things = client.list(Thing)
observations = client.list(Observation)

# Same query options, streamed a page at a time — for collections too large
# to hold in memory
for obs in client.iter_list(Observation, orderby="phenomenonTime"):
    ...
```

### Filter queries

`list()` passes OData query options straight to the server:

```python
observations = client.list(
    Observation,
    filter="phenomenonTime ge 2026-07-01T00:00:00Z and result gt 20",
    orderby="phenomenonTime",
)
```

Supported options: `filter`, `select`, `orderby`, `expand`, `top`
(`get()` takes `expand` and `filter`, `patch()` takes `filter`).
Field names in query strings use the server's camelCase form
(`phenomenonTime`, not `phenomenon_time`). Note that `select` must keep
the fields the model requires, and `top` sets the server page size —
`list()` still follows pagination and returns all matches.

### Update entities

```python
thing = client.get(Thing, 1)
thing.description = "Moved to the north side of the roof"
client.patch(thing)     # requires iot_id, set by get()/post()
```

Only the fields that are set are sent, so a partial update needs no read:

```python
client.patch(Observation(iot_id=7, result=1.5, result_quality="100"))
```

`filter` is passed through as OData `$filter`:

```python
client.patch(
    Observation(iot_id=7, result=1.5),
    filter="phenomenonTime eq '2026-07-15T10:00:00Z'",
)
```

### Delete entities

```python
client.delete(Thing, 1)
```

Options after the entity (`commit_message`, `filter`, `expand`, `force`, ...)
are keyword-only on every method.

### Errors

`get`, `list`, `post`, `patch`, `delete` and `bulk_observations` raise
`requests.HTTPError` on a non-2xx response, with the server's error body in
the message and the response itself on `exc.response`.

### Result quality

`decode_result_quality` turns a resultQuality bitmask into one readable entry
per 2-bit pair (data state, each constraint, human review). `oasi_quality`
maps the same mask to a single OASI score, or `None` when there is none:

```python
from istsos4_client import decode_result_quality, oasi_quality

constraints = [...]   # the datastream's constraints, list or JSON string
decode_result_quality(1007, constraints, legend=True)
# [{"id": 0, "status": "raw", "description": "data state", "color": ...}, ...]
oasi_quality(1007, constraints)
# {"id": 10, "status": "HQC", "description": "good"}
```

`status_colors=[...]` replaces the legend colors; see the function's
docstring for the order.

### Time intervals

`phenomenonTime` ranges use the SensorThings `start/end` ISO string encoding,
exposed as a typed object:

```python
from istsos4_client import TimeInterval

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

### STAplus

STAplus entities live in `istsos4_client.staplus` and need an istSOS4 build
with STAplus support. The client refuses them unless enabled at init:

```python
from istsos4_client import staplus

client = Client("http://localhost:8018/istsos4/v1.1", staplus=True)
party = staplus.Party(role="individual", display_name="Jo")
client.post(party)
client.post(staplus.Datastream(..., party=party))  # Datastream + Party link
```

Available: `Party`, and `Datastream` (the base one plus its `party` relation).

## License

Apache-2.0
