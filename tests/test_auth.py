import time
from unittest.mock import Mock, patch

import pytest
import requests

from istsos4_client._auth import BearerTokenAuth


def make_token_response(token="tok", expires_in=3600, status=200):
    resp = Mock(spec=requests.Response)
    resp.status_code = status
    resp.json.return_value = {
        "access_token": token,
        "expires_in": expires_in,
    }
    resp.raise_for_status.side_effect = (
        None if status < 400 else requests.HTTPError(f"{status}")
    )
    return resp


def auth():
    return BearerTokenAuth("http://x/Login", "admin", "admin")


def test_headers_fetches_token_once_while_valid():
    a = auth()
    with patch(
        "istsos4_client._auth.requests.post",
        return_value=make_token_response(),
    ) as post:
        assert a.headers() == {"Authorization": "Bearer tok"}
        assert a.headers() == {"Authorization": "Bearer tok"}
    assert post.call_count == 1


def test_expires_at_is_absolute_not_duration():
    a = auth()
    before = time.time()
    with patch(
        "istsos4_client._auth.requests.post",
        return_value=make_token_response(expires_in=3600),
    ):
        a.refresh()
    assert before + 3600 <= a._expires_at <= time.time() + 3600


def test_expires_in_as_epoch_timestamp():
    # istSOS4 sends the expiry time itself, not a lifetime in seconds
    expiry = time.time() + 3600
    a = auth()
    with patch(
        "istsos4_client._auth.requests.post",
        return_value=make_token_response(expires_in=expiry),
    ):
        a.refresh()
    assert a._expires_at == expiry


def test_headers_refreshes_within_leeway_of_expiry():
    a = BearerTokenAuth("http://x/Login", "admin", "admin", leeway=30)
    with patch(
        "istsos4_client._auth.requests.post",
        side_effect=[
            make_token_response("old", expires_in=10),
            make_token_response("new", expires_in=3600),
        ],
    ) as post:
        assert a.headers() == {"Authorization": "Bearer old"}
        # 10s lifetime is inside the 30s leeway, so it is stale on next use
        assert a.headers() == {"Authorization": "Bearer new"}
    assert post.call_count == 2


def test_refresh_raises_on_http_error():
    a = auth()
    with patch(
        "istsos4_client._auth.requests.post",
        return_value=make_token_response(status=401),
    ):
        with pytest.raises(requests.HTTPError):
            a.headers()


def test_posts_password_grant_credentials():
    a = auth()
    with patch(
        "istsos4_client._auth.requests.post",
        return_value=make_token_response(),
    ) as post:
        a.refresh()
    assert post.call_args.kwargs["data"] == {
        "grant_type": "password",
        "username": "admin",
        "password": "admin",
    }
