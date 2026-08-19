"""Config-Snapshot-Aufloesung (Phase 2 aus TRADING_ENGINE_ARCHITECTURE.md).

Loest die doppelt gepflegte trading.pipeline_config-Zeilen-zu-Map-Uebersetzung ab
(CFG.KEY ?? default in WF14, num('KEY', default) in WF17). ConfigSnapshot selbst ist in
models.py definiert (Phase 3); dieses Modul ist die vorgesehene einzige Implementierungsstelle
fuer ConfigSnapshot.from_rows()/get() - siehe Modulstruktur-Begruendung in
TRADING_ENGINE_ARCHITECTURE.md Phase 2.

Vor der Implementierung gegen den in FINAL_REVIEW.md dokumentierten Config-Key-Sweep pruefen
(37 projektweit verwendete Keys, Tabelle in REVIEW_REPORT.md) - insbesondere die dort bereits
gefundenen und behobenen Faelle (WF14 MAX_DATA_ERROR_RETRIES, WF17 Mini-Future-Keys) nicht
erneut als offen behandeln.
"""

from __future__ import annotations

from .models import ConfigSnapshot

__all__ = ["ConfigSnapshot"]
