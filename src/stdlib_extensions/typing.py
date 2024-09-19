from typing_extensions import *
from typing import *
import os
import array
import types
import pathlib
import datetime
import threading




_MISSING = object()




# [ General TypeVars ]

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
T_contra = TypeVar("T_contra", contravariant=True)
N = TypeVar("N", float, int)
N_co = TypeVar("N_co", float, int, covariant=True)
N_contra = TypeVar("N_contra", float, int, contravariant=True)
KT = TypeVar("KT", bound=Hashable)
KT_co = TypeVar("KT_co", bound=Hashable, covariant=True)
KT_contra = TypeVar("KT_contra", bound=Hashable, contravariant=True)
VT = TypeVar("VT")
VT_co = TypeVar("VT_co", covariant=True)
VT_contra = TypeVar("VT_contra", contravariant=True)

P = ParamSpec("P")
CallableT = TypeVar('CallableT', bound=Callable)

# XXX: I THINK `AnyStr` is marked for deprecation?
try:
    AnyStr  # type: ignore
except NameError:
    AnyStr = TypeVar('AnyStr', bytes, str)
AnyStr_co = TypeVar('AnyStr_co', bytes, str, covariant=True)







# [ Structural Types ]

class SupportsRichComparison(Protocol):
    __slots__ = ()
    def __le__(self, other: Any, /) -> bool: ...
    def __lt__(self, other: Any, /) -> bool: ...
    def __eq__(self, other: Any, /) -> bool: ...
    def __gt__(self, other: Any, /) -> bool: ...
    def __ge__(self, other: Any, /) -> bool: ...

SupportsRichComparisonT = TypeVar('SupportsRichComparisonT', bound=SupportsRichComparison)


class SupportsStrCast(Protocol):
    __slots__ = ()
    def __str__(self) -> str: ...

SupportsStrCastT = TypeVar("SupportsStrCastT", bound=SupportsStrCast)


class SupportsIntCast(Protocol):
    __slots__ = ()
    def __int__(self) -> int: ...

SupportsIntCastT = TypeVar("SupportsIntCastT", bound=SupportsIntCast)


class SupportsBytesCast(Protocol):
    __slots__ = ()
    def __bytes__(self) -> bytes: ...

SupportsBytesCastT = TypeVar("SupportsBytesCastT", bound=SupportsBytesCast)


class SupportsSlice(Protocol[T_co]):
    __slots__ = ()
    def __getitem__(self, __slice: slice) -> Iterable[T_co]: ...

SupportsSliceT = TypeVar('SupportsSliceT', bound=SupportsSlice)


class SupportsView(Protocol[KT_co, VT_co]):
    __slots__ = ()
    def keys(self) -> Iterable[KT_co]: ...
    def values(self) -> Iterable[VT_co]: ...
    def items(self) -> Iterable[tuple[KT_co, VT_co]]: ...

SupportsViewT = TypeVar("SupportsViewT", bound=SupportsView)


class SupportsRead(Protocol[T_co]):
    __slots__ = ()
    def read(self) -> T_co: ...

SupportsReadT = TypeVar("SupportsReadT", bound=SupportsRead)


class SupportsWrite(Protocol[T_contra]):
    __slots__ = ()
    def write(self, obj: T_contra, /) -> Any: ...

SupportsWriteT = TypeVar("SupportsWriteT", bound=SupportsWrite)


class SupportsSend(Protocol[T_contra]):
    __slots__ = ()
    def send(self, obj: T_contra, /) -> Any: ...

SupportsSendT = TypeVar("SupportsSendT", bound=SupportsSend)


class SupportsRecv(Protocol):
    __slots__ = ()
    def recv(self) -> Any: ...

SupportsRecvT = TypeVar("SupportsRecvT", bound=SupportsRecv)


class Descriptor(Protocol[T_co]):
    __slots__ = ()
    @overload
    def __get__(self, __inst: None, __type: type[Any] | None) -> Self: ...
    @overload
    def __get__(self, __inst: T, __type: type[T] | None) -> T_co: ...

DescriptorT = TypeVar("DescriptorT", bound=Descriptor)


class DataDescriptor(Protocol[T_co, T_contra]):
    __slots__ = ()
    @overload
    def __get__(self, __inst: None, __type: type[Any] | None) -> Self: ...
    @overload
    def __get__(self, __inst: T, __type: type[T] | None) -> T_co: ...
    def __set__(self, __inst: Any, __value: T_contra) -> None: ...

