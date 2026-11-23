"""
Tests for Auto-Updater module.
"""

from unittest.mock import MagicMock, patch
import wx

from novel_reader.updater import (
    CURRENT_VERSION,
    UpdateDialog,
    check_for_updates,
    get_install_paths,
    parse_version,
)


def test_parse_version() -> None:
    assert parse_version("1.0.0") == (1, 0, 0)
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("v2.1") == (2, 1, 0)
    assert parse_version("26.0") == (26, 0, 0)
    assert parse_version("v26.0") == (26, 0, 0)
    assert parse_version("") == (0, 0, 0)
    assert parse_version("v26.0") > parse_version("1.0.0")
    assert parse_version("v2.0.0") > parse_version("v1.9.9")
    assert parse_version("1.0.0") == parse_version("v1.0.0")


def test_get_install_paths() -> None:
    paths = get_install_paths()
    assert "mode" in paths
    assert "install_dir" in paths
    assert paths["mode"] in ("source", "standalone")


def test_check_for_updates_available() -> None:
    mock_payload = {
        "tag_name": "v2.0.0",
        "name": "Accessible Novel Reader v2.0.0",
        "published_at": "2026-12-01T12:00:00Z",
        "body": "Fixed bugs and added enhancements.",
        "html_url": "https://github.com/test/releases/v2.0.0",
        "assets": [
            {
                "name": "novel_reader_v2.0.0.zip",
                "browser_download_url": "https://github.com/test/releases/download/v2.0.0/novel_reader.zip",
                "size": 5242880,
            }
        ],
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        info = check_for_updates(current_version="1.0.0", repo="test/repo")
        assert info is not None
        assert info["update_available"] is True
        assert info["latest_version"] == "v2.0.0"
        assert info["download_size"] == 5242880
        assert "Fixed bugs" in info["changelog"]


def test_check_for_updates_none_when_up_to_date() -> None:
    mock_payload = {
        "tag_name": "v1.0.0",
        "name": "Release v1.0.0",
        "assets": [],
    }

    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_payload
        mock_get.return_value = mock_resp

        info = check_for_updates(current_version="1.0.0", repo="test/repo")
        assert info is None


def test_check_for_updates_network_failure_handled() -> None:
    with patch("requests.get", side_effect=Exception("Connection refused")):
        info = check_for_updates(current_version="1.0.0", repo="test/repo")
        assert info is None


def test_update_dialog_creation() -> None:
    app = wx.App(False)
    sample_info = {
        "update_available": True,
        "current_version": "1.0.0",
        "latest_version": "v1.1.0",
        "release_name": "Release v1.1.0",
        "published_at": "2026-11-23",
        "changelog": "- New features\n- Bug fixes",
        "html_url": "https://github.com/test",
        "download_url": "https://github.com/test/download.zip",
        "download_size": 1048576,
    }

    dlg = UpdateDialog(None, sample_info)
    assert dlg.GetTitle() == "Software Update Available"
    assert dlg.btn_update is not None
    assert dlg.btn_later is not None
    assert "v1.1.0" in dlg.lbl_header.GetLabel()
    dlg.Destroy()
    app.Destroy()
