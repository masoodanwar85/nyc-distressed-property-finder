from django.test import SimpleTestCase

from leads.services.bbl import make_bbl, split_bbl
from leads.services.socrata import SocrataClient, in_clause, chunked


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    """Serves rows from a list, honouring $limit and $offset like Socrata."""

    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append({"url": url, "params": dict(params), "headers": dict(headers or {})})
        limit, offset = int(params["$limit"]), int(params["$offset"])
        return FakeResponse(self.rows[offset : offset + limit])


class BblTests(SimpleTestCase):
    def test_make_bbl_pads_block_and_lot(self):
        self.assertEqual(make_bbl("3", "935", "7504"), "3009357504")
        self.assertEqual(make_bbl(1, 1146, 16), "1011460016")

    def test_make_bbl_returns_empty_when_a_part_is_missing(self):
        self.assertEqual(make_bbl("3", "", "7"), "")

    def test_split_bbl_returns_integers(self):
        self.assertEqual(split_bbl("3009357504"), (3, 935, 7504))


class SocrataClientTests(SimpleTestCase):
    def test_fetch_all_pages_until_a_short_page(self):
        session = FakeSession([{"n": i} for i in range(5)])
        client = SocrataClient("https://example.test/resource", session=session, page_size=2, pause=0)
        rows = list(client.fetch_all("abcd-1234", where="x > 1"))
        self.assertEqual([r["n"] for r in rows], [0, 1, 2, 3, 4])
        self.assertEqual([c["params"]["$offset"] for c in session.calls], [0, 2, 4])
        self.assertEqual(session.calls[0]["url"], "https://example.test/resource/abcd-1234.json")
        self.assertEqual(session.calls[0]["params"]["$where"], "x > 1")

    def test_fetch_all_orders_by_id_for_stable_paging(self):
        session = FakeSession([])
        client = SocrataClient("https://example.test/resource", session=session, pause=0)
        list(client.fetch_all("abcd-1234"))
        self.assertEqual(session.calls[0]["params"]["$order"], ":id")

    def test_app_token_is_sent_as_header_when_set(self):
        session = FakeSession([])
        client = SocrataClient("https://example.test/resource", app_token="tok", session=session, pause=0)
        list(client.fetch_all("abcd-1234"))
        self.assertEqual(session.calls[0]["headers"]["X-App-Token"], "tok")

    def test_no_token_header_when_token_is_empty(self):
        session = FakeSession([])
        client = SocrataClient("https://example.test/resource", session=session, pause=0)
        list(client.fetch_all("abcd-1234"))
        self.assertNotIn("X-App-Token", session.calls[0]["headers"])


class HelperTests(SimpleTestCase):
    def test_in_clause_quotes_values(self):
        self.assertEqual(in_clause("zip", ["10027", "10030"]), "zip in ('10027','10030')")

    def test_in_clause_escapes_single_quotes(self):
        self.assertEqual(in_clause("name", ["O'Neil"]), "name in ('O''Neil')")

    def test_chunked_splits_into_batches(self):
        self.assertEqual(list(chunked([1, 2, 3, 4, 5], 2)), [[1, 2], [3, 4], [5]])