DataDescriptorT = TypeVar("DataDescriptorT", bound=DataDescriptor)


class SizedArray(Protocol[T]):
    __slots__ = ()
    def __len__(self) -> int: ...
    def __iter__(self) -> Iterator[T]: ...
    @overload
    def __getitem__(self, __index: SupportsIndex, /) -> T: ...
    @overload
    def __getitem__(self, __slice: slice, /) -> Self: ...
    @overload
    def __setitem__(self, __key: SupportsIndex, __value: T, /) -> None: ...
    @overload
    def __setitem__(self, __key: slice, __value: Iterable[T], /) -> None: ...
    def __contains__(self, __value: Any, /) -> bool: ...

SizedArray.register(list)         # type: ignore
SizedArray.register(array.array)  # type: ignore
SizedArray.register(tuple)        # type: ignore

SizedArrayT = TypeVar('SizedArrayT', bound=SizedArray)







# [ Property Built-In ]

_PROPERTY_TYPE_INIT      = '_PropertyType__init'            # (bool) instance-level docstrings are writable
_PROPERTY_TYPE_INST_DOC  = '_PropertyType__inst_docstring'  # (str | None) instance-level docstring
_PROPERTY_TYPE_CLASS_DOC = '_PropertyType__class_docstring' # (str | None) class-level docstring


class _disabled_descriptor:
    __slots__ = ('cls', 'attrib', 'value', '_lock')

    __lock = threading.Lock()

    def __init__(self, cls: Any, attrib: str, lock: Any = None):
        self.cls    = cls
        self.attrib = attrib
        self._lock  = lock or self.__lock

    def __enter__(self):
        self.disable()
        return self

    def __exit__(self, *args):
        self.enable()

    def disable(self):
        self._lock.acquire()
        self.value = getattr(self.cls, self.attrib)
        # `delattr` doesn't work on metaclasses; or, at least not while
        # readying a new class with them.
        setattr(self.cls, self.attrib, None)

    def enable(self):
        setattr(self.cls, self.attrib, self.value)
        del self.value
        self._lock.release()


class _PropertyType(type):
    """Metaclass that helps classes emulate the certain behaviors of
    the `property` builtin class. Allows slotted classes to have readable
    and writable instance-level and class-level docstrings.
    """
    # NOTE: The above docstring is not available at runtime!

    __slots__ = ()

    @property
    def __doc__(self) -> str | None:
        return getattr(self, _PROPERTY_TYPE_CLASS_DOC)
    @__doc__.setter
    def __doc__(self, value: str | None):
        setattr(self, _PROPERTY_TYPE_CLASS_DOC, value)
    @__doc__.deleter
    def __doc__(self):
        self.__doc__ = None  # type: ignore

    def __new__(
        mcls,
        name,
        bases,
        namespace,
        *,
        __lock=threading.Lock(),
        **kwargs,
    ):
        # [once per inheritance tree] ensure that instance docstrings
        # will be writable
        if not any(hasattr(b, _PROPERTY_TYPE_INIT) for b in bases):
            if '__slots__' in namespace:
                namespace['__slots__'] = [*namespace['__slots__'], _PROPERTY_TYPE_INST_DOC]
            namespace[_PROPERTY_TYPE_CLASS_DOC] = namespace.pop('__doc__', None)
            namespace['__doc__'] = property(
                lambda self: getattr(self, _PROPERTY_TYPE_INST_DOC, None) or getattr(self.fget, '__doc__', None),
                lambda self, v: setattr(self, _PROPERTY_TYPE_INST_DOC, v),
            )
            namespace[_PROPERTY_TYPE_INIT] = True

            return super().__new__(mcls, name, bases, namespace, **kwargs)

        cls = super().__new__(mcls, name, bases, namespace, **kwargs)

        # TODO/FIXME:
        #   - check `cls.__dict__` for `__doc__`
        #   - check if Python sets `__doc__` to None for inherited docstrings

        # A new `__doc__` is set during the class' creation, overridding
        # the inherited instance-level descriptor.
        if isinstance(cls.__doc__, (type(None), str)):
            # HACK: `PropertyType.__doc__` is a data descriptor -- `__doc__`
            # needs to be updated without invoking it.
            with _disabled_descriptor(_PropertyType, '__doc__', __lock):
                setattr(cls, _PROPERTY_TYPE_CLASS_DOC, cls.__doc__)
                del cls.__doc__

        return cls

    def __instancecheck__(self, inst: Any) -> bool:
        return super().__instancecheck__(inst) or isinstance(inst, property)

    def __subclasscheck__(self, cls: type) -> bool:
        return super().__subclasscheck__(cls) or issubclass(cls, property)


