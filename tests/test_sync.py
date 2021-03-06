import datetime
import operator
import typing
import unittest.mock

import pytest

import smartlist.client
import smartlist.sync


@pytest.mark.asyncio
async def test_sync_artists(monkeypatch: pytest.MonkeyPatch):
    mock_sync_artist = unittest.mock.AsyncMock()
    monkeypatch.setattr("smartlist.sync.sync_artist", mock_sync_artist)

    mock_ws = unittest.mock.AsyncMock()
    mock_db = unittest.mock.Mock()
    mock_db.get_artists.return_value = ["a1", "a2", "a3"]

    await smartlist.sync.sync_artists(mock_ws, "config", mock_db, "user_id", "client")

    mock_ws.send_json.assert_called_once_with(dict(type="start"))
    mock_db.get_artists.assert_called_once_with("user_id")
    mock_sync_artist.assert_has_calls((
        unittest.mock.call(mock_ws, "config", mock_db, "user_id", "client", "a1"),
        unittest.mock.call(mock_ws, "config", mock_db, "user_id", "client", "a2"),
        unittest.mock.call(mock_ws, "config", mock_db, "user_id", "client", "a3"),
    ))


@pytest.mark.asyncio
class TestSyncArtist(object):

    @pytest.fixture
    def mock_processing_functions(self, monkeypatch: pytest.MonkeyPatch):
        def create_mock(name, constructor=unittest.mock.Mock):
            mock = constructor()
            monkeypatch.setattr("smartlist.sync.{}".format(name), mock)
            return mock

        return (
            create_mock("filter_albums"),
            create_mock("merge_album_lists"),
            create_mock("convert_album_list_to_track_list"),
            create_mock("get_or_create_playlist", constructor=unittest.mock.AsyncMock),
            create_mock("replace_playlist_tracks", constructor=unittest.mock.AsyncMock),
            create_mock("update_artist_playlist_info"),
        )

    async def test_success(self, mock_processing_functions: typing.Tuple[unittest.mock.Mock, ...]):
        (
            mock_filter_albums,
            mock_merge_album_lists,
            mock_convert_album_list_to_track_list,
            mock_get_or_create_playlist,
            mock_replace_playlist_tracks,
            mock_update_artist_playlist_info,
        ) = mock_processing_functions

        now = datetime.datetime.now(datetime.timezone.utc)
        mock_filter_albums.side_effect = ["filtered_saved_albums", "filtered_saved_tracks"]
        mock_merge_album_lists.return_value = "merged_album_list"
        mock_convert_album_list_to_track_list.return_value = [
            smartlist.client.Track("t1", None, None, None, None, None),
            smartlist.client.Track("t2", None, None, None, None, None),
        ]
        mock_get_or_create_playlist.return_value = "playlist_id"
        mock_update_artist_playlist_info.return_value = now

        mock_client = unittest.mock.AsyncMock()
        mock_client.get_saved_albums.return_value = "saved_albums"
        mock_client.get_saved_tracks.return_value = "saved_tracks"

        mock_ws = unittest.mock.AsyncMock()

        await smartlist.sync.sync_artist(
            mock_ws, "config", "db", "user_id", mock_client, dict(id="artist_id"))

        mock_filter_albums.assert_has_calls((
            unittest.mock.call("artist_id", "saved_albums"),
            unittest.mock.call("artist_id", "saved_tracks"),
        ))
        mock_merge_album_lists.assert_called_once_with(
            "filtered_saved_albums", "filtered_saved_tracks")
        mock_convert_album_list_to_track_list.assert_called_once_with("merged_album_list")
        mock_get_or_create_playlist.assert_called_once_with(
            "config", "user_id", mock_client, dict(id="artist_id"))
        mock_replace_playlist_tracks.assert_called_once_with(
            mock_client, "playlist_id", mock_convert_album_list_to_track_list.return_value)
        mock_update_artist_playlist_info.assert_called_once_with(
            "db", "user_id", dict(id="artist_id"), "playlist_id")

        mock_client.get_saved_albums.assert_called_once_with()
        mock_client.get_saved_tracks.assert_called_once_with()

        mock_ws.send_json.assert_has_calls((
            unittest.mock.call(dict(type="artistStart", artistId="artist_id")),
            unittest.mock.call(dict(type="artistComplete", artistId="artist_id",
                               lastUpdated=now.isoformat())),
        ))

    async def test_exception(self,
                             mock_processing_functions: typing.Tuple[unittest.mock.Mock, ...]):
        (
            mock_filter_albums,
            mock_merge_album_lists,
            mock_convert_album_list_to_track_list,
            mock_get_or_create_playlist,
            mock_replace_playlist_tracks,
            mock_update_artist_playlist_info,
        ) = mock_processing_functions

        mock_client = unittest.mock.AsyncMock()
        mock_client.get_saved_albums.side_effect = Exception("test exception")

        mock_ws = unittest.mock.AsyncMock()

        await smartlist.sync.sync_artist(
            mock_ws, None, None, None, mock_client, dict(id="artist_id"))

        mock_filter_albums.assert_not_called()
        mock_merge_album_lists.assert_not_called()
        mock_convert_album_list_to_track_list.assert_not_called()
        mock_get_or_create_playlist.assert_not_called()
        mock_replace_playlist_tracks.assert_not_called()
        mock_update_artist_playlist_info.assert_not_called()

        mock_client.get_saved_albums.assert_called_once_with()
        mock_client.get_saved_tracks.assert_not_called()

        mock_ws.send_json.assert_has_calls((
            unittest.mock.call(dict(type="artistStart", artistId="artist_id")),
            unittest.mock.call(
                dict(type="artistError", artistId="artist_id", error="Unable to sync")),
        ))


