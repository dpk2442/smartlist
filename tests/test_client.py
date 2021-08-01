import copy
import datetime
import unittest.mock

import pytest

import smartlist.client
import smartlist.session


@pytest.fixture
def client():
    config = unittest.mock.Mock()
    db = unittest.mock.Mock()
    session = smartlist.session.Session({})
    return smartlist.client.SpotifyClient(config, db, session)


def test_constructor():
    client = smartlist.client.SpotifyClient("config", "db", "session")
    assert client._request_session == "session"
    assert client._config == "config"
    assert client._db == "db"
    assert client._client_session is None


def test_get_client_session(monkeypatch: pytest.MonkeyPatch):
    mock_session_constructor = unittest.mock.Mock()
    monkeypatch.setattr("smartlist.client.aiohttp.ClientSession", mock_session_constructor)

    client = smartlist.client.SpotifyClient(None, None, None)

    session1 = client._get_client_session()
    assert session1 == mock_session_constructor.return_value
    assert client._client_session == mock_session_constructor.return_value

    session2 = client._get_client_session()
    assert session1 == session2

    mock_session_constructor.assert_called_once_with()


def test_is_access_token_expired(monkeypatch: pytest.MonkeyPatch,
                                 client: smartlist.client.SpotifyClient):
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_datetime = unittest.mock.Mock()
    mock_datetime.now.return_value = now
    monkeypatch.setattr("smartlist.client.datetime.datetime", mock_datetime)

    client._request_session.user_info = dict(
        access_token_expiry="mock_expiry",
    )

    for expiry_delta, expected_result in (
        (-10, True),
        (-5, True),
        (0, True),
        (4, True),
        (5, False),
        (10, False),
    ):
        mock_datetime.fromisoformat.return_value = now + datetime.timedelta(minutes=expiry_delta)
        assert client._is_access_token_expired() == expected_result, "({}, {}) failed".format(
            expiry_delta, expected_result)

    assert mock_datetime.fromisoformat.call_count == 6