class Property(Generic[T_co], cast(type[property], object), metaclass=_PropertyType):
    """A fully-extensible generic emulation of the built-in `property`
    class. Derived classes are considered subclasses of `property`.

    Several methods invoke `__getstate__` and `__setstate__`, which
    can be overridden when needed.
    """

    __slots__ = ('_fget', '_fset', '_fdel')

    @overload
    def __new__(cls, fget: Callable[[Any], T], fset: Callable[[Any, Any], Any] | None = ..., fdel: Callable[[Any], Any] | None = ..., doc: str | None = ...) -> Self: ...
    @overload
    def __new__(cls, fget: None = ..., fset: Callable[[Any, Any], Any] | None = ..., fdel: Callable[[Any], Any] | None = ..., doc: str | None = ...) -> Self: ...
    @overload
    def __new__(cls, *args, **kwargs) -> Any: ...
    def __new__(cls, *args, **kwargs) -> Any: ...
    del __new__

    def __init__(
        self,
        fget: Callable[[Any], T_co] | None = None,
        fset: Callable[[Any, Any], Any] | None = None,
        fdel: Callable[[Any], Any] | None = None,
        doc : str | None = None
    ):
        self._fget   = fget
        self._fset   = fset
        self._fdel   = fdel
        self.__doc__ = doc   # type: ignore

    @property
    def fget(self):  # pyright: ignore[reportIncompatibleVariableOverride]
        return self._fget

    @property
    def fset(self):  # pyright: ignore[reportIncompatibleVariableOverride]
        return self._fset

    @property
    def fdel(self):  # pyright: ignore[reportIncompatibleVariableOverride]
        return self._fdel

    def __getstate__(self) -> tuple[tuple[Callable | None, Callable | None, Callable | None, str | None], dict[str, Any] | None]:
        """Return the simplified state of this object.

        The value returned is a 2-tuple; one of Python's "default state" formats.
        The first item is another tuple containing (in order) `Property.__init__`
        positional arguments -- the state implemented by the `Property` class. The
        second item in the tuple is any "additional state" implemented via
        subclassing, which is None (default) or an "attribute-to-value" dictionary.
        """
        return (self.fget, self.fset, self.fdel, self.__doc__), getattr(self, '__dict__', None)

    def __setstate__(self, state: tuple[tuple[Callable | None, Callable | None, Callable | None, str | None], dict[str, Any] | None]):
        """Update the object from a simplified state.

        Args:
            - state: A 2-tuple, where the first item is a 4-tuple and the second
            is None or a "attribute-to-value" dictionary.


        When setting the object state, `Property.__init__` is explicitly called
        and receives values within the first item in *state*. If the second value
        is not None, it must be a dictionary -- `setattr` is used to update the
        object with the "attribute-to-value" pairs it contains.
        """
        Property.__init__(self, *state[0])
        if state[1] is not None:
            for k,v in state[1].items():
                setattr(self, k, v)

    def __copy__(self) -> Self:
        p = self.__new__(type(self))
        p.__setstate__(self.__getstate__())
        return p

    # XXX: As of Python 3.12, `__replace__` is recognized as a
    # standardized method.
    @overload
    def __replace__(self, *, fget: Callable[[Any], T], fset: Callable[[Any, Any], Any] | None = ..., fdel: Callable[[Any], Any] | None = ..., doc : str | None = ..., **kwargs) -> 'Property[T]': ...
    @overload
    def __replace__(self, *, fget: None, fset: Callable[[Any, Any], Any] | None = ..., fdel: Callable[[Any], Any] | None = ..., doc : str | None = ..., **kwargs) -> Self: ...
    @overload
    def __replace__(self, *, fset: Callable[[Any, Any], Any] | None = ..., fdel: Callable[[Any], Any] | None = ..., doc : str | None = ..., **kwargs) -> Self: ...
    def __replace__(self, *, fget: Any = _MISSING, fset: Any = _MISSING, fdel: Any = _MISSING, doc: Any = _MISSING, **kwargs) -> Any:
        prop_state, user_state = self.__getstate__()
        prop_state = tuple(
            nv if nv is not _MISSING else ov
            for nv, ov in zip((fget, fset, fdel, doc), prop_state)
        )

        if kwargs:
            if user_state is None:
                user_state = {}
            user_state.update(kwargs)

        p = self.__new__(type(self))
        p.__setstate__((prop_state, user_state))  # type: ignore
        return p

    @overload
    def __get__(self, inst: Any, cls: type[Any] | None, /) -> T_co: ...
    @overload
    def __get__(self, inst: None, cls: type[Any] | None, /) -> Self: ...
    def __get__(self, inst: Any, cls: type[Any] | None = None):
        if inst is None:
            return self
        try:
            return self._fget(inst)  # type: ignore
        except TypeError:
            if self._fget is None:
                raise AttributeError(f'{type(self).__name__!r} object has no getter') from None
            raise

    def __set__(self, inst: Any, value: Any) -> None:
        try:
            self._fset(inst, value)  # type: ignore
        except TypeError:
            raise AttributeError(
                f"cannot set read-only attribute of {type(inst).__name__!r} object"
            ) from None

    def __delete__(self, inst: Any) -> None:
        try:
            self._fdel(inst)  # type: ignore
        except TypeError:
            raise AttributeError(f"cannot delete read-only attribute of {type(inst).__name__!r} object")

    def getter(self, fget: Callable[[Any], T], /):
        """Return a copy of this property with a different getter."""
        return self.__replace__(fget=fget)

    def setter(self, fset: Callable[[Any, Any], Any], /) -> Self:
        """Return a copy of this property with a different setter."""
        return self.__replace__(fset=fset)

    def deleter(self, fdel: Callable[[Any], Any], /) -> Self:
        """Return a copy of this property with a different deleter."""
        return self.__replace__(fdel=fdel)








