from .base import MikrotikBase
from .users import MikrotikUsersMixin
from .profiles import MikrotikProfilesMixin
from .secrets import MikrotikSecretsMixin
from .system import MikrotikSystemMixin

class MikrotikAPI(MikrotikBase, MikrotikUsersMixin, MikrotikProfilesMixin, MikrotikSecretsMixin, MikrotikSystemMixin):
    pass