def test_filter_albums():
    def _build_track(track_name, artist_names):
        return smartlist.client.Track(
            track_name,
            track_name,
            None,
            None,
            [smartlist.client.Artist(artist_name, artist_name) for artist_name in artist_names],
            None,
        )

    # album with only matching tracks
    album1 = smartlist.client.Album("album1", None, None, None, None)
    album1.add_track(_build_track("t1", ["a1"]))
    album1.add_track(_build_track("t2", ["a1"]))

    # album with no matching tracks
    album2 = smartlist.client.Album("album4", None, None, None, None)
    album2.add_track(_build_track("t1", ["a2"]))
    album2.add_track(_build_track("t2", ["a2"]))

    # album with some matching tracks
    album3 = smartlist.client.Album("album2", None, None, None, None)
    album3.add_track(_build_track("t1", ["a1"]))
    album3.add_track(_build_track("t2", ["a2"]))

    # album with multi artist tracks
    album4 = smartlist.client.Album("album3", None, None, None, None)
    album4.add_track(_build_track("t1", ["a2", "a3"]))
    album4.add_track(_build_track("t2", ["a1", "a2"]))

    filtered_albums = smartlist.sync.filter_albums("a1", [album1, album2, album3, album4])

    assert filtered_albums == [album1, album3, album4]
    assert list(map(operator.attrgetter("name"), album1.tracks.values())) == ["t1", "t2"]
    assert list(map(operator.attrgetter("name"), album2.tracks.values())) == []
    assert list(map(operator.attrgetter("name"), album3.tracks.values())) == ["t1"]
    assert list(map(operator.attrgetter("name"), album4.tracks.values())) == ["t2"]


def test_merge_album_lists():
    def _build_album(album_name, track_names):
        album = smartlist.client.Album(album_name, None, None, album_name, None)
        for track_name in track_names:
            album.add_track(smartlist.client.Track(track_name, track_name, None, None, None, None))
        return album

    album_list1 = [
        # only in list 1
        _build_album("album1", ["t1", "t2"]),
        # duplicates in list 2
        _build_album("album2", ["t1", "t2"]),
        # disjoint from list 2
        _build_album("album3", ["t1", "t2"]),
    ]

    album_list2 = [
        # only in list 2
        _build_album("album4", ["t1"]),
        # duplicates in list 1
        _build_album("album2", ["t1"]),
        # disjoint from list 1
        _build_album("album3", ["t3", "t4"]),
    ]

    merged_list = smartlist.sync.merge_album_lists(album_list1, album_list2)

    assert tuple(map(lambda a: (
        a.name,
        tuple(map(operator.attrgetter("name"), a.tracks.values()))
    ), merged_list)) == (
        ("album1", ("t1", "t2")),
        ("album2", ("t1", "t2")),
        ("album3", ("t1", "t2", "t3", "t4")),
        ("album4", ("t1",)),
    )


