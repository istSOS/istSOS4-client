import time
from collections.abc import Callable

import requests


class BearerTokenAuth:
    """Bearer token authentication for istSOS4 client.

    `post(url, **kwargs)` sends the login request. The client passes its own,
    so login gets the same timeout, retries and error messages as every other
    request.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str | None,
        post: Callable[..., requests.Response],
        leeway: int = 30,
    ):
        self._token_url = url
        self._user = username
        self._pwd = password
        self._post = post
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
        data = self._post(
            self._token_url,
            data={
                "grant_type": "password",
                "username": self._user,
                "password": self._pwd,
            },
        ).json()
        self._token = data["access_token"]
        expires_in = float(data["expires_in"])
        # istSOS4 sends the expiry as a Unix timestamp, other servers send a
        # lifetime in seconds. Past 1e9 (year 2001) it can only be a timestamp.
        self._expires_at = (
            expires_in if expires_in > 1e9 else time.time() + expires_in
        )
