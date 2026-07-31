# Price Gate snapshot optimization

Yes. The live pipeline uses Alpaca's multi-symbol Latest Trades endpoint
(`GET /v2/stocks/trades/latest`) to obtain only the `p` value required by the
Price Gate. Full snapshots are requested only for Price Gate survivors. Providers
without a minimal-price method retain the snapshot fallback for compatibility.

## Per-scan accounting

`pipeline_timing_summary` includes a `Market Data Retrieval` row with:

- the Price Gate input, survivor, and avoided-symbol counts;
- the baseline, actual, and avoided snapshot batch counts;
- observed Latest Trades and survivor-snapshot elapsed milliseconds; and
- estimated gross snapshot time avoided and net time saved.

Symbol and batch savings are exact. Timing is an estimate because Walter does not
make a wasteful second request for the rejected symbols. It divides observed survivor
snapshot time by actual snapshot batches, multiplies by avoided batches, and subtracts
the measured Latest Trades overhead for net savings:

`net saved = (survivor snapshot ms / actual batches × avoided batches) - latest-trade ms`

The timing estimate is `null` when no symbol survives, because there is no observed
snapshot batch from which to extrapolate. This avoids presenting an invented latency.

For example, a 420-symbol universe with 90 Price Gate survivors and a 150-symbol
batch size requests snapshots for **90 instead of 420 symbols**: **330 symbols
(78.57%)** and **2 of 3 snapshot batches** are avoided. If Latest Trades takes 40 ms
and the one survivor snapshot batch takes 120 ms, estimated gross snapshot time
avoided is 240 ms and estimated net time saved is **200 ms**.

These values are emitted per scan rather than treated as a fixed benchmark; real
latency varies with feed entitlement, network conditions, response size, retries, and
the number of survivors.

## Universe boundary

The Price Gate input is the reduced Alpaca Asset universe, not a union with movers,
most-actives, news symbols, or a public symbol directory. Each member must have
`tradable=true`, `status=active`, and `class=us_equity`. Preferred shares, warrants,
rights, units, depositary instruments, exchange-traded products, funds, debt, and
partnership instruments are rejected from Alpaca's asset `name` metadata; symbol
suffixes are not used as a proxy for instrument type.

The live per-scan diagnostics report the confirmed membership as `final_seed_count`
and `broad_eligible`. `pipeline_timing_summary` reports the measured Universe
Construction time, Price Gate time, and complete scan time, so the production scan
itself supplies the benchmark for its current network, feed, and market session.
