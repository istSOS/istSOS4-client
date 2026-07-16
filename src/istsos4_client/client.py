from __future__ import annotations
import requests
from .models import Entity, Observation
from ._auth import BearerTokenAuth


class Client:
    """Client for an istSOS4 server instance."""

    def __init__(
        self,
        base_url: str,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = (
            BearerTokenAuth(f"{self._base_url}/Login", username, password)
            if username is not None
            else None
        )
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self, commit_message: str | None = None) -> dict[str, str]:
        headers = self._auth.headers() if self._auth else {}
        if commit_message:
            headers["commit-message"] = commit_message
        return headers

    def post(self, entity: Entity, commit_message: str | None = None) -> int:
        """Post an entity to the istSOS4 server."""
        response = requests.post(
            f"{self._base_url}{entity.ENDPOINT}",
            json=entity.serialize(),
            headers=self._headers(commit_message),
            timeout=self._timeout,
        )
        if response.status_code not in (200, 201):
            print(
                f"Error posting {entity.__class__.__name__}: {response.text}"
            )
        location = response.headers.get("Location")
        if location:
            entity.iot_id = int(location.rsplit("(", 1)[1].rstrip(")"))

        return response.status_code

    def get(self, entity: type[Entity], entity_id: int) -> Entity:
        """Get an entity from the istSOS4 server."""
        response = requests.get(
            f"{self._base_url}{entity.ENDPOINT}/{entity_id}",
            headers=self._headers(),
            timeout=self._timeout,
        )
        response.raise_for_status()
        return entity.model_validate(response.json())

    def list(
        self,
        entity: type[Entity],
        filter: str | None = None,
        select: str | None = None,
        orderby: str | None = None,
        expand: str | None = None,
        top: int | None = None,
    ) -> list[Entity]:
        """List all entities of a given type from the istSOS4 server.

        Query options are passed through as OData parameters, e.g.
        filter="phenomenonTime ge 2026-01-01T00:00:00Z".
        """
        params: dict[str, str | int] | None = {
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
        entities: list[Entity] = []
        url: str | None = f"{self._base_url}{entity.ENDPOINT}"
        while url:
            response = requests.get(
                url,
                params=params,
                headers=self._headers(),
                timeout=self._timeout,
            )
            params = None  # @iot.nextLink already carries query params
            response.raise_for_status()
            data = response.json()
            entities.extend(
                entity.model_validate(item) for item in data.get("value", [])
            )
            url = data.get("@iot.nextLink")
        return entities

    def patch(self, entity: Entity) -> int:
        """Patch an entity on the istSOS4 server."""
        if entity.iot_id is None:
            raise ValueError(
                f"Cannot patch {entity.__class__.__name__} without an iot_id. Please ensure the entity has been created and has a valid iot_id."
            )
        response = requests.patch(
            f"{self._base_url}{entity.ENDPOINT}/{entity.iot_id}",
            json=entity.serialize(),
            headers=self._headers(),
            timeout=self._timeout,
        )
        if response.status_code not in (200, 204):
            print(
                f"Error patching {entity.__class__.__name__}: {response.text}"
            )
        return response.status_code

    @staticmethod
    def _datastream_id(obs: Observation) -> int:
        ds = obs.datastream
        ds_id = ds.iot_id if isinstance(ds, Entity) else ds
        if ds_id is None:
            raise ValueError(
                "Each observation needs a datastream with an id."
            )
        return ds_id

    def bulk_observations(self, observations: list[Observation]) -> int:
        """Post a list of observations to a single Datastream."""
        if not observations:
            raise ValueError("The observations list is empty.")
        datastream_id = self._datastream_id(observations[0])
        if any(
            self._datastream_id(obs) != datastream_id
            for obs in observations
        ):
            raise ValueError(
                "All observations must belong to the same Datastream."
            )
        payload = [obs.serialize() for obs in observations]
        response = requests.post(
            f"{self._base_url}/Datastreams({datastream_id})/Observations",
            json=payload,
            headers=self._headers(),
            timeout=self._timeout,
        )
        if response.status_code not in (200, 201):
            print(f"Error posting observations: {response.text}")
        return response.status_code
