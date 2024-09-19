from numbers import *
from ._shared import AbstractComposition
from .typing import Any, Protocol, Literal, SupportsIndex, TypeVar, Self




_N = TypeVar('_N', bound=Number, covariant=True)




# [ Primitives ]

@Number.register
class ComposedNumber(AbstractComposition, Protocol[_N]):
    """Base composition class for types whose instances
    represent a numeric value."""
    __slots__ = ()

    _object_value_: _N


@Complex.register
class ComposedComplex(ComposedNumber, Protocol):
    __slots__ = ()

    _object_value_: Complex

    def __hash__(self):
        return hash(self._object_value_)

    def __bool__(self):
        return bool(self._object_value_)

    def __eq__(self, other: Any):
        return self._object_value_ == other

    def __complex__(self):
        return complex(self._object_value_)

    def __neg__(self):
        return -self._object_value_

    def __pos__(self):
        return +self._object_value_

    def __add__(self, other: Any):
        return self._object_value_ + other

    def __radd__(self, other: Any):
        return other + self._object_value_

    def __sub__(self, other: Any):
        return self._object_value_ - other

    def __rsub__(self, other: Any):
        return other - self._object_value_

    def __mul__(self, other: Any):
        return self._object_value_ * other

    def __rmul__(self, other: Any):
        return other * self._object_value_

    def __truediv__(self, other: Any):
        return self._object_value_ / other

    def __rtruediv__(self, other: Any):
        return other / self._object_value_

    def __pow__(self, exponent: Integral):
        return self._object_value_ ** exponent

    def __rpow__(self, base: Integral):
        return base ** self._object_value_

    def __abs__(self):
        return abs(self._object_value_)

    @property
    def real(self):
        return self._object_value_.real

    @property
    def imag(self):
        return self._object_value_.imag

    def conjugate(self):
        return self._object_value_.conjugate()


