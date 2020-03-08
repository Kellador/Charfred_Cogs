import logging
import re
from collections import namedtuple
from utils import Config

log = logging.getLogger('charfred')

MessageType = namedtuple('MessageType', [
    'prefix', 'formatstr', 'formatfields', 'restricted',
    'logfile', 'logonly', 'sendable'
])

fieldspat = re.compile('(?<={)\w*(?=})')


class TypeMapping(Config):
    """Config subclass that handles the conversion from
    the underlying MutableMapping to MessageType namedtuples.
    """

    def __init__(self, cfgfile, **opts):
        super().__init__(cfgfile, **opts)

    def _decodestore(self):
        for prefix, typedict in self.store.items():
            self.store[prefix] = MessageType(**typedict)

    def _encodestore(self):
        for prefix, msgtype in self.store.items():
            self.store[prefix] = msgtype._asdict()

    def _load(self):
        super()._load()
        self._decodestore()

    def _save(self):
        self._encodestore()
        super()._save()

    def __setitem__(self, key, value):
        if isinstance(value, MessageType):
            self.store[key] = value
        elif isinstance(value, dict):
            self.store[key] = MessageType(**value)
        else:
            raise ValueError

    async def add(self, prefix, formatstr, restricted=False, logfile='',
                  logonly=False, sendable=True):
        formatfields = fieldspat.findall(formatstr)
        self.store[prefix] = MessageType(prefix, formatstr, formatfields,
                                         restricted, logfile, logonly, sendable)
        await self.save()
