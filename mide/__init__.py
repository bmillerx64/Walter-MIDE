from .version import __version__

# Install provider-boundary capability guards before live scanner modules run.
from . import data_validation_cleanup as _data_validation_cleanup  # noqa: F401,E402

# Install the catalyst-first two-lane routing before app.py imports the
# architecture constants and constructs WalterArchitectureV1.
from .catalyst_route import install as _install_catalyst_route  # noqa: E402

_install_catalyst_route()
