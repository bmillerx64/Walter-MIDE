"""GS285: keep synchronous FMP acquisition from stalling Streamlit sessions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed


def install() -> None:
    from .news_provider import FMPNewsProvider, UTC

    if getattr(FMPNewsProvider, "_gs285_installed", False):
        return

    original_request = FMPNewsProvider._request
    original_init = FMPNewsProvider.__init__

    def init(self, api_key, *, timeout=4, session=None, now=None):
        original_init(self, api_key, timeout=timeout, session=session, now=now)
        self.request_failures = []

    def fetch(self, *, since, symbols=()):
        wanted = list(dict.fromkeys(
            str(symbol or "").strip().upper()
            for symbol in symbols
            if str(symbol or "").strip()
        ))
        if not self.api_key:
            raise RuntimeError("FMP news credential is not configured")

        # Preserve the provider's existing public contract exactly: the provider
        # records and queries the caller-supplied range. NewsService owns any
        # downstream six-hour effective-window filtering/diagnostics.
        since = since.astimezone(UTC)
        self.last_since = since
        self.last_requested_symbols = list(wanted)
        self.endpoints_requested = []
        self.request_failures = []
        self.request_count = 0

        batches = [
            wanted[index:index + self.BATCH_SIZE]
            for index in range(0, len(wanted), self.BATCH_SIZE)
        ] or [[]]
        jobs = [
            (endpoint, batch)
            for batch in batches
            if batch
            for endpoint in ("news/stock", "news/press-releases")
        ]
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

        # original_request updates these counters from worker threads. Normalize
        # them after completion so audit provenance remains deterministic and
        # identical to the prior serial contract.
        self.request_count = len(jobs)
        self.endpoints_requested = [endpoint for endpoint, _ in jobs]

        if self.request_failures and not output:
            raise RuntimeError("FMP news requests failed within bounded timeout")
        return output

    FMPNewsProvider.__init__ = init
    FMPNewsProvider.fetch = fetch
    FMPNewsProvider._gs285_installed = True