# [ Aliases ]

Mappable = TypeAliasType("Mappable", Mapping[KT, VT] | Iterable[tuple[KT, VT]], type_params=(KT, VT))
Array = array.ArrayType
StrPath = str | pathlib.Path
PathLike = os.PathLike
FileLike = TypeAliasType("FileLike", PathLike[AnyStr_co] | IO[AnyStr_co] | str, type_params=(AnyStr_co,))
MappingProxy = types.MappingProxyType
Function = types.FunctionType
Method = types.MethodType
Module = types.ModuleType
Date = datetime.date
Time = datetime.time
DateTime = datetime.datetime


if TYPE_CHECKING:
    from numpy import (  # type: ignore
        generic as _np_generic,
        ndarray as _np_ndarray,
        dtype as _np_dtype,
    )
else:  # no stringification w/`import __future__.annotations`
    _np_generic = "_np_generic"
    _np_ndarray = "_np_ndarray"

_NpDataType = TypeVar("_NpDataType", bound=_np_generic)
# ndarray-like
Vector = TypeAliasType('Vector', '_np_ndarray[tuple[int], _np_dtype[_NpDataType]] | SizedArray[_NpDataType]', type_params=(_NpDataType,))
Matrix = TypeAliasType('Matrix', '_np_ndarray[tuple[int, int], _np_dtype[_NpDataType]] | SizedArray[Vector[_NpDataType]]', type_params=(_NpDataType,))
Tensor = TypeAliasType('Tensor', '_np_ndarray[tuple[int, int, int], _np_dtype[_NpDataType]] | SizedArray[Matrix[_NpDataType]]', type_params=(_NpDataType,))








# [ Utilities ]

@overload
def cast_to(tp: type[T]) -> Callable[[Any], T]: ...
@overload
def cast_to(tp: T) -> Callable[[Any], T]: ...
@overload
def cast_to(tp: type[T], value: Any) -> T: ...
@overload
def cast_to(tp: T, value: Any) -> T: ...
def cast_to(tp: Any, value: Any = _MISSING) -> Any:
    """Equivelent to `typing.cast` but can be used as a decorator."""
    if value is _MISSING:
        return lambda value: value
    return value