@Real.register
class ComposedReal(ComposedComplex, Protocol):
    __slots__ = ()

    _object_value_: Real  # type: ignore

    def __float__(self):
        return float(self._object_value_)

    def __complex__(self):
        return complex(float(self))

    def __trunc__(self):
        return self._object_value_.__trunc__()

    def __floor__(self):
        return self._object_value_.__floor__()

    def __ceil__(self):
        return self._object_value_.__ceil__()

    def __round__(self, ndigits: int | None = None):
        return round(self._object_value_, ndigits)

    def __divmod__(self, other: Any):
        return (self // other, self % other)

    def __rdivmod__(self, other: Any):
        return (other // self, other % self)

    def __floordiv__(self, other: Any):
        return self._object_value_ // other

    def __rfloordiv__(self, other: Any):
        return other // self._object_value_

    def __mod__(self, other: Any):
        return self._object_value_ % other

    def __rmod__(self, other: Any):
        return other % self._object_value_

    def __lt__(self, other: Any):
        return self._object_value_ < other

    def __le__(self, other: Any):
        return self._object_value_ <= other

    def __ge__(self, other: Any):
        return self._object_value_ >= other

    def __gt__(self, other: Any):
        return self._object_value_ > other

    @property
    def real(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        return +self

    @property
    def imag(self):
        return 0

    def conjugate(self):
        return +self


@Rational.register
class ComposedRational(ComposedReal, Protocol):
    __slots__ = ()

    _object_value_: Rational  # type: ignore

    def __float__(self):
        return int(self.numerator) / int(self.denominator)

    @property
    def numerator(self):
        return self._object_value_.numerator

    @property
    def denominator(self):
        return self._object_value_.denominator


@Integral.register
class ComposedIntegral(ComposedRational, Protocol):
    __slots__ = ()

    _object_value_: Integral  # type: ignore

    def __int__(self):
        return int(self._object_value_)

    __index__ = __int__

    def __pow__(self, exponent: Integral, modulus: Integral | None = None):
        return pow(self._object_value_, exponent, modulus)

    def __lshift__(self, other):
        return self._object_value_ << other

    def __rlshift__(self, other):
        return other << self._object_value_

    def __rshift__(self, other):
        return self._object_value_ >> other

    def __rrshift__(self, other):
        return other >> self._object_value_

    def __and__(self, other):
        return self._object_value_ & other

    def __rand__(self, other):
        return other & self._object_value_

    def __xor__(self, other):
        return self._object_value_ ^ other

    def __rxor__(self, other):
        return other ^ self._object_value_

    def __or__(self, other):
        return self._object_value_ | other

    def __ror__(self, other):
        return other | self._object_value_

    def __invert__(self):
        return ~self._object_value_

    @property
    def numerator(self):  # pyright: ignore[reportIncompatibleMethodOverride]
        return +self

    @property
    def denominator(self):
        return 1








# [ High-Level ]

class ComposedFloat(ComposedReal, Protocol):
    """Emulates the `float` built-in type."""
    __slots__ = ()

    _object_value_: float  # type: ignore

    def __int__(self):
        return int(self._object_value_)

    @classmethod
    def fromhex(cls, *args, **kwargs) -> Any:
        raise NotImplementedError

    def as_integer_ratio(self) -> tuple[int, int]:
        return self._object_value_.as_integer_ratio()

    def hex(self) -> str:
        return self._object_value_.hex()

    def is_integer(self) -> bool:
        return self._object_value_.is_integer()


class ComposedIFloat(ComposedFloat):
    """Emulates the `float` built-in type. Defines in-place operators
    that update `self._object_value_` and return `self`."""
    __slots__ = ()

    def __iadd__(self, other: Real) -> Self:
        self._object_value_ = self + other
        return self

    def __isub__(self, other: Real) -> Self:
        self._object_value_ = self - other
        return self

    def __imul__(self, other: Real) -> Self:
        self._object_value_ = self * other
        return self

    def __itruediv__(self, other: Real) -> Self:
        self._object_value_ = self / other
        return self

    def __ifloordiv__(self, other: Real) -> Self:
        self._object_value_ = self // other
        return self

    def __imod__(self, other: Real) -> Self:
        self._object_value_ = self % other
        return self





class ComposedInt(ComposedIntegral, Protocol):
    """Emulates the `int` built-in type."""
    __slots__ = ()

    _object_value_: int  # type: ignore

    @classmethod
    def from_bytes(cls, *args, **kwargs) -> Any:
        raise NotImplementedError

    def as_integer_ratio(self) -> tuple[int, Literal[1]]:
        return self._object_value_.as_integer_ratio()

    def conjugate(self) -> int:
        return self._object_value_.conjugate()

    def bit_length(self) -> int:
        return self._object_value_.bit_length()

    def bit_count(self) -> int:
        return self._object_value_.bit_count()

    def to_bytes(
        self,
        length: SupportsIndex = 1,
        byteorder: Literal["little", "big"] = "big",
        *,
        signed: bool = False
    ) -> bytes:
        return self._object_value_.to_bytes(length, byteorder, signed=signed)


class ComposedIInt(ComposedInt):
    """Emulates the `int` built-in type. Defines in-place operators
    that update `self._object_value_` and return `self`."""
    __slots__ = ()

    def __iadd__(self, other: Integral) -> Self:
        self._object_value_ = self + other
        return self

    def __isub__(self, other: Integral) -> Self:
        self._object_value_ = self - other
        return self

    def __imul__(self, other: Integral) -> Self:
        self._object_value_ = self * other
        return self

    def __itruediv__(self, other: Integral) -> Self:
        self._object_value_ = self / other
        return self

    def __ifloordiv__(self, other: Integral) -> Self:
        self._object_value_ = self // other
        return self

    def __imod__(self, other: Integral) -> Self:
        self._object_value_ = self % other
        return self

    def __ilshift__(self, other: Integral):
        self._object_value_ = self << other
        return self

    def __irshift__(self, other: Integral):
        self._object_value_ = self >> other
        return self

    def __iand__(self, other: Integral):
        self._object_value_ = self & other
        return self

    def __ixor__(self, other: Integral):
        self._object_value_ = self ^ other
        return self

    def __ior__(self, other: Integral):
        self._object_value_ = self | other
        return self
