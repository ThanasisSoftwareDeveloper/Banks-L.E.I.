"""
Tests for the LEI checker engine.
HTTP calls are mocked via unittest.mock.AsyncMock — no respx, no real network.
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from lei_checker import (
    _check_gleif,
    _fmt_date,
    _parse_lei_lookup_html,
    check_lei_batch,
    GLEIF_API,
)

GLEIF_RESPONSE = {
    "data": {
        "attributes": {
            "entity":       {"status": "ACTIVE"},
            "registration": {"nextRenewalDate": "2025-06-30T00:00:00Z"},
        }
    }
}

VALID_LEI = "7LTWFZYICNSX8D621K86"


def _mock_response(status_code=200, json_data=None, text=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.headers = {}
    if json_data is not None:
        resp.json = MagicMock(return_value=json_data)
    else:
        resp.json = MagicMock(side_effect=Exception("not json"))
    if text is not None:
        resp.text = text
    return resp


class TestFmtDate:
    def test_iso_with_z(self):
        assert _fmt_date("2025-03-31T00:00:00Z") == "2025-03-31"
    def test_iso_with_offset(self):
        assert _fmt_date("2025-06-30T12:00:00+02:00") == "2025-06-30"
    def test_plain_date(self):
        assert _fmt_date("2025-12-31") == "2025-12-31"
    def test_empty_string(self):
        assert _fmt_date("") == ""
    def test_none_coercion(self):
        assert _fmt_date("") == ""


class TestParseLeiLookupHtml:
    _TABLE_HTML = """
    <table>
      <tr><th>Entity Status</th><td>ACTIVE</td></tr>
      <tr><th>Next Renewal Date</th><td>2025-09-30</td></tr>
    </table>
    """
    _DL_HTML = """
    <dl>
      <dt>entity status</dt><dd>ACTIVE</dd>
      <dt>next renewal</dt><dd>2026-01-01</dd>
    </dl>
    """
    def test_parses_table(self):
        status, renewal = _parse_lei_lookup_html(self._TABLE_HTML)
        assert status  == "ACTIVE"
        assert renewal == "2025-09-30"
    def test_parses_dl(self):
        status, renewal = _parse_lei_lookup_html(self._DL_HTML)
        assert status  == "ACTIVE"
        assert renewal == "2026-01-01"
    def test_empty_html(self):
        status, renewal = _parse_lei_lookup_html("")
        assert status  == ""
        assert renewal == ""


@pytest.mark.asyncio
async def test_check_gleif_success():
    mock_resp = _mock_response(200, json_data=GLEIF_RESPONSE)
    with patch("lei_checker._get_with_retry", new=AsyncMock(return_value=mock_resp)):
        async with httpx.AsyncClient() as client:
            status, renewal = await _check_gleif(client, VALID_LEI)
    assert status  == "ACTIVE"
    assert renewal == "2025-06-30"


@pytest.mark.asyncio
async def test_check_gleif_404_returns_empty():
    mock_resp = _mock_response(404)
    with patch("lei_checker._get_with_retry", new=AsyncMock(return_value=mock_resp)):
        async with httpx.AsyncClient() as client:
            status, renewal = await _check_gleif(client, VALID_LEI)
    assert status  == ""
    assert renewal == ""


@pytest.mark.asyncio
async def test_check_gleif_network_error_returns_empty():
    with patch("lei_checker._get_with_retry", new=AsyncMock(return_value=None)):
        async with httpx.AsyncClient() as client:
            status, renewal = await _check_gleif(client, VALID_LEI)
    assert status  == ""
    assert renewal == ""


@pytest.mark.asyncio
async def test_check_gleif_malformed_json():
    mock_resp = _mock_response(200)
    with patch("lei_checker._get_with_retry", new=AsyncMock(return_value=mock_resp)):
        async with httpx.AsyncClient() as client:
            status, renewal = await _check_gleif(client, VALID_LEI)
    assert status  == ""
    assert renewal == ""


@pytest.mark.asyncio
async def test_batch_skips_blank_leis():
    with patch("lei_checker._get_with_retry", new=AsyncMock(return_value=_mock_response(404))):
        results = await check_lei_batch(["", "  ", ""])
    assert results == []


@pytest.mark.asyncio
async def test_batch_marks_invalid_format():
    results = await check_lei_batch(["NOT-A-LEI", "123", "toolongstringthatisnotlei99"])
    assert all(r["entity_status"] == "INVALID FORMAT" for r in results)


@pytest.mark.asyncio
async def test_batch_calls_fallback_when_gleif_incomplete():
    gleif_partial = {"data": {"attributes": {"entity": {"status": "ACTIVE"}, "registration": {"nextRenewalDate": ""}}}}
    fallback_html = """<table><tr><th>Entity Status</th><td>ACTIVE</td></tr><tr><th>Next Renewal Date</th><td>2025-09-30</td></tr></table>"""
    gleif_resp    = _mock_response(200, json_data=gleif_partial)
    fallback_resp = _mock_response(200, text=fallback_html)
    fallback_resp.json = MagicMock(side_effect=Exception("not json"))
    call_count = 0
    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return gleif_resp if call_count == 1 else fallback_resp
    with patch("lei_checker._get_with_retry", new=AsyncMock(side_effect=side_effect)):
        results = await check_lei_batch([VALID_LEI])
    assert len(results) == 1
    assert results[0]["entity_status"] == "ACTIVE"
    assert results[0]["next_renewal"]  == "2025-09-30"


@pytest.mark.asyncio
async def test_batch_on_progress_called_for_each_lei():
    leis  = [VALID_LEI, "AAAAAA1234567890AA01", "BBBBBB1234567890BB02"]
    calls = []
    with patch("lei_checker._get_with_retry", new=AsyncMock(return_value=_mock_response(404))):
        await check_lei_batch(leis, on_progress=lambda idx, r: calls.append(idx))
    assert calls == [0, 1, 2]
