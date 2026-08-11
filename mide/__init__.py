from .version import __version__

# Install provider-boundary capability guards before live scanner modules run.
from . import data_validation_cleanup as _data_validation_cleanup  # noqa: F401,E402
