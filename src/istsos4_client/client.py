from __future__ import annotations

import builtins
import time
from collections.abc import Iterator
from functools import partial
from typing import Any
from urllib.parse import quote, urlencode

import requests

from ._auth import BearerTokenAuth
from .models import Entity, EntityT, Observation

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


def _odata_query(**options: Any) -> str:
    """'?$key=value&...' for the OData options that are set, '' if none."""
    params = {
        f"${key}": value for key, value in options.items() if value is not None
    }
    if not params:
        return ""
    # requests encodes spaces as '+' by default; OData servers expect %20.
    # safe="$" keeps the OData $filter/$top keys literal.
    return f"?{urlencode(params, safe='$', quote_via=quote)}"


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
        self._session = requests.Session()  # reuses connections
        self._timeout = timeout
        self._staplus = staplus
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._auth = (
            BearerTokenAuth(
                f"{self._base_url}/Login",
                username,
                password,
                post=partial(self._request, "POST"),
            )
            if username is not None
            else None
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    def close(self) -> None:
        """Close the pooled connections. Or use the client as a context
        manager: `with Client(url) as client: ...`."""
        self._session.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _headers(self, commit_message: str | None = None) -> dict[str, str]:
        headers = self._auth.headers() if self._auth else {}
        if commit_message:
            headers["commit-message"] = commit_message
        return headers

    def _request(
        self, method: str, url: str, **kwargs: Any
    ) -> requests.Response:
        """Send a request with the client's timeout, retrying as described in
        __init__. Raises requests.HTTPError, with the server's message, on a
        non-2xx response, or the last connection error."""
        for attempt in range(self._max_retries + 1):
            last = attempt == self._max_retries
            try:
                response = self._session.request(
                    method, url, timeout=self._timeout, **kwargs
                )
            except (requests.ConnectionError, requests.Timeout):
                if last:
                    raise
            else:
                if last or response.status_code not in RETRY_STATUSES:
                    raise_for_status(response, method)
                    return response
            time.sleep(self._retry_delay)
        raise AssertionError("unreachable")

    def _check_staplus(self, entity: Entity | type[Entity]) -> None:
        if not self._staplus and _uses_staplus(entity):
            raise ValueError(
                "STAplus entities need Client(..., staplus=True)."
            )

    def post(
        self, entity: EntityT, *, commit_message: str | None = None
    ) -> EntityT:
        """Create an entity on the server and return it, with iot_id set
        from the response."""
        self._check_staplus(entity)
        response = self._request(
            "POST",
            f"{self._base_url}{entity.ENDPOINT}",
            json=entity.serialize(),
            headers=self._headers(commit_message),
        )
        location = response.headers.get("Location")
        if location:
            entity.iot_id = int(location.rsplit("(", 1)[1].rstrip(")"))
        return entity

    def get(
        self,
        entity: type[EntityT],
        entity_id: int,
        *,
        expand: str | None = None,
        filter: str | None = None,
    ) -> EntityT:
        """Get an entity by id.

        `expand` and `filter` are passed through as OData $expand and $filter,
        e.g. expand="Datastream".
        """
        self._check_staplus(entity)
        url = f"{self._base_url}{entity.ENDPOINT}({entity_id})"
        url += _odata_query(expand=expand, filter=filter)
        response = self._request("GET", url, headers=self._headers())
        return entity.deserialize(response.json())

    def iter_list(
        self,
        entity: type[EntityT],
        *,
        filter: str | None = None,
        select: str | None = None,
        orderby: str | None = None,
        expand: str | None = None,
        top: int | None = None,
    ) -> Iterator[EntityT]:
        """Yield entities one page at a time, following @iot.nextLink.

        Use this instead of `list()` for collections too large to hold in
        memory (observation histories, migrations, ...).

        Query options are passed through as OData parameters, e.g.
        filter="phenomenonTime ge 2026-01-01T00:00:00Z".
        """
        self._check_staplus(entity)
        url: str | None = f"{self._base_url}{entity.ENDPOINT}" + _odata_query(
            filter=filter,
            select=select,
            orderby=orderby,
            expand=expand,
            top=top,
        )
        while url:
            data = self._request("GET", url, headers=self._headers()).json()
            for item in data.get("value", []):
                yield entity.deserialize(item)
            url = data.get("@iot.nextLink")

    # `builtins.list` below: inside this class `list` is the method.
    def list(
        self, entity: type[EntityT], **query: Any
    ) -> builtins.list[EntityT]:
        """List all entities of a given type.

        Accepts the same query options as `iter_list()`.
        """
        return list(self.iter_list(entity, **query))

    def patch(
        self,
        entity: Entity,
        *,
        commit_message: str | None = None,
        filter: str | None = None,
    ) -> None:
        """Update an entity on the server.

        Only the fields that are set are sent, so a partial update is just a
        partly-filled entity: Observation(iot_id=7, result=1.5).

        `filter` is passed through as OData $filter, e.g.
        filter="phenomenonTime eq '2026-07-15T10:00:00Z'".
        """
        if entity.iot_id is None:
            raise ValueError(
                f"Cannot patch {type(entity).__name__} without an iot_id; "
                "get() or post() it first."
            )
        self._check_staplus(entity)
        self._request(
            "PATCH",
            f"{self._base_url}{entity.ENDPOINT}({entity.iot_id})"
            + _odata_query(filter=filter),
            json=entity.serialize(),
            headers=self._headers(commit_message),
        )

    def delete(
        self,
        entity: type[Entity],
        entity_id: int,
        *,
        commit_message: str | None = None,
    ) -> None:
        """Delete an entity by id."""
        self._check_staplus(entity)
        self._request(
            "DELETE",
            f"{self._base_url}{entity.ENDPOINT}({entity_id})",
            headers=self._headers(commit_message),
        )

    def bulk_observations(
        self,
        observations: builtins.list[Observation],
        *,
        force: bool = False,
        commit_message: str | None = None,
    ) -> int:
        """Post observations to /BulkObservations, one dataArray per Datastream.

        Returns the number of observations sent. Requests are split so a single
        one never exceeds the server's parameter limit; duplicates are not
        filtered out, so the server rejects a batch that repeats a
        phenomenonTime already stored for the datastream. force=True adds
        ?force=true to each request, passed through to istSOS4.
        A missing resultTime defaults to the phenomenonTime.
        """
        if not observations:
            raise ValueError("The observations list is empty.")
        rows_by_datastream: dict[int, builtins.list[builtins.list[Any]]] = {}
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
                self._request(
                    "POST",
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
                sent += len(batch)
        return sent
