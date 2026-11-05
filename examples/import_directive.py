# %% ---------------------------------------------------------------------------------

"""Accept a collection class directly or through a validated import string."""

from collections import Counter

from confidantic import BaseConfig
from confidantic.annotations import Import

# %% ---------------------------------------------------------------------------------


class Config(BaseConfig):
    """Select a Counter-compatible class without constructing a collection."""

    collection: Import[type[Counter]] = Counter  # passes type check


assert Config().collection == Config(collection="collections:Counter").collection

# %% ---------------------------------------------------------------------------------
