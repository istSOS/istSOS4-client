import time
from unittest.mock import Mock

import pytest
import requests

from istsos4_client._auth import BearerTokenAuth


def token_response(token="tok", expires_in=3600):
    resp = Mock(spec=requests.Response)
    resp.json.return_value = {"access_token": token, "expires_in": expires_in}
    return resp


def auth(post, leeway=30):
    return BearerTokenAuth("http://x/Login", "admin", "admin", post, leeway)


def test_headers_fetches_token_once_while_valid():
    post = Mock(return_value=token_response())
    a = auth(post)
    assert a.headers() == {"Authorization": "Bearer tok"}
    assert a.headers() == {"Authorization": "Bearer tok"}
    assert post.call_count == 1


def test_expires_in_as_duration():
    before = time.time()
    a = auth(Mock(return_value=token_response(expires_in=3600)))
    a.refresh()
    assert before + 3600 <= a._expires_at <= time.time() + 3600


def test_expires_in_as_epoch_timestamp():
    # istSOS4 sends the expiry time itself, not a lifetime in seconds
    expiry = time.time() + 3600
    a = auth(Mock(return_value=token_response(expires_in=expiry)))
    a.refresh()
    assert a._expires_at == expiry


def test_headers_refreshes_within_leeway_of_expiry():
    post = Mock(
        side_effect=[
            token_response("old", expires_in=10),
            token_response("new", expires_in=3600),
        ]
    )
    a = auth(post, leeway=30)
    assert a.headers() == {"Authorization": "Bearer old"}
    # 10s lifetime is inside the 30s leeway, so it is stale on next use
    assert a.headers() == {"Authorization": "Bearer new"}
    assert post.call_count == 2


def test_login_errors_propagate():
    a = auth(Mock(side_effect=requests.HTTPError("401")))
    with pytest.raises(requests.HTTPError):
        a.headers()


def test_posts_password_grant_credentials():
    post = Mock(return_value=token_response())
    auth(post).refresh()
    assert post.call_args.args == ("http://x/Login",)
    assert post.call_args.kwargs["data"] == {
        "grant_type": "password",
        "username": "admin",
        "password": "admin",
    }
