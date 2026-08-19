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
