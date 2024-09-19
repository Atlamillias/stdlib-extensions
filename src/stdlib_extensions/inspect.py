from inspect import *
import io
import enum
import pathlib
from .typing import (
    overload,
    Any,
    StrPath,
    IO,
    Sequence,
    Mapping,
    Callable,
    TypeIs
)




class PyTypeFlag(enum.IntFlag):
    """Python type bit masks (`type.__flags__`, `PyTypeObject.tp_flags`).

    A type's flag bit mask is created when the object is defined --
    changing it from Python does nothing helpful.
    """
    STATIC_BUILTIN           = (1 << 1)  # internal & undocumented
    MANAGED_WEAKREF          = (1 << 3)
    MANAGED_DICT             = (1 << 4)
    PREHEADER                = (MANAGED_WEAKREF | MANAGED_DICT)
    SEQUENCE                 = (1 << 5)
    MAPPING                  = (1 << 6)
    DISALLOW_INSTANTIATION   = (1 << 7)  # `tp_new == NULL`
    IMMUTABLETYPE            = (1 << 8)
    HEAPTYPE                 = (1 << 9)
    BASETYPE                 = (1 << 10)  # allows subclassing
    HAVE_VECTORCALL          = (1 << 11)
    READY                    = (1 << 12)  # fully constructed type
    READYING                 = (1 << 13)  # type is under construction
    HAVE_GC                  = (1 << 14)  # allow garbage collection
    HAVE_STACKLESS_EXTENSION = (3 << 15)  # Stackless Python
    METHOD_DESCRIPTOR        = (1 << 17)  # behaves like unbound methods
    VALID_VERSION_TAG        = (1 << 19)  # has up-to-date type attribute cache
    ABSTRACT                 = (1 << 20)  # `ABCMeta.__new__`
    MATCH_SELF               = (1 << 22)  # "builtin" class pattern-matting behavior (undocumented, internal)
    ITEMS_AT_END             = (1 << 23)  # items at tail end of instance memory
    LONG_SUBCLASS            = (1 << 24)  # |- used for `Py<type>_Check`, `isinstance`, `issubclass`
    LIST_SUBCLASS            = (1 << 25)  # |
    TUPLE_SUBCLASS           = (1 << 26)  # |
    BYTES_SUBCLASS           = (1 << 27)  # |
    UNICODE_SUBCLASS         = (1 << 28)  # |
    DICT_SUBCLASS            = (1 << 29)  # |
    BASE_EXC_SUBCLASS        = (1 << 30)  # |
    TYPE_SUBCLASS            = (1 << 31)  # |


def hasfeature(cls: type[Any], /, flags: PyTypeFlag | int) -> bool:
    """Python implementation of the Python C-API `PyType_HasFeature`
    macro.
    """
    return bool(cls.__flags__ & flags)




def iscclass(obj: type[Any] | Any, /) -> TypeIs[type[Any]]:
    """Return True if *obj* is a class implemented in C."""
    return isinstance(obj, type) and not hasfeature(obj, PyTypeFlag.HEAPTYPE)


def iscfunction(obj: type[Any] | Any, /) -> TypeIs[Callable]:
    """Return True if *obj* is a function or bound method
    implemented in C.

    This is the equivelent of `inspect.isbuiltin(o)`, but is named
    much more appropriately.
    """
    return isinstance(obj, type(print))


def ispythonbuiltin(obj: type[Any] | Any, /) -> bool:
    """Return True if *obj* is a Python built-in class or object.
    """
    try:
        return obj.__module__ == type.__module__
    except:
        return False


@overload
def ismapping(obj: type[Any] | Any, /) -> TypeIs[Mapping]: ...  # pyright: ignore[reportInconsistentOverload]
def ismapping(obj: type[Any] | Any, /, *, __key=object()) -> Any:
    """Return True if *obj* implements the minimal behavior of a
    mapping.

    At minimum, a mapping must implement the `__len__`, `__contains__`,
    `__iter__`, and `__getitem__` methods. It does not need to be
    an instance of `dict` or `Mapping`.

    While not included in the mapping protocol, this function ensures
    that `__getitem__` raises `KeyError` when it does not contain a
    key. This is done to differentiate between mappings and sequences,
    since the standard protocols that define them overlap.

    This function returns False when *obj* is a class.
    """
    # Most classes implement `__class_getitem__`, which could falsify
    # the below check.
    if isinstance(obj, type):
        return False
    # Could also throw it a non-hashable and check for `TypeError`, but
    # it feels more ambiguous than `KeyError` in this context.
    try:
        obj[__key]
    except KeyError: pass
    except:
        return False
    return (
        hasattr(obj, '__len__')
        and
        hasattr(obj, '__contains__')
        and
        hasattr(obj, '__iter__')
    )


def issequence(obj: type[Any] | Any, /) -> TypeIs[Sequence]:
    """Return True if *obj* implements the minimal behavior of a
    sequence.

    At minimum, a sequence must implement the `__len__`, `__contains__`,
    `__iter__`, and `__getitem__` methods. It does not need to be
    an instance of `list` or `Sequence`.

    While not included in the sequence protocol, this function ensures
    that `__getitem__` raises `IndexError` when provided an index
    outside of its' range. This is done to differentiate between
    mappings and sequences, since the standard protocols that define
    them overlap.

    This function returns False when *obj* is a class.
    """
    # Most classes implement `__class_getitem__`, which could falsify
    # the below check.
    if isinstance(obj, type):
        return False
    try:
        obj[len(obj)]
    except IndexError: pass
    except:
        return False
    return hasattr(obj, '__contains__') and hasattr(obj, '__iter__')


def isfilepath(obj: type[Any] | Any, /) -> TypeIs[StrPath]:
    """Return True if *obj* could be a file path. Note that *obj*
    does not need to point to an existing file.
    """
    if hasattr(obj, '__fspath__'):
        if isinstance(obj, type):
            return False
        return True
    if not isinstance(obj, str):
        return False

    try:
        pathlib.Path(obj)
        return True
    except:
        return False


def isfilelike(obj: type[Any] | Any, /) -> TypeIs[IO]:
    """Return True if *obj* is seemingly file-like.

    This function checks if *obj* is an instance of one of many
    abstract IO classes. If that fails, then this function checks
    if the object has the `.close`, `.read`, and `.write` methods.

    Note that distinctions aren't made between the stream's
    content type; only by their minimal public behaviors and API.
    """
    if isinstance(obj, (IO, io.TextIOBase, io.BufferedIOBase, io.RawIOBase)):
        return True

    try:
        if not callable(obj.read):
            return False
        if not callable(obj.write):
            return False
        if not callable(obj.close):
            return False
    except:
        return False

    if isinstance(obj, type):
        return False

    return True
