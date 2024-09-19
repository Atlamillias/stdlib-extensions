from functools import *
from .typing import overload, T_co, Any, Property, Callable, Self




class classproperty(Property[T_co]):
    """Creates class-bound, read-only properties.

    Once set, accessing the actual descriptor object can be difficult. To
    do so, use `getattr_static` function from the `inspect` module.
    """

    __slots__ = ()

    def __init__(self, fget: Callable[[Any], T_co] | None = None, doc: str | None = None):
        super().__init__(fget, None, None, doc)

    @overload
    def __get__(self, inst: Any, cls: type[Any] | None, /) -> T_co: ...
    @overload
    def __get__(self, inst: None, cls: type[Any] | None, /) -> Self: ...
    def __get__(self, inst: Any, cls: type[Any] | None = None):
        if cls is None:
            return self
        try:
            return self.fget(cls)  # type: ignore
        except TypeError:
            raise AttributeError(f'{type(self).__name__!r} object has no getter') from None

    def setter(self, *args: Any) -> Any:
        """Raises `NotImplementedError`."""
        raise NotImplementedError(f"{type(self).__name__!r} object does not support setters")

    def deleter(self, *args: Any) -> Any:
        """Raises `NotImplementedError`."""
        raise NotImplementedError(f"{type(self).__name__!r} object does not support deleters")
