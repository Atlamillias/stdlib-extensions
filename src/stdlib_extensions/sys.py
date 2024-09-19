from sys import *
from typing import overload, Any
import types




@overload
def bytesizeof(obj: Any, memo: set | None = None, /) -> int: ...  # type: ignore[overload]
def bytesizeof(obj: Any, memo: set | None = None, /, *, __missing=object()) -> int:
    """Recursive `sys.getsizeof` implementation.

    Args:
        - obj: Target for calculation.

        - memo: Collection of object memory addresses already "counted" via
        recursive calls from within this function. Only include this argument
        if it is desired to exclude specific objects from the calculation.

    """
    size = getsizeof(obj)
    if memo is None:
        memo = set()

    obj_id = id(obj)
    if obj_id in memo:
        return 0

    memo.add(obj_id) # mark cyclic refs

    if isinstance(obj, dict):
        size += sum([bytesizeof(v, memo) for v in obj.values()])
        size += sum([bytesizeof(k, memo) for k in obj.keys()])
    elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes, bytearray)):
        size += sum([bytesizeof(i, memo) for i in obj])

    if hasattr(obj, '__dict__'):
        size += bytesizeof(obj.__dict__, memo)

    tp = type(obj)
    if not tp.__flags__ & (1 << 9):  # instance of slotted user-defined class
        for name in object.__dir__(obj):
            if isinstance(getattr(tp, name, None), types.MemberDescriptorType):
                obj_val = getattr(obj, name, __missing)
                if obj_val is not __missing:
                    size += bytesizeof(obj_val, memo)

    return size


