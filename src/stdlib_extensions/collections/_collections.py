import sys
import copy
import types
import reprlib
from collections import *  # pyright: ignore[reportAssignmentType]
from .._shared import AbstractComposition
from ..inspect import ismapping
from ..typing import (
    cast,
    overload,
    Any,
    Mappable,
    SupportsIndex,
    Iterable,
    Mapping,
    MutableMapping,
    Sequence,
    Iterator,
    Iterable,
    Protocol,
    TypeIs,
    Self,
    T,
    T_co,
    KT,
    KT_co,
    VT,
    VT_co,
    VT_contra,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from collections.abc import KeysView, ValuesView, ItemsView








# [ Extensions/Rewrites ]

class ChainMap(MutableMapping):
    __slots__ = ('maps',)

    def __getstate__(self) -> tuple[tuple[MutableMapping, ...], dict[str, Any] | None]:
        return tuple(self.maps), None

    def __setstate__(self, state: tuple[Sequence[MutableMapping], Any]):
        self.maps = deque(state[0], maxlen=len(state[0]))

    @overload
    def __init__(self, m: Mappable | MutableMapping, /) -> None: ...
    @overload
    def __init__(self, *maps: Mappable | MutableMapping) -> None: ...
    def __init__(self, *_maps: Mappable | MutableMapping):
        if not _maps:
            _maps = ({},)
        else:
            _maps = tuple(m if ismapping(m) else dict(m) for m in _maps)
        self.__setstate__((_maps, None))  # type: ignore

    @classmethod
    def fromkeys(cls, iterable, value: Any = None, /) -> Self:
        return cls(dict.fromkeys(iterable, value))

    def new_child(self, m: MutableMapping | None = None, /, **kwargs) -> Self:
        if m is None:
            m = kwargs
        else:
            m.update(kwargs)
        return self.__class__(m, *self.maps)

    def chainmap_from(self, key: Any) -> Self:
        """Create a chain map with mappings assigned to *key* from each
        mapping in `self.maps`.

        If a mapping does not contain *key* or *key* is set to None, the
        new chain map will contain a new, empty dictionary in place of the
        missing/empty value.
        """
        maps = []
        for i, m in enumerate(self.maps):
            v = m.get(key)
            if v is None:
                v = {}
            elif not ismapping(v):
                raise TypeError(f"value of {key!r} in `self.maps[{i}]` is not a mapping")
            maps.append(v)
        return self.__class__(*maps)

    def ichainmap_from(self, key: Any) -> Self:
        """Return `self.chainmap_from(key)`, but also assign *key* of this
        chain map's newest mapping to the new chain map."""
        m = self.maps[0][key] = self.chainmap_from(key)
        return m

    @property
    def parents(self):
        maps, other = self.__getstate__()
        new = self.__new__(self.__class__)
        new.__setstate__((maps[1:], other))
        return new

    def copy(self) -> Self:
        maps, other = self.__getstate__()
        try:
            m = maps[0].copy()  # type: ignore
        except AttributeError:
            m = copy.copy(maps[0])

        new = self.__new__(self.__class__)
        new.__setstate__(((m, *maps[1:]), other))
        return new

    __copy__ = copy

    __repr__ = ChainMap.__repr__  # type: ignore
    __bool__ = ChainMap.__bool__
    __len__ = ChainMap.__len__
    __contains__ = ChainMap.__contains__  # type: ignore

    def __iter__(self):
        d = {}
        for m in reversed(self.maps):
            d.update(m)
        return iter(d)

    def __missing__(self, key):
        raise KeyError(key)

    def __getitem__(self, key):
        # doesn't work w/defaultdict but is faster for the common case
        for m in self.maps:
            if key in m:
                return m[key]
        return self.__missing__(key)

    __setitem__ = ChainMap.__setitem__  # type: ignore
    __delitem__ = ChainMap.__delitem__  # type: ignore

    def update(self, m: Mappable | None = None, **kwargs) -> None:  # pyright: ignore[reportIncompatibleMethodOverride]
        if not m:
            self.maps[0].update(kwargs)
        else:
            self.maps[0].update(m, **kwargs)

    __ior__ = ChainMap.__ior__

    def __or__(self, other: Mapping) -> Self:
        if not ismapping(other):
            return NotImplemented
        new = self.copy()
        new.maps[0].update(other)
        return new

    def __ror__(self, other: MutableMapping) -> Self:
        if not ismapping(other):
            return NotImplemented

        m = dict(other)
        for d in reversed(self.maps):
            m.update(d)

        new = self.__new__(self.__class__)
        new.__setstate__(((m,), None))

        return new

    def clear(self):
        self.maps[0].clear()

    @overload
    def pop(self, key, /) -> Any: ...
    @overload
    def pop(self, key, default, /) -> Any: ...
    def pop(self, *args):  # type: ignore
        return self.maps[0].pop(*args)

    def popitem(self) -> tuple[Any, Any]:
        return self.maps[0].popitem()






# [Composition ABCs]

# Personal experience; when I make a new type emulating a built-in, most
# methods are one-liners forwarding the call to a method (of the same
# name, no less) of an underlying object. The below ABCs are lightweight
# wrappers around an object found on an instance's `_object_value_`
# attribute, broken out by behavior. They try to emulate built-in behavior
# as much as possible by not "crossing" methods (for example, an `.update`
# method would not hook through `.__setitem__`).

class ComposedCollection(AbstractComposition, Protocol[T_co]):
    """Base composition class for types emulating containers.

    Methods are completely independent of each other to best emulate
    built-in behavior. However, many call the `._format_key` and
    `._format_value` methods, which can be overridden to mutate subscript
    and values prior to most get, set, and delete operations.
    """
    __slots__ = ()

    def _format_key(self, key: Any) -> Any:
        """Format hook for keys and indices. Called on get, set/update, and
        delete/pop operations.

        This is a no-op unless overridden by a user.
        """
        return key

    def _format_value(self, value: Any) -> Any:
        """Format hook for values. Called during operations that would
        set a value.

        This is a no-op unless overridden by a user.
        """
        return value

    def __getstate__(self) -> tuple[tuple[Any, ...], dict | None]:
        return (self._object_value_,), None

    def __contains__(self, __value: Any) -> bool:
        return __value in self._object_value_

    def __iter__(self) -> Iterator[T_co]:
        return iter(self._object_value_)

    def __len__(self) -> int:
        return len(self._object_value_)


class KeyItemGet(ComposedCollection[KT], Protocol[KT, VT_co]):
    """Base composition class for objects accepting hashable subscript
    and returning a value(s)."""
    __slots__ = ()

    def __getitem__(self, __key: KT) -> VT_co:
        try:
            return self._object_value_[self._format_key(__key)]
        except KeyError:
            raise KeyError(__key) from None  # use original key

    def get(self, __key: KT, __default: Any = None, /) -> VT_co | Any:
        return self._object_value_.get(self._format_key(__key), __default)


class KeyItemSet(ComposedCollection[KT], Protocol[KT, VT_contra]):
    """Base composition class for objects accepting updates using
    hashable subscript."""
    __slots__ = ()

    def __setitem__(self, __key: KT, __value: VT_contra) -> Any:
        self._object_value_[self._format_key(__key)] = self._format_value(__value)

    @overload
    def update(self, /, **kwargs) -> None: ...
    @overload
    def update(self, m: Mapping[KT, VT] | Iterable[tuple[KT, VT]] | None, /, **kwargs: VT) -> None: ...
    def update(self, m: Any = None, /, **kwargs: Any):
        if m is None:
            m = kwargs
        else:
            m = dict(m, **kwargs)  # throws `KeyError` (duplicate keys) w/original keys
        # XXX: NOT forwarded through `__setitem__` to mirror built-in behavior
        fmt_key = self._format_key
        fmt_val = self._format_value
        self._object_value_.update(
            (fmt_key(k), fmt_val(v)) for k,v in m.items()
        )

    __ior__ = update


class KeyItemDel(ComposedCollection[KT], Protocol[KT, VT_co]):
    """Base composition class for objects allowing deletion of values
    using hashable subscript and clear operations."""
    __slots__ = ()

    def __delitem__(self, __key: KT) -> None:
        try:
            del self._object_value_[self._format_key(__key)]
        except KeyError:
            raise KeyError(__key) from None  # use original key

    def clear(self) -> None:
        self._object_value_.clear()

    @overload
    def pop(self, __key: KT) -> VT_co: ...
    @overload
    def pop(self, __key: KT, __default: T) -> VT_co | T:  ...
    def pop(self, __key: KT, *args) -> Any:
        return self._object_value_.pop(self._format_key(__key), *args)

    def popitem(self) -> tuple[KT, VT_co]:
        return self._object_value_.popitem()


class MapView(ComposedCollection[KT_co], Protocol[KT_co, VT_co]):
    """Base composition class for objects supporting mapping views."""
    __slots__ = ()

    def items(self, /) -> 'ItemsView[KT_co, VT_co]':
        return self._object_value_.items()

    def keys(self, /) -> 'KeysView[KT_co]':
        return self._object_value_.keys()

    def values(self, /) -> 'ValuesView[VT_co]':
        return self._object_value_.values()


class ComposedDict(    # pyright: ignore
    KeyItemDel[KT, VT],
    KeyItemSet[KT, VT],
    KeyItemGet[KT, VT],
    MapView[KT, VT],
    Protocol[KT, VT],
    cast(type[MutableMapping], object)    # pyright: ignore
):
    """Base composition class for objects emulating most behaviors
    of built-in dictionaries."""
    __slots__ = ()

    __abc_tpflags__ = 1 << 6 # Py_TPFLAGS_MAPPING

    def __bool__(self) -> bool:
        return bool(self._object_value_)




class IndexItemGet(ComposedCollection[T], Protocol[T]):
    __slots__ = ()

    def __getitem__(self, __index: SupportsIndex, /) -> T:
        try:
            return self._object_value_[self._format_key(__index)]
        except IndexError:
            raise IndexError(__index) from None  # use original idx

    def __reversed__(self) -> Iterator[T]:
        yield from reversed(self._object_value_)

    def index(self, __value: T, __start: int = 0, __stop: int = sys.maxsize, /) -> int:
        return self._object_value_.index(__value, __start, __stop)

    def count(self, __value: Any, /) -> int:
        return self._object_value_.count(__value)


class IndexItemSet(ComposedCollection[T], Protocol[T]):
    __slots__ = ()

    def __setitem__(self, __key: SupportsIndex, __value: T) -> None:
        self._object_value_[self._format_key(__key)] = self._format_value(__value)

    def __add__(self, __value: Sequence[T]) -> Self:
        self._object_value_.extend(__value)  # can't set -- it may not be writable!
        return self

    __iadd__ = __radd__ = __add__

    def append(self, __value: T) -> None:
        self._object_value_.append(__value)

    def extend(self, __iterable: Iterable[T]) -> None:
        self._object_value_.extend(__iterable)

    def insert(self, __index: int, __value: T) -> None:
        self._object_value_.insert(__index, __value)

    def reverse(self) -> None:
        self._object_value_.reverse()


class IndexItemDel(ComposedCollection[T], Protocol[T]):
    __slots__ = ()

    def __delitem__(self, __key: SupportsIndex) -> None:
        del self._object_value_[__key]  # type: ignore

    def pop(self, __index: int = -1) -> T:
        return self._object_value_.pop(__index)

    def remove(self, __value: T) -> None:
        self._object_value_.remove(__value)


class ComposedTuple(IndexItemGet[T], Protocol[T]):
    """Base composition class for objects emulating most behaviors
    of built-in tuples."""
    __slots__ = ()

    __abc_tpflags__ = 1 << 5 # Py_TPFLAGS_SEQUENCE

    def __bool__(self):
        return bool(self._object_value_)


class ComposedList(IndexItemDel[T], IndexItemSet[T], IndexItemGet[T], Protocol[T]):
    """Base composition class for objects emulating most behaviors
    of built-in lists."""
    __slots__ = ()

    __abc_tpflags__ = 1 << 5 # Py_TPFLAGS_SEQUENCE

    def __bool__(self):
        return bool(self._object_value_)





# [ Mappings ]

class IdentifierDict(ComposedDict[str, Any]):
    """A case-insensitive mapping containing valid Python identifiers."""
    __slots__ = ('_object_value_',)

    def __init__(self, m: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None, **kwargs: Any):
        self._object_value_ = {}
        self.update(m, **kwargs)

    def _format_key(self, key: str):
        k = ' '.join(key.strip().split()).casefold().replace(' ', '_')
        try:
            if not k[0].isalpha():
                k = '_' + k

            if not k.isidentifier():
                raise ValueError
        except (IndexError, ValueError):
            raise ValueError(f"{key!r} cannot be formatted into a valid Python identifier") from None

        return k


class NamespaceDict(ComposedDict[str, Any], cast(type[types.SimpleNamespace], object)):
    """A mutable mapping wrapper for creating namespaces. Similar
    to `SimpleNamespace`, but allows for access and mutations of the
    namespace as if it were a mutable mapping in addition to dotted
    attribute access and assignment.

    All constructors accept an optional mutable mapping as a
    positional argument and an arbitrary number keyword arguments.
    When a mapping is provided, that mapping is used as the new
    namespace's `__dict__` (note that it is used as-is and that a
    copy/new dict is NOT created). However, if the mapping is another
    `NamespaceDict` object, then its' underlying `__dict__` is used
    as the new namespace's `__dict__` instead. Otherwise, the
    namespace will be created with an empty dictionary. The namespace
    is then updated with any provided keyword arguments via
    `self.update`.

    Note that dotted attribute access will prioritize methods and
    descriptor members over those in the namespace's dictionary.
    """
    __slots__ = ('__dict__', '_object_value_', '_format_value')

    def _format_value_default(self, value):
        return value

    def _format_value_chained(self, value):
        if ismapping(value) and not isinstance(value, NamespaceDict):
            return self.chain(value)  # type: ignore
        return value

    def __new__(cls, m: MutableMapping[str, Any] | None = None, **kwargs: Any) -> Self:
        self = super().__new__(cls)
        if ismapping(m):
            self.__dict__ = m  # type: ignore
        self._object_value_ = self.__dict__
        return self

    def __init__(self, m: MutableMapping[str, Any] | None = None, **kwargs: Any) -> None:
        self._format_value = self._format_value_default
        if kwargs:
            self.update(kwargs)

    @classmethod
    def chain(cls, m: MutableMapping[str, Any] | None = None, /, **kwargs: Any) -> Self:
        """Alternative constructor for accessing nested mapping structures.

        A `NamespaceDict` instance created using this method will convert
        all non-`NamespaceDict` mapping values to namespace dictionaries.
        This includes all existing values and those set in the future. This
        behavior is propegated to all child `NamespaceDict` objects created
        by the returned instance, making this a recursive operation.

        The behavior can be removed using the `.unlink` method.
        """
        self = cls.__new__(cls, m)
        self._format_value = self._format_value_chained
        if m:
            self.update(m)
        if kwargs:
            self.update(kwargs)
        return self

    def unlink(self, force: bool = False) -> None:
        """If the instance has the "chain" behavior set from the
        `NamespaceDict.chain` class method, remove the behavior from this
        object and all inner namespaces, recursively.

        This is a no-op if this instance does not have the "chain"
        behavior set from `NamespaceDict.chain`, unless *force* is True.
        Additionally, *force* will be forwarded to child namespace dicts.
        """
        if force or self._format_value is self._format_value_chained:
            for v in self.__dict__.values():
                if isinstance(v, NamespaceDict):
                    v.unlink(force)

    @reprlib.recursive_repr()
    def __repr__(self) -> str:
        return f'{self.__class__.__name__}({self.__dict__!r})'

    def __getattr__(self, name: str):
        # Forwards to `_object_value_` since it can point to a
        # delegate of `__dict__` (like a chain map) — `__dict__`
        # WILL always point to a Python `dict` object.
        return self._object_value_[name]
