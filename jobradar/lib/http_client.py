from __future__ import annotations

import httpx

TOOL_USER_AGENT = "job-radar/0.1 (personal job search tool)"
# Some public search pages are served to browsers only.
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                                 "Chrome/140.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}


class HttpClient:
    def __init__(self, timeout: float = 30, user_agent: str = TOOL_USER_AGENT):
        self.http = httpx.Client(headers={"User-Agent": user_agent}, timeout=timeout, follow_redirects=True)

    def get_json(self, url: str, **params):
        response = self.http.get(url, params=params or None)
        response.raise_for_status()
        return response.json()

    def get_page(self, url: str, **params) -> str:
        response = self.http.get(url, params=params or None, headers=BROWSER_HEADERS)
        response.raise_for_status()
        return response.text

    def get_bytes(self, url: str) -> bytes:
        response = self.http.get(url)
        response.raise_for_status()
        return response.content

    def status_code(self, url: str) -> int:
        """Raises httpx.HTTPError when the host can't be reached."""
        return self.http.get(url).status_code

    def close(self):
        self.http.close()
