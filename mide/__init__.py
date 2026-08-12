from .version import __version__

# Install provider-boundary capability guards before live scanner modules run.
from . import data_validation_cleanup as _data_validation_cleanup  # noqa: F401,E402

# Install the catalyst-first two-lane routing before app.py imports the
# architecture constants and constructs WalterArchitectureV1.
from .catalyst_route import install as _install_catalyst_route  # noqa: E402
from .contract_compat import install as _install_contract_compat  # noqa: E402
from .prefilter_compat import install as _install_prefilter_compat  # noqa: E402

_install_catalyst_route()
_install_contract_compat()
_install_prefilter_compat()
