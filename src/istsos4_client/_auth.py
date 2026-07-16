import time
import requests


class BearerTokenAuth:
    """Bearer token authentication for istSOS4 client."""

    def __init__(
        self, url: str, username: str, password: str, leeway: int = 30
    ):
        self._token_url = url
        self._user = username
        self._pwd = password
        self._leeway = leeway
        self._token: str | None = None
        self._expires_at: float = 0.0

    def headers(self) -> dict[str, str]:
        if (
            self._token is None
            or time.time() > self._expires_at - self._leeway
        ):
            self.refresh()
        return {"Authorization": f"Bearer {self._token}"}

    def refresh(self) -> None:
        resp = requests.post(
            self._token_url,
            data={
                "grant_type": "password",
                "username": self._user,
                "password": self._pwd,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._expires_at = float(data["expires_in"])
