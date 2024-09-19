from enum import *  # type: ignore
import enum
from . import _shared
from .typing import Any, T




class EnumType(enum.EnumMeta):
    """An extension of `enum.EnumType` used for porting changes made to
    newer versions and other various customizations."""
    def __contains__(self, value: Any) -> bool:
        # allow enum subclasses to define this behavior
        return self.__class_contains__(self, value)

    @staticmethod
    def __class_contains__(inst, value: Any, /):  # pyright: ignore[reportSelfClsParameterName]
        """Hook used to override or extend the behavior of 'EnumType.__contains__'.

        Note that the method will be called unbound, and does not need to be
        defined as a static method (similar to the `__new__` method). It will
        receive the enum class and the value to check as positional arguments.

        To fall back to the default implementation, you must call the metaclass'
        implementation explicitly e.g. `cls.__class__.__class_contains__(cls, value)`
        (you cannot use `super().__class_contains__(...)`).
        """
        # [Python 3.12] check members & member values
        try:
            if value in inst._value2member_map_ or isinstance(value, inst):
                return True
        except AttributeError:  # in case internals ('._value2member_map_') changes in the future
            try:
                res = enum.EnumMeta.__contains__(inst, value)
            except TypeError:
                pass
            else:
                if res:
                    return True
        return False

EnumMeta = EnumType




class StrEnum(str, enum.Enum, metaclass=EnumType):
    """Emulates `enum.StrEnum` behavior in Python 3.11+."""
    def __str__(self):
        return self._value_




def _add_caseinsensitive_dunders(tp: type[T]) -> type[T]:
    for name in (
        '__contains__',
        '__le__',
        '__lt__',
        '__eq__',
        '__gt__',
        '__ge__',
    ):
        fn = _shared.create_function(
            name,
            ('self', 'other', '/', '*', f'_mthd = str.{name}'),
            (
                'if not isinstance(other, str):',
                '    return False',
                'return _mthd(self, other.casefold())',
            ),
            bool,
            __name__,
            globals=globals(),
            locals=vars(tp),
        )
        type.__setattr__(tp, name, fn)

    return tp


@_add_caseinsensitive_dunders
class CaseInsensitiveStrEnum(StrEnum):
    """A `StrEnum` extension that casefolds all member values before
    creation. Additionally, string operands are casefolded for most
    operations.
    """
    def __new__(cls, obj, *args):
        value = str(obj, *args).casefold()
        self  = str.__new__(cls, value)
        self._value_ = value
        return self

    def __class_contains__(cls: EnumType, value: Any) -> bool:  # type: ignore
        if isinstance(value, str):
            value = value.casefold()
        return cls.__class__.__class_contains__(cls, value)

    @classmethod
    def _missing_(cls, value: Any):
        if not isinstance(value, str):
            return None

        value = value.casefold()




class MultiEnum(enum.Enum, metaclass=EnumType):
    """An enumeration type where members are associated with one or more
    constants.
    """
    _values_: tuple[Any, ...]

    def __new__(cls, *values):
        assert values
        try:
            # bypass all of the EnumType crap
            cache = type.__getattribute__(cls, '_alias_map_')
        except AttributeError:
            # `_alias_map_` contains aliases to their associated
            # member. The value (member) is unknown at this point
            # since `cls.__members__` is still being -- The "0_SETUP"
            # key signals `cls._missing_` to fill in the members later.
            cache = {"0_SETUP": None}
            type.__setattr__(cls, '_alias_map_', cache)

        value, *_consts = values
        aliases = []
        for v in _consts:
            if value == v:
                continue
            if v in cache:
                raise ValueError(f"{v!r} is already associated with another member")  # type: ignore
            aliases.append(v)
            cache[v] = None  # don't know the members' name yet!

        self = object.__new__(cls)
        self._value_  = value
        self._values_ = tuple(aliases)
        return self

    def __str__(self):
        return str(self._value_)

    def __hash__(self):
        return hash(self._value_)

    def __eq__(self, other: Any):
        return self._value_ == other or other in self._values_

    @classmethod
    def _missing_(cls, value: Any):
        cache = getattr(cls, '_alias_map_')
        # finish what was started during class creation and
        # fill in the members
        if '0_SETUP' in cache:
            for member in cls.__members__.values():
                for alias in member._values_:
                    cache[alias] = member
            del cache['0_SETUP']
        return cache.get(value, None)
