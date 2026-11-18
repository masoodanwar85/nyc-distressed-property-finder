"""Small client for the NYC Open Data (Socrata) API."""
import time

import requests


def in_clause(field, values):
    """SoQL `field in ('a','b')` with single quotes escaped."""
    quoted = ",".join("'" + str(v).replace("'", "''") + "'" for v in values)
    return f"{field} in ({quoted})"


def chunked(items, size):
    items = list(items)
    for start in range(0, len(items), size):
        yield items[start : start + size]


class SocrataClient:
    def __init__(self, base_url, app_token="", session=None, page_size=5000, pause=0.2, timeout=60):
        self.base_url = base_url.rstrip("/")
        self.app_token = app_token
        self.session = session or requests.Session()
        self.page_size = page_size
        self.pause = pause
        self.timeout = timeout

    def fetch_all(self, dataset_id, where=None, select=None):
        """Yield every row matching `where`, paging with $limit/$offset."""
        headers = {"X-App-Token": self.app_token} if self.app_token else {}
        offset = 0
        while True:
            params = {"$limit": self.page_size, "$offset": offset, "$order": ":id"}
            if where:
                params["$where"] = where
            if select:
                params["$select"] = select
            response = self.session.get(
                f"{self.base_url}/{dataset_id}.json", params=params, headers=headers, timeout=self.timeout
            )
            response.raise_for_status()
            rows = response.json()
            yield from rows
            if len(rows) < self.page_size:
                return
            offset += self.page_size
            if self.pause:
                time.sleep(self.pause)


def make_client():
    """Client configured from Django settings."""
    from django.conf import settings

    return SocrataClient(settings.SOCRATA_BASE_URL, app_token=settings.SOCRATA_APP_TOKEN)
