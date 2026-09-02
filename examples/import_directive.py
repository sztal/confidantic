# %% ---------------------------------------------------------------------------------

from collections import Counter

from confidantic import BaseConfig
from confidantic.annotations import Import

# %% ---------------------------------------------------------------------------------


class Config(BaseConfig):
    collection: Import[type[Counter]] = Counter  # passes type check


assert Config().collection == Config(collection="collections:Counter").collection

# %% ---------------------------------------------------------------------------------
