from __future__ import annotations
import time
from typing import Any, Callable, Iterator
from urllib.parse import quote, urlencode
import requests
from .models import Entity, Observation
from ._auth import BearerTokenAuth

OBSERVATION_COMPONENTS = [
    "result",
    "phenomenonTime",
    "resultTime",
    "resultQuality",
]

# asyncpg rejects a statement with more than 32767 bound parameters. The server
# binds one parameter per component plus a handful of bookkeeping columns per
# row, so keep a single /BulkObservations request comfortably under the cap.
MAX_ROWS_PER_BULK = int(32767 * 0.9) // (len(OBSERVATION_COMPONENTS) + 8)

# Responses worth sending again: the server did not handle the request
# (timeout, rate limit, proxy or server unavailable). A 500 is not retried,
# the request may already have been applied.
RETRY_STATUSES = {408, 429, 502, 503, 504}


def raise_for_status(
    response: requests.Response, context: str | None = None
) -> None:
    """requests' raise_for_status, with the server's error body in the message.

    istSOS4 explains rejections in the response body (which datastream is
    missing, which observation is a duplicate, ...); the default HTTPError
    message drops it, so callers only ever see the status code.
    """
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        message = f"{context}: {exc}" if context else str(exc)
        body = response.text.strip()
        if body:
            message = f"{message}; response body: {body}"
        raise requests.HTTPError(
            message, response=response, request=response.request
        ) from exc


def _uses_staplus(value: Any) -> bool:
    """True if value is a STAplus entity class, or an entity that is or embeds
    one (deep insert)."""
    if isinstance(value, type):
        return issubclass(value, Entity) and value.STAPLUS
    if isinstance(value, Entity):
        return value.STAPLUS or any(map(_uses_staplus, vars(value).values()))
    if isinstance(value, list):
        return any(map(_uses_staplus, value))
    return False


