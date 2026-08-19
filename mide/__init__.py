from .version import __version__

from .fmp_bootstrap import activate_streamlit_fmp_secret as _activate_streamlit_fmp_secret  # noqa: E402

# Normalize an already-configured Streamlit FMP secret before any news provider
# is constructed. The helper exposes only presence and never logs the value.
_activate_streamlit_fmp_secret()

from . import data_validation_cleanup as _data_validation_cleanup  # noqa: F401,E402
from .prefilter_compat import install as _install_prefilter_compat  # noqa: E402

_install_prefilter_compat()

from .catalyst_route import install as _install_catalyst_route  # noqa: E402
from .contract_compat import install as _install_contract_compat  # noqa: E402

_install_catalyst_route()
_install_contract_compat()

from .readiness_audit import install as _install_readiness_audit  # noqa: E402

_install_readiness_audit()

from .gs257_runtime import install as _install_gs257_runtime  # noqa: E402

_install_gs257_runtime()

from .gs258_cutover import install as _install_gs258_cutover  # noqa: E402

_install_gs258_cutover()

from .gs259_ui_cleanup import install as _install_gs259_ui_cleanup  # noqa: E402

_install_gs259_ui_cleanup()

from .gs261_provenance import install as _install_gs261_provenance  # noqa: E402

_install_gs261_provenance()

from .gs262_discovery_fidelity import install as _install_gs262_discovery_fidelity  # noqa: E402

_install_gs262_discovery_fidelity()

from .gs263_discovery_gate import install as _install_gs263_discovery_gate  # noqa: E402

_install_gs263_discovery_gate()

from .gs285_fmp_latency import install as _install_gs285_fmp_latency  # noqa: E402

_install_gs285_fmp_latency()

from .gs288_fmp_filtering import install as _install_gs288_fmp_filtering  # noqa: E402

_install_gs288_fmp_filtering()

from .gs289_fmp_stock_news_contract import install as _install_gs289_fmp_stock_news_contract  # noqa: E402

_install_gs289_fmp_stock_news_contract()

from .gs292_reevaluation_continuity import install as _install_gs292_reevaluation_continuity  # noqa: E402

_install_gs292_reevaluation_continuity()

from .gs294_fresh_attention_recheck import install as _install_gs294_fresh_attention_recheck  # noqa: E402

_install_gs294_fresh_attention_recheck()

from .gs295_escalation_patch import install as _install_gs295_escalation_patch  # noqa: E402

_install_gs295_escalation_patch()

from .gs296_first_print_alert_patch import install as _install_gs296_first_print_alert_patch  # noqa: E402

_install_gs296_first_print_alert_patch()

from .gs298_news_seeded_discovery import install as _install_gs298_news_seeded_discovery  # noqa: E402

_install_gs298_news_seeded_discovery()

from .gs299_news_reaction_watch import install as _install_gs299_news_reaction_watch  # noqa: E402

_install_gs299_news_reaction_watch()

from .gs300_fmp_news_pagination import install as _install_gs300_fmp_news_pagination  # noqa: E402

_install_gs300_fmp_news_pagination()

from .gs301_catalyst_evidence_handoff import install as _install_gs301_catalyst_evidence_handoff  # noqa: E402

_install_gs301_catalyst_evidence_handoff()

from .gs302_stage_purity_enforcement import install as _install_gs302_stage_purity_enforcement  # noqa: E402

_install_gs302_stage_purity_enforcement()
