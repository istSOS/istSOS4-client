"""STAplus entities (istSOS4 staplus branch).

Kept out of the base models so plain istSOS4 code never sees them; the client
only accepts them when built with Client(..., staplus=True).
"""

from typing import Any, ClassVar

from pydantic import Field, field_serializer

from . import models
from .models import Entity, _link_or_embed


class Party(Entity):
    """Who owns a Datastream."""

    ENDPOINT: ClassVar[str] = "/Parties"
    STAPLUS: ClassVar[bool] = True

    role: str
    display_name: str | None = None
    description: str | None = None
    auth_id: str | None = None


class Datastream(models.Datastream):
    """Datastream with the STAplus Party relation."""

    STAPLUS: ClassVar[bool] = True

    party: int | Party | None = Field(None, alias="Party")

    @field_serializer("party")
    def _rel_party(self, v: Any) -> Any:
        return _link_or_embed(v)