@pytest.mark.asyncio
class TestRefreshToken(object):

    async def _test_success(self,
                            include_refresh_token: bool,
                            monkeypatch: pytest.MonkeyPatch,
                            client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = dict(
            access_token="access_token",
            expires_in=10,
        )
        if include_refresh_token:
            mock_response.json.return_value["refresh_token"] = "refresh_token"

        utcnow = datetime.datetime.now(datetime.timezone.utc)
        mock_datetime_datetime = unittest.mock.Mock()
        mock_datetime_datetime.now.return_value = utcnow
        monkeypatch.setattr("smartlist.actions.datetime.datetime", mock_datetime_datetime)
        expected_expiry_time = (utcnow + datetime.timedelta(seconds=10)).isoformat()

        client._config.get.side_effect = ("id", "secret")

        client._client_session = unittest.mock.MagicMock()
        client._client_session.post.return_value.__aenter__.return_value = mock_response

        client._request_session.user_info = dict(
            user_id="user_id",
        )

        await client._refresh_token()

        client._client_session.post.assert_called_once_with(
            "https://accounts.spotify.com/api/token",
            data=dict(
                grant_type="refresh_token",
                refresh_token=client._db.get_refresh_token.return_value,
                client_id="id",
                client_secret="secret",
            )
        )
        mock_response.json.assert_called_once_with()
        client._db.get_refresh_token.assert_called_once_with("user_id")
        if include_refresh_token:
            client._db.upsert_user.assert_called_once_with("user_id", "refresh_token")

        client._config.get.assert_has_calls((
            unittest.mock.call("auth", "client_id"),
            unittest.mock.call("auth", "client_secret"),
        ))

        assert client._request_session.user_info == dict(
            user_id="user_id",
            access_token="access_token",
            access_token_expiry=expected_expiry_time,
        )

    async def test_success_with_new_refresh_token(self,
                                                  monkeypatch: pytest.MonkeyPatch,
                                                  client: smartlist.client.SpotifyClient):
        await self._test_success(True, monkeypatch, client)

    async def test_success_without_new_refresh_token(self,
                                                     monkeypatch: pytest.MonkeyPatch,
                                                     client: smartlist.client.SpotifyClient):
        await self._test_success(False, monkeypatch, client)

    async def test_failed_response(self, client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.AsyncMock()
        mock_response.status = 500

        client._client_session = unittest.mock.MagicMock()
        client._client_session.post.return_value.__aenter__.return_value = mock_response

        client._request_session.user_info = dict(
            user_id="user_id",
        )

        with pytest.raises(smartlist.client.SpotifyAuthorizationException,
                           match="Unable to refresh token, status code"):
            await client._refresh_token()

        client._client_session.post.assert_called_once_with(
            "https://accounts.spotify.com/api/token",
            data=dict(
                grant_type="refresh_token",
                refresh_token=client._db.get_refresh_token.return_value,
                client_id=client._config.get.return_value,
                client_secret=client._config.get.return_value,
            )
        )
        mock_response.json.assert_not_called()
        client._db.get_refresh_token.assert_called_once_with("user_id")


@pytest.mark.asyncio
class TestMakeApiCall(object):

    @pytest.fixture
    def mocked_client(self, client: smartlist.client.SpotifyClient):
        client._client_session = unittest.mock.MagicMock()
        client._request_session.user_info = dict(
            access_token="token",
        )
        client._is_access_token_expired = unittest.mock.Mock()
        client._is_access_token_expired.return_value = False
        client._refresh_token = unittest.mock.AsyncMock()
        return client

    async def test_refreshes_token_if_expired(self, mocked_client: smartlist.client.SpotifyClient):
        async with mocked_client._make_api_call("get", "url"):
            pass

        mocked_client._is_access_token_expired.return_value = True
        async with mocked_client._make_api_call("get", "url"):
            pass

        mocked_client._is_access_token_expired.assert_has_calls((
            unittest.mock.call(),
            unittest.mock.call(),
        ))
        mocked_client._refresh_token.assert_called_once_with()

    async def test_returns_on_success(self, mocked_client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.Mock()
        mock_response.status = 200

        mocked_client._client_session.request.return_value.__aenter__.return_value = mock_response

        async with mocked_client._make_api_call("method", "url") as resp:
            assert resp == mock_response

        mocked_client._client_session.request.assert_called_once_with(
            "method", "url", headers=dict(Authorization="Bearer token"))

    async def test_retries_on_401(self, mocked_client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.Mock()
        mock_response.status = 401

        mocked_client._request_session.user_info = unittest.mock.MagicMock()
        mocked_client._request_session.user_info.__contains__.return_value = True
        mocked_client._request_session.user_info.__getitem__.side_effect = ("token1", "token2")

        request_calls = []

        def request_side_effect(*args, **kwargs):
            request_calls.append(unittest.mock.call(*copy.deepcopy(args), **copy.deepcopy(kwargs)))
            return unittest.mock.DEFAULT

        mocked_client._client_session.request.side_effect = request_side_effect
        mocked_client._client_session.request.return_value.__aenter__.side_effect = (
            mock_response, "response2")

        async with mocked_client._make_api_call("method", "url") as resp:
            assert resp == "response2"

        assert request_calls == [
            unittest.mock.call("method", "url", headers=dict(Authorization="Bearer token1")),
            unittest.mock.call("method", "url", headers=dict(Authorization="Bearer token2")),
        ]


@pytest.mark.asyncio
async def test_close(client: smartlist.client.SpotifyClient):
    await client.close()

    client._client_session = unittest.mock.AsyncMock()
    await client.close()

    client._client_session.close.assert_called_once_with()


@pytest.mark.asyncio
class TestGetFollowedArtists(object):

    async def test_single_page(self, client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = dict(
            artists=dict(
                items=[dict(name="artist2"), dict(name="artist1")],
                next=None,
            ),
        )

        client._make_api_call = unittest.mock.MagicMock()
        client._make_api_call.return_value.__aenter__.return_value = mock_response

        artists = await client.get_followed_artists()

        assert artists == [dict(name="artist1"), dict(name="artist2")]
        client._make_api_call.assert_called_once_with(
            "get", "https://api.spotify.com/v1/me/following?type=artist&limit=10")
        mock_response.json.assert_called_once_with()

    async def test_multiple_pages(self, client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.AsyncMock()
        mock_response.status = 200
        mock_response.json.side_effect = (dict(
            artists=dict(
                items=[dict(name="artist2"), dict(name="artist1")],
                next="page 2 url",
            ),
        ), dict(
            artists=dict(
                items=[dict(name="artist4"), dict(name="artist3")],
                next=None,
            ),
        ))

        client._make_api_call = unittest.mock.MagicMock()
        client._make_api_call.return_value.__aenter__.return_value = mock_response

        artists = await client.get_followed_artists()

        assert artists == [dict(name="artist1"), dict(name="artist2"),
                           dict(name="artist3"), dict(name="artist4")]
        client._make_api_call.assert_has_calls((
            unittest.mock.call(
                "get", "https://api.spotify.com/v1/me/following?type=artist&limit=10"),
            unittest.mock.call().__aenter__(),
            unittest.mock.call().__aenter__().json(),
            unittest.mock.call().__aexit__(None, None, None),
            unittest.mock.call("get", "page 2 url"),
            unittest.mock.call().__aenter__(),
            unittest.mock.call().__aenter__().json(),
            unittest.mock.call().__aexit__(None, None, None),
        ))

    async def test_non_200_response(self, client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.Mock()
        mock_response.status = 500

        client._make_api_call = unittest.mock.MagicMock()
        client._make_api_call.return_value.__aenter__.return_value = mock_response

        with pytest.raises(smartlist.client.SpotifyApiException, match="Error getting artists"):
            await client.get_followed_artists()

        client._make_api_call.assert_called_once_with(
            "get", "https://api.spotify.com/v1/me/following?type=artist&limit=10")


@pytest.mark.asyncio
class TestGetArtistsById(object):

    async def test_single_batch(self, client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.AsyncMock()
        mock_response.status = 200
        mock_response.json.return_value = dict(
            artists=[dict(name="artist2"), dict(name="artist3"), dict(name="artist1")])

        client._make_api_call = unittest.mock.MagicMock()
        client._make_api_call.return_value.__aenter__.return_value = mock_response

        artist_ids = ["spotify:artist:id1", "spotify:artist:id2", "spotify:artist:id3"]
        artists = await client.get_artists_by_ids(artist_ids)

        assert artists == [dict(name="artist1"), dict(name="artist2"), dict(name="artist3")]
        mock_response.json.assert_called_once_with()
        client._make_api_call.assert_called_once_with(
            "get",  "https://api.spotify.com/v1/artists?ids=id1,id2,id3")
        client._make_api_call.return_value.__aenter__.assert_called_once_with()

    async def test_multiple_batches(self,
                                    monkeypatch: pytest.MonkeyPatch,
                                    client: smartlist.client.SpotifyClient):
        monkeypatch.setattr("smartlist.client.ARTIST_IDS_BATCH_SIZE", 2)

        mock_response = unittest.mock.AsyncMock()
        mock_response.status = 200
        mock_response.json.side_effect = (
            dict(artists=[dict(name="artist2"), dict(name="artist1")]),
            dict(artists=[dict(name="artist3")]),
        )

        client._make_api_call = unittest.mock.MagicMock()
        client._make_api_call.return_value.__aenter__.return_value = mock_response

        artist_ids = ["spotify:artist:id1", "spotify:artist:id2", "spotify:artist:id3"]
        artists = await client.get_artists_by_ids(artist_ids)

        assert artists == [dict(name="artist1"), dict(name="artist2"), dict(name="artist3")]
        client._make_api_call.assert_has_calls((
            unittest.mock.call("get", "https://api.spotify.com/v1/artists?ids=id1,id2"),
            unittest.mock.call().__aenter__(),
            unittest.mock.call().__aenter__().json(),
            unittest.mock.call().__aexit__(None, None, None),
            unittest.mock.call("get", "https://api.spotify.com/v1/artists?ids=id3"),
            unittest.mock.call().__aenter__(),
            unittest.mock.call().__aenter__().json(),
            unittest.mock.call().__aexit__(None, None, None),
        ))

    async def test_non_200_response(self, client: smartlist.client.SpotifyClient):
        mock_response = unittest.mock.AsyncMock()
        mock_response.status = 500

        client._make_api_call = unittest.mock.MagicMock()
        client._make_api_call.return_value.__aenter__.return_value = mock_response

        artist_ids = ["spotify:artist:id1", "spotify:artist:id2", "spotify:artist:id3"]
        with pytest.raises(smartlist.client.SpotifyApiException,
                           match="Error getting artists by id"):
            await client.get_artists_by_ids(artist_ids)

        mock_response.json.assert_not_called()
        client._make_api_call.assert_called_once_with(
            "get",  "https://api.spotify.com/v1/artists?ids=id1,id2,id3")
        client._make_api_call.return_value.__aenter__.assert_called_once_with()
