from datetime import datetime, timezone
from mide.completed_scan import CompletedScan
from mide.live_evidence_observation import render_live_evidence_diagnostics

class Col:
    def metric(self,*args,**kwargs): pass
class UI:
    def __init__(self): self.captions=[]; self.messages=[]
    def subheader(self,v): pass
    def caption(self,v): self.captions.append(v)
    def columns(self,n): return [Col() for _ in range(n)]
    def success(self,v): self.messages.append(("success",v))
    def warning(self,v): self.messages.append(("warning",v))
    def error(self,v): self.messages.append(("error",v))
    def info(self,v): self.messages.append(("info",v))

def test_completed_scan_binds_same_readiness_snapshot_to_rendered_evidence():
    scan=CompletedScan(provider="test",records=[],diagnostics={},warnings=[],symbols_sampled=1,prefilter_count=0,completed_at=datetime(2026,8,14,tzinfo=timezone.utc),source_label="test")
    evidence=scan.diagnostics["live_evidence_observation"]
    readiness=scan.diagnostics["evidence_readiness"]
    assert evidence["readiness_snapshot"] == readiness
    assert evidence["readiness_snapshot"] is not readiness

def test_renderer_prefers_bound_snapshot_over_recomputation():
    report={"candidates_audited":1,"trusted_count":1,"caution_count":0,"insufficient_count":0,"trusted_pct":100.0,"stale_evidence_count":0,"incomplete_evidence_count":0,"incoherent_evidence_count":0,"nontrusted_elevated_count":0,"nontrusted_elevated_symbols":[],"observations":[],"readiness_snapshot":{"status":"NOT READY","candidates_audited":1,"trusted_pct":50.0,"target_pct":99.0,"target_met":False,"nontrusted_elevated_count":0,"stale_evidence_count":0,"incomplete_evidence_count":0,"incoherent_evidence_count":0,"reasons":["snapshot provenance marker"]}}
    ui=UI(); render_live_evidence_diagnostics(ui,report)
    assert ui.messages[0][0] == "error"
    assert any("snapshot provenance marker" in c for c in ui.captions)
