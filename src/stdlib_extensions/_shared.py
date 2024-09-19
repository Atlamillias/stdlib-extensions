import sys
import types
from typing import Protocol, Sequence, TypeVar, Mapping, Callable, Iterable, Any, overload


T = TypeVar('T')



# [Dynamic Code Generation]

def create_module(
    name : str,
    body : Mapping[str, Any] | Iterable[tuple[str, Any]] = (),
    attrs: Mapping[str, Any] | Iterable[tuple[str, Any]] = (),
) -> types.ModuleType:
    """Create a new module object.

    Args:
        * name: Name for the new module.

        * body: Used to update the module's contents/dictionary.

        * attrs: Used to update the module's attributes.
    """
    m = types.ModuleType(name, None)
    for k, v in tuple(attrs):
        setattr(m, k, v)
    m.__dict__.update(body)

    return m


@overload
def create_function(name: str, args: Sequence[str], body: Sequence[str], return_type: T = Any, module: str = '', *, globals: dict[str,  Any] | None = None, locals: Mapping[str,  Any] | Iterable[tuple[str,  Any]] = ()) -> Callable[..., T]: ...  # type: ignore
def create_function(
    name: str,
    args: Sequence[str],
    body: Sequence[str],
    return_type: T = Any,
    module: str = '',
    *,
    globals: dict[str,  Any] | None = None,
    locals: Mapping[str,  Any] | Iterable[tuple[str,  Any]] = (),
    __default_module=create_module('')
) -> Callable[..., T]:
    """Compile a new function from source.

    Args:
        * name: Name for the new function.

        * args: A sequence containing argument signatures (as strings)
        for the new function. Each value in *args* should be limited to
        a single argument signature.

        * body: A sequence containing the source that will be executed when
        the when the new function is called. Each value in the sequence should
        be limited to one line of code.

        * return_type: Object to use as the function's return annotation.

        * module: Used to update the function's `__module__` attribute
        and to fetch the appropriate global mapping when *globals* is
        None.

        * globals: The global scope for the new function.

        * locals: The (non)local scope for the new function.


    When *globals* is None, this function will attempt to look up *module*
    in `sys.modules`, and will use the returned module's dictionary as
    *globals* if found. If the module could not be found or both *module*
    and *globals* are unspecified, *globals* defaults to the dictionary of
    a dedicated internal dummy module.

    Note that, when including *locals*, the created function's local scope
    will not be *locals*, but a new mapping created from its' contents.
    However, *globals* is used as-is.

    """
    assert not isinstance(body, str)
    body = '\n'.join(f'        {line}' for line in body)

    locals = dict(locals)
    locals["_return_type"] = return_type

    if globals is None:
        if module in sys.modules:
            globals = sys.modules[module].__dict__
        else:
            globals = __default_module.__dict__

    closure = (
        f"def __create_function__({', '.join(locals)}):\n"
        f"    def {name}({', '.join(args)}) -> _return_type:\n{body}\n"
        f"    return {name}"
    )

    scope = {}
    exec(closure, globals, scope)

    fn = scope["__create_function__"](**locals)
    fn.__module__   = module or __default_module.__name__
    fn.__qualname__ = fn.__name__ = name

    return fn


def ammend_closure(cls, func):
    """Update the class reference within a method's closure to match that
    of *cls*; correcting the binding of the local `__class__` variable
    and, by extension, fixing zero-argument `super()`.

    *cls* must share a name with the class found on the `__class__`
    attribute local to the function.
    """
    if hasattr(func, '__self__'):
        return func

    if isinstance(func, (classmethod, staticmethod)):
        fn = func.__func__
    elif isinstance(func, property):  # impossible for custom descriptors
        fn = func.fget
    else:
        fn = func

    closure = getattr(fn, '__closure__', None) or ()
    for cell in closure:
        try:
            contents = cell.cell_contents
        except:
            continue
        if isinstance(contents, type) and contents.__name__ == cls.__name__:
            cell.cell_contents = cls




# [ Types ]

class AbstractComposition(Protocol):
    """Base class for classes that wrap other objects.

    Instances of a base composition class must have a `_object_value_`
    attribute pointing to the wrapped object.
    """
    __slots__ = ()

    _object_value_: Any
