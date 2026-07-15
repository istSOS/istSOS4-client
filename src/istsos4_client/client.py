from __future__ import annotations
import requests
from .models import Entity
from .auth import BearerTokenAuth


class Client:
    """Client for an istSOS4 server instance."""

    def __init__(
        self,
        base_url: str,
        auth: BearerTokenAuth | None = None,
        timeout: float = 30.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    def __repr__(self) -> str:
        return f"Client(base_url={self._base_url!r}, auth={self._auth!r}, timeout={self._timeout!r})"

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

    def get(self, entity_class: type[Entity], entity_id: int) -> Entity:
        """Get an entity from the istSOS4 server."""
        response = requests.get(
            f"{self._base_url}{entity_class.ENDPOINT}/{entity_id}",
            headers=self._headers(),
            timeout=self._timeout,
        )
        response.raise_for_status()
        return entity_class.model_validate(response.json())

    def list(self, entity_class: type[Entity]) -> list[Entity]:
        """List all entities of a given type from the istSOS4 server."""
        entities: list[Entity] = []
        url: str | None = f"{self._base_url}{entity_class.ENDPOINT}"
        while url:
            response = requests.get(
                url,
                headers=self._headers(),
                timeout=self._timeout,
            )
            response.raise_for_status()
            data = response.json()
            entities.extend(
                entity_class.model_validate(item)
                for item in data.get("value", [])
            )
            url = data.get("@iot.nextLink")
        return entities
