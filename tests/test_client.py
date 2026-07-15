from unittest.mock import Mock, patch

import pytest
import requests

from istsos4_client import Client
from istsos4_client.models import User


def make_response(json_data=None, status=200, headers=None):
    resp = Mock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.json.return_value = json_data
    resp.raise_for_status.side_effect = (
        requests.HTTPError(f"{status}") if status >= 400 else None
    )
    return resp


def test_client_strips_trailing_slash():
    c = Client("http://example.com/v1.1/")
    assert c.base_url == "http://example.com/v1.1"


# ---------------------------------------------------------------------------
# headers
# ---------------------------------------------------------------------------


def test_headers_without_auth():
    assert Client("http://x")._headers() == {}


def test_headers_with_commit_message():
    assert Client("http://x")._headers("why") == {"commit-message": "why"}


def test_headers_with_auth():
    auth = Mock()
    auth.headers.return_value = {"Authorization": "Bearer tok"}
    c = Client("http://x", auth=auth)
    assert c._headers("why") == {
        "Authorization": "Bearer tok",
        "commit-message": "why",
    }


# ---------------------------------------------------------------------------
# post
# ---------------------------------------------------------------------------


def test_post_sets_iot_id_from_location():
    user = User(username="a", role="viewer")
    resp = make_response(
        status=201, headers={"Location": "http://x/v1.1/Users(7)"}
    )
    with patch(
        "istsos4_client.client.requests.post", return_value=resp
    ) as post:
        status = Client("http://x/v1.1").post(user, commit_message="add a")
    assert status == 201
    assert user.iot_id == 7
    assert post.call_args.args[0] == "http://x/v1.1/Users"
    assert post.call_args.kwargs["json"] == user.serialize()
    assert post.call_args.kwargs["headers"] == {"commit-message": "add a"}


def test_post_error_keeps_iot_id_none(capsys):
    user = User(username="a", role="viewer")
    resp = make_response(status=400)
    resp.text = "bad request"
    with patch("istsos4_client.client.requests.post", return_value=resp):
        status = Client("http://x").post(user)
    assert status == 400
    assert user.iot_id is None
    assert "bad request" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def test_get_returns_entity():
    resp = make_response({"id": 3, "username": "a", "role": "viewer"})
    with patch(
        "istsos4_client.client.requests.get", return_value=resp
    ) as get:
        user = Client("http://x/v1.1").get(User, 3)
    assert isinstance(user, User)
    assert user.iot_id == 3
    assert get.call_args.args[0] == "http://x/v1.1/Users/3"


def test_get_raises_on_http_error():
    resp = make_response(status=404)
    with patch("istsos4_client.client.requests.get", return_value=resp):
        with pytest.raises(requests.HTTPError):
            Client("http://x").get(User, 99)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


def test_list_single_page():
    resp = make_response(
        {"value": [{"id": 1, "username": "a", "role": "viewer"}]}
    )
    with patch("istsos4_client.client.requests.get", return_value=resp):
        users = Client("http://x").list(User)
    assert [u.iot_id for u in users] == [1]


def test_list_empty_value():
    with patch(
        "istsos4_client.client.requests.get",
        return_value=make_response({"value": []}),
    ):
        assert Client("http://x").list(User) == []


def test_list_follows_next_link():
    page1 = make_response(
        {
            "value": [{"id": 1, "username": "a", "role": "viewer"}],
            "@iot.nextLink": "http://x/v1.1/Users?$skip=1",
        }
    )
    page2 = make_response(
        {"value": [{"id": 2, "username": "b", "role": "viewer"}]}
    )
    with patch(
        "istsos4_client.client.requests.get", side_effect=[page1, page2]
    ) as get:
        users = Client("http://x/v1.1").list(User)
    assert [u.iot_id for u in users] == [1, 2]
    assert get.call_args_list[1].args[0] == "http://x/v1.1/Users?$skip=1"


def test_list_raises_on_http_error():
    with patch(
        "istsos4_client.client.requests.get",
        return_value=make_response(status=500),
    ):
        with pytest.raises(requests.HTTPError):
            Client("http://x").list(User)