class Client:
    """Client for an istSOS4 server instance."""

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
        staplus: bool = False,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """staplus=True enables the STAplus entities in istsos4_client.staplus
        (the server must be an istSOS4 build with STAplus support).

        A request that fails with a connection error, a timeout or one of
        RETRY_STATUSES is sent again up to `max_retries` times, waiting
        `retry_delay` seconds in between; max_retries=0 disables it. A POST
        whose first attempt did reach the server before timing out can come
        back as a duplicate error on the retry."""
        self._base_url = base_url.rstrip("/")
        self._auth = (
            BearerTokenAuth(f"{self._base_url}/Login", username, password)
            if username is not None
            else None
        )
        self._timeout = timeout
        self._staplus = staplus
        self._max_retries = max_retries
        self._retry_delay = retry_delay

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self, commit_message: str | None = None) -> dict[str, str]:
        headers = self._auth.headers() if self._auth else {}
        if commit_message:
            headers["commit-message"] = commit_message
        return headers

    def _send(
        self, send: Callable[..., requests.Response], url: str, **kwargs: Any
    ) -> requests.Response:
        """Call `send` (requests.get/post/patch), retrying as described in
        __init__. Returns the last response, or raises the last error."""
        for attempt in range(self._max_retries + 1):
            last = attempt == self._max_retries
            try:
                response = send(url, timeout=self._timeout, **kwargs)
            except (requests.ConnectionError, requests.Timeout):
                if last:
                    raise
            else:
                if last or response.status_code not in RETRY_STATUSES:
                    return response
            time.sleep(self._retry_delay)
        raise AssertionError("unreachable")

    def _check_staplus(self, entity: Entity | type[Entity]) -> None:
        if not self._staplus and _uses_staplus(entity):
            raise ValueError(
                "STAplus entities need Client(..., staplus=True)."
            )

    def post(self, entity: Entity, commit_message: str | None = None) -> int:
        """Post an entity to the istSOS4 server."""
        self._check_staplus(entity)
        response = self._send(
            requests.post,
            f"{self._base_url}{entity.ENDPOINT}",
            json=entity.serialize(),
            headers=self._headers(commit_message),
        )
        raise_for_status(response, f"POST {entity.ENDPOINT}")
        location = response.headers.get("Location")
        if location:
            entity.iot_id = int(location.rsplit("(", 1)[1].rstrip(")"))

        return response.status_code

    def get(
        self, entity: type[Entity], entity_id: int, expand: str | None = None
    ) -> Entity:
        """Get an entity from the istSOS4 server.

        `expand` is passed through as OData $expand, e.g. expand="Datastream".
        """
        self._check_staplus(entity)
        url = f"{self._base_url}{entity.ENDPOINT}({entity_id})"
        if expand:
            url = f"{url}?{urlencode({'$expand': expand}, safe='$', quote_via=quote)}"
        response = self._send(requests.get, url, headers=self._headers())
        raise_for_status(response, f"GET {entity.ENDPOINT}({entity_id})")
        return entity.model_validate(response.json())

    def iter_list(
        self,
        entity: type[Entity],
        filter: str | None = None,
        select: str | None = None,
        orderby: str | None = None,
        expand: str | None = None,
        top: int | None = None,
    ) -> Iterator[Entity]:
        """Yield entities one page at a time, following @iot.nextLink.

        Use this instead of `list()` for collections too large to hold in
        memory (observation histories, migrations, ...).

        Query options are passed through as OData parameters, e.g.
        filter="phenomenonTime ge 2026-01-01T00:00:00Z".
        """
        self._check_staplus(entity)
        params: dict[str, str | int] = {
            f"${key}": value
            for key, value in dict(
                filter=filter,
                select=select,
                orderby=orderby,
                expand=expand,
                top=top,
            ).items()
            if value is not None
        }
        url: str | None = f"{self._base_url}{entity.ENDPOINT}"
        if params:
            # requests encodes spaces as '+' by default; OData servers expect
            # %20. safe="$" keeps the OData $filter/$top keys literal.
            url = f"{url}?{urlencode(params, safe='$', quote_via=quote)}"
        while url:
            response = self._send(requests.get, url, headers=self._headers())
            raise_for_status(response, f"GET {url}")
            data = response.json()
            for item in data.get("value", []):
                yield entity.model_validate(item)
            url = data.get("@iot.nextLink")

    def list(self, entity: type[Entity], **query: Any) -> list[Entity]:
        """List all entities of a given type from the istSOS4 server.

        Accepts the same query options as `iter_list()`.
        """
        return list(self.iter_list(entity, **query))

    def patch(self, entity: Entity, commit_message: str | None = None) -> int:
        """Patch an entity on the istSOS4 server.

        Only the fields that are set are sent, so a partial update is just a
        partly-filled entity: Observation(iot_id=7, result=1.5).
        """
        if entity.iot_id is None:
            raise ValueError(
                f"Cannot patch {entity.__class__.__name__} without an iot_id. Please ensure the entity has been created and has a valid iot_id."
            )
        self._check_staplus(entity)
        response = self._send(
            requests.patch,
            f"{self._base_url}{entity.ENDPOINT}({entity.iot_id})",
            json=entity.serialize(),
            headers=self._headers(commit_message),
        )
        raise_for_status(response, f"PATCH {entity.ENDPOINT}({entity.iot_id})")
        return response.status_code

    def bulk_observations(
        self,
        observations: list[Observation],
        force=False,
        commit_message: str | None = None,
    ) -> int:
        """Post observations to /BulkObservations, one dataArray per Datastream.

        Returns the number of observations sent. Requests are split so a single
        one never exceeds the server's parameter limit; duplicates are not
        filtered out, so the server rejects a batch that repeats a
        phenomenonTime already stored for the datastream.
        """
        if not observations:
            raise ValueError("The observations list is empty.")
        rows_by_datastream: dict[int, list[list[Any]]] = {}
        for observation in observations:
            datastream = observation.datastream
            datastream_id = (
                datastream.iot_id
                if isinstance(datastream, Entity)
                else datastream
            )
            if datastream_id is None:
                raise ValueError(
                    "Each observation needs a datastream with an id."
                )
            row = observation.serialize()
            if "phenomenonTime" not in row:
                raise ValueError("Each observation needs a phenomenonTime.")
            rows_by_datastream.setdefault(datastream_id, []).append(
                [
                    row.get("result"),
                    row["phenomenonTime"],
                    row.get("resultTime", row["phenomenonTime"]),
                    row.get("resultQuality"),
                ]
            )

        sent = 0
        for datastream_id, rows in rows_by_datastream.items():
            for offset in range(0, len(rows), MAX_ROWS_PER_BULK):
                batch = rows[offset : offset + MAX_ROWS_PER_BULK]
                response = self._send(
                    requests.post,
                    f"{self._base_url}/BulkObservations",
                    json=[
                        {
                            "Datastream": {"@iot.id": datastream_id},
                            "components": OBSERVATION_COMPONENTS,
                            "dataArray": batch,
                        }
                    ],
                    headers=self._headers(commit_message),
                    params={"force": "true"} if force else None,
                )
                raise_for_status(response, "POST /BulkObservations")
                sent += len(batch)
        return sent
