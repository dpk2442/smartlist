import unittest.mock

import pytest

import smartlist.session


def test_session_constructor():
    session = smartlist.session.Session("mock_input")
    assert session._session == "mock_input"


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


@pytest.mark.asyncio
async def test_get_session(monkeypatch):
    mock_aiohttp_get_session = unittest.mock.AsyncMock()
    mock_aiohttp_get_session.side_effect = ("mock_session",)
    monkeypatch.setattr("smartlist.session.aiohttp_session.get_session", mock_aiohttp_get_session)

    session = await smartlist.session.get_session("request")
    assert isinstance(session, smartlist.session.Session)
    assert session._session == "mock_session"
    mock_aiohttp_get_session.assert_called_once_with("request")
