"""GS563: native fast-mover attention and pause-awareness facade.

Live validation on 2026-09-25 exposed a gap between Walter's already-fetched Webull
native radar and the trade-qualified candidate pipeline. RDGT entered the native
five-minute-movers feed but free-float reference data failed closed before scanner
analysis; it later expanded sharply and was suspended in Webull Desktop. MSGY likewise
continued into an extreme move and later displayed as suspended.

GS563 does not bypass any trading gate. It:
- promotes already-fetched top-five-minute-mover evidence into the existing
  presentation-only market-event lane using GS377's established 15% / $5 context;
- gives newly-current native market events a bounded LOOK NOW audio cue even when
  qualification/reference data prevents a normal candidate alert;
- emits only a probabilistic CHECK TRADING STATUS cue when a current hot mover's
  analyzed source bar becomes stale; it never manufactures confirmed halt truth;
- preserves explicit halt/suspension fields if the official snapshot supplies them.

No new provider request, score, rank, float decision, qualification, readiness,
anti-chase, execution, or order authority is added.
"""

from __future__ import annotations


def install() -> None:
    from .authorities import market_evidence, presentation_audio

    market_evidence.activate_native_fast_mover_attention()
    presentation_audio.install_native_market_event_audio()


__all__ = ["install"]
