import unittest.mock

import pytest

import smartlist.session


def test_session_constructor():
    session = smartlist.session.Session("mock_input")
    assert session._session == "mock_input"


def test_flash():
    session = smartlist.session.Session({})

    assert session.pop_flashes() == []
    session.add_flash("f1")
    session.add_flash("f2")
    assert session.pop_flashes() == ["f1", "f2"]
    assert session.pop_flashes() == []


@pytest.mark.parametrize("attr", ["auth_state", "user_info"])
def test_properties(attr):
    session = smartlist.session.Session({})

    assert getattr(session, attr) is None
    delattr(session, attr)
    assert getattr(session, attr) is None
    setattr(session, attr, "test_value")
    assert getattr(session, attr) == "test_value"
    delattr(session, attr)
    assert getattr(session, attr) is None


def test_user_info_acccessors():
    session = smartlist.session.Session({})

    assert session.user_id is None
    assert session.access_token is None
    assert session.access_token_expiry is None

    session.user_info = dict(
        user_id="user_id",
        access_token="access_token",
        access_token_expiry="access_token_expiry",
    )

    assert session.user_id == "user_id"
    assert session.access_token == "access_token"
    assert session.access_token_expiry == "access_token_expiry"


@pytest.mark.asyncio
async def test_get_session(monkeypatch):
    mock_aiohttp_get_session = unittest.mock.AsyncMock()
    mock_aiohttp_get_session.side_effect = ("mock_session",)
    monkeypatch.setattr("smartlist.session.aiohttp_session.get_session", mock_aiohttp_get_session)

    session = await smartlist.session.get_session("request")
    assert isinstance(session, smartlist.session.Session)
    assert session._session == "mock_session"
    mock_aiohttp_get_session.assert_called_once_with("request")
