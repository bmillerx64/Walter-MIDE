"""GS285: keep synchronous FMP acquisition from stalling Streamlit sessions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed


def install() -> None:
    from .news_provider import FMPNewsProvider

    if getattr(FMPNewsProvider, "_gs285_installed", False):
        return

    original_request = FMPNewsProvider._request

    def fetch(self, *, since, symbols=()):
        wanted = list(dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in symbols
            if str(symbol or "").strip()
        ))
        if not self.api_key:
            raise RuntimeError("FMP news credential is not configured")

        since = max(
            since.astimezone(self.now().astimezone().tzinfo),
            self.now().astimezone() - self.FRESHNESS,
        )
        self.last_since = since
        self.last_requested_symbols = list(wanted)
        self.endpoints_requested = []
        self.request_failures = []

        batches = [
            wanted[index:index + self.BATCH_SIZE]
            for index in range(0, len(wanted), self.BATCH_SIZE)
        ]
        jobs = [
            (endpoint, batch)
            for batch in batches
            for endpoint in ("news/stock", "news/press-releases")
        ]
        self.request_count = len(jobs)
        self.endpoints_requested = [endpoint for endpoint, _ in jobs]
        if not jobs:
            return []

        output = []
        with ThreadPoolExecutor(
            max_workers=min(4, len(jobs)), thread_name_prefix="fmp-news"
        ) as pool:
            futures = {
                pool.submit(original_request, self, endpoint, batch, since): (endpoint, batch)
                for endpoint, batch in jobs
            }
            for future in as_completed(futures):
                endpoint, batch = futures[future]
                try:
                    output.extend(future.result())
                except Exception as exc:
                    self.request_failures.append(
                        f"{endpoint} ({len(batch)} symbols): {type(exc).__name__}"
                    )

        if self.request_failures and not output:
            raise RuntimeError("FMP news requests failed within bounded timeout")
        return output

    # Bound each underlying HTTP call well below the Streamlit connection timeout.
    original_init = FMPNewsProvider.__init__

    def init(self, api_key, *, timeout=4, session=None, now=None):
        original_init(self, api_key, timeout=timeout, session=session, now=now)
        self.request_failures = []

    FMPNewsProvider.__init__ = init
    FMPNewsProvider.fetch = fetch
    FMPNewsProvider._gs285_installed = True