def test_convert_album_list_to_track_list():
    def _build_album(album_name, release_date, track_builders):
        album = smartlist.client.Album(album_name, release_date, "day", None, None)
        for track_builder in track_builders:
            album.add_track(track_builder(album))
        return album

    def _build_track(album, track_name, disc_number, track_number):
        return smartlist.client.Track(
            track_name, track_name, disc_number, track_number, None, album)

    albums = [
        _build_album("album1", "2021-06-01", (
            lambda a: _build_track(a, "t1", 1, 1),
        )),
        _build_album("album2", "2021-01-01", (
            lambda a: _build_track(a, "t2", 1, 2),
            lambda a: _build_track(a, "t1", 1, 1),
        )),
        _build_album("album3", "2021-03-30", (
            lambda a: _build_track(a, "d2t1", 2, 1),
            lambda a: _build_track(a, "d1t1", 1, 1),
            lambda a: _build_track(a, "d1t2", 1, 2),
            lambda a: _build_track(a, "d2t2", 2, 2),
            lambda a: _build_track(a, "d1t3", 1, 3),
        )),
    ]

    track_list = smartlist.sync.convert_album_list_to_track_list(albums)

    assert tuple(map(lambda a: (
        a.album.name,
        a.name,
    ), track_list)) == (
        ("album2", "t1"),
        ("album2", "t2"),
        ("album3", "d1t1"),
        ("album3", "d1t2"),
        ("album3", "d1t3"),
        ("album3", "d2t1"),
        ("album3", "d2t2"),
        ("album1", "t1"),
    )


@pytest.mark.asyncio
class TestGetOrCreatePlaylist(object):

    async def test_playlist_exists(self):
        mock_client = unittest.mock.AsyncMock()

        playlist_id = await smartlist.sync.get_or_create_playlist(
            None, None, mock_client, dict(playlist_id="playlist_id"))

        assert playlist_id == "playlist_id"
        mock_client.get_playlist.assert_called_once_with("playlist_id")

    @pytest.mark.parametrize("get_fails", (True, False), ids=("GetFails", "NoExisting"))
    async def test_playlist_created(self, get_fails):
        mock_config = unittest.mock.Mock()
        mock_config.get.side_effect = ("NameTemplate: {name}", "DescriptionTemplate: {name}")
        mock_client = unittest.mock.AsyncMock()
        mock_client.get_artists_by_ids.return_value = [dict(name="artist_name")]
        mock_client.create_playlist.return_value = dict(uri="created_playlist_id")

        artist = dict(id="artist_id", playlist_id=None)
        if get_fails:
            artist["playlist_id"] = "existing_playlist_id"
            mock_client.get_playlist.side_effect = smartlist.client.SpotifyApiException(
                "Error getting playlist")

        playlist_id = await smartlist.sync.get_or_create_playlist(
            mock_config, "user_id", mock_client, artist)

        assert playlist_id == "created_playlist_id"
        mock_config.get.assert_has_calls((
            unittest.mock.call("playlist", "name_template", fallback="SmartList: {name}"),
            unittest.mock.call(
                "playlist", "description_template",
                fallback="An automatic playlist for \"{name}\" created by SmartList"),
        ))
        mock_client.get_artists_by_ids.assert_called_once_with(["artist_id"])
        mock_client.create_playlist.assert_called_once_with(
            "user_id", "NameTemplate: artist_name", "DescriptionTemplate: artist_name")
        if get_fails:
            mock_client.get_playlist.assert_called_once_with("existing_playlist_id")


@pytest.mark.asyncio
async def test_replace_playlist_tracks():
    mock_client = unittest.mock.AsyncMock()
    await smartlist.sync.replace_playlist_tracks(mock_client, "playlist_id", "tracks")

    mock_client.clear_playlist.assert_called_once_with("playlist_id")
    mock_client.add_items_to_playlist.assert_called_once_with("playlist_id", "tracks")


def test_update_artist_playlist_info(monkeypatch: pytest.MonkeyPatch):
    mock_datetime_datetime = unittest.mock.Mock()
    monkeypatch.setattr("smartlist.actions.datetime.datetime", mock_datetime_datetime)

    mock_db = unittest.mock.Mock()
    last_updated = smartlist.sync.update_artist_playlist_info(
        mock_db, "user_id", dict(id="artist_id"), "playlist_id")

    assert last_updated == mock_datetime_datetime.now.return_value
    mock_datetime_datetime.now.assert_called_once_with(datetime.timezone.utc)
    mock_db.update_artist_playlist.assert_called_once_with(
        "user_id", "artist_id", "playlist_id",
        mock_datetime_datetime.now.return_value.isoformat.return_value)
