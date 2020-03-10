import logging
import re
from collections import namedtuple, MutableMapping
from utils import Config, InvertableMapping

log = logging.getLogger('charfred')

MessageType = namedtuple('MessageType', [
    'prefix', 'formatstr', 'sendable',
    'formatfields', 'encoding'
])

fieldspat = re.compile('(?<={)\w*(?=})')


class TypeMapping(MutableMapping):
    """MutableMapping that handles the conversion from
    the underlying dict to MessageType namedtuples.
    """

    def __init__(self, initial):
        if initial:
            self.store = {k: MessageType(**v) for k, v in initial.items()}
        else:
            self.store = {}

    def as_dict(self):
        return {k: v._asdict() for k, v in self.store.items()}

    def __getitem__(self, key):
        return self.store[key]

    def __iter__(self):
        return iter(self.store)

    def __len__(self):
        return len(self.store)

    def __setitem__(self, key, value):
        if isinstance(value, MessageType):
            self.store[key] = value
        elif isinstance(value, dict):
            self.store[key] = MessageType(**value)
        else:
            raise ValueError

    def __delitem__(self, key):
        del self.store[key]

    def add(self, prefix, formatstr, sendable):
        formatfields = fieldspat.findall(formatstr)
        encoding = f'{prefix}::'
        for field in formatfields:
            encoding += '{' + field + '}::'
        else:
            encoding += '\n'
        self.store[prefix] = MessageType(prefix, formatstr, sendable,
                                         formatfields, encoding)


class RelayConfig(Config):
    """Config subclass holding exposing multiple internal dictionaries,
    saved to a single config file.
    """

    def __init__(self, cfgfile, initial={}, **opts):
        default = {
            'types': initial,
            'routing': {},
            'typerouting': {}
        }
        super().__init__(cfgfile, default=default, **opts)

    @property
    def types(self):
        return self.store['types']

    @property
    def routing(self):
        return self.store['routing']

    @property
    def client_ch(self):
        return self.store['routing']

    @property
    def ch_clients(self):
        return self.store['routing'].inverted

    @property
    def typerouting(self):
        return self.store['typerouting']

    @property
    def type_ch(self):
        return self.store['typerouting']

    @property
    def ch_type(self):
        return self.store['typerouting'].inverted

    def as_dict(self):
        _store = {}
        for k, v in self.store.items():
            if isinstance(v, TypeMapping):
                _store[k] = v.as_dict()
            elif isinstance(v, InvertableMapping):
                _store[k] = v.store.copy()
            elif isinstance(v, dict):
                _store[k] = v.copy()
            else:
                _store[k] = v
        return _store

    def _decode(self):
        self.store['types'] = TypeMapping(self.store['types'])
        self.store['routing'] = InvertableMapping(self.store['routing'])
        self.store['typerouting'] = InvertableMapping(self.store['typerouting'])

    def _load(self):
        super()._load()
        self._decode()

    def _save(self):
        super()._save(savee=self.as_dict())
