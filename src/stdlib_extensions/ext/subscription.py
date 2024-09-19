import enum
import inspect
import threading
import functools
import contextlib
import collections
from .. import _shared
from ..typing import (
    overload,
    T, T_co, Any,
    Mapping, MutableMapping, Callable, TypeVar, ClassVar, Protocol, Property
)




class EventFlag(enum.IntFlag):
    ON_SET       = 4
    ON_DEL       = 8
    ON_CALL      = 16
    ON_PRE_CALL  = 32
    ON_POST_CALL = ON_CALL




def _verify_subscribable_type(cls: type[Any]):
    if not issubclass(cls, Subscribable):
        raise TypeError(f"class must be a subclass of {Subscribable.__name__!r}")


def _set_subscribable_member(cls: type['Subscribable'], name: str, flags: int):
    try:
        event_fields = cls.__dict__['__event_fields__']
    except KeyError:
        assert issubclass(cls, Subscribable)
        event_fields = cls.__event_fields__ = collections.ChainMap({})

        maps = event_fields.maps
        for parent in cls.__mro__[1:]:
            cm = getattr(parent, '__event_fields__', None)
            if cm is not None:
                cm = cm.maps[0]
                if all(cm is not m for m in maps):
                    maps.append(cm)

    event_fields[name] = flags  # type: ignore




class _SubscribableField(Property[T_co]):
    __slots__ = ('_on_set', '_on_del')

    def __init__(
        self,
        fget  : Any = None,
        fset  : Any = None,
        fdel  : Any = None,
        doc   : Any = None,
        *,
        on_set: Any = None,
        on_del: Any = None,
    ):
        super().__init__(fget, fset, fdel, doc)

        if on_set is None and on_del is None:
            on_set = True
            on_del = False
        else:
            on_set = bool(on_set)
            on_del = bool(on_del)
        self._on_set = on_set
        self._on_del = on_del

    def __getstate__(self) -> tuple[tuple[Callable[..., Any] | None, Callable[..., Any] | None, Callable[..., Any] | None, str | None], dict[str, Any]]:
        return super().__getstate__()[0], {"_on_set": self._on_set, "_on_del": self._on_del}

    @overload
    def __call__(self, fget: Callable[[Any], T]) -> Property[T]: ...
    @overload
    def __call__(self, fget: None) -> Property[Any]: ...
    def __call__(self, fget: Any) -> Any:
        return self.getter(fget)

    def __set_name__(self, cls: type['Subscribable'], name: str):
        assert getattr(cls, name) is self
        _verify_subscribable_type(cls)

        flag_set = 0 if not self._on_set else int(EventFlag.ON_SET)
        flag_del = 0 if not self._on_del else int(EventFlag.ON_DEL)

        create_fn = functools.partial(
            _shared.create_function,
            return_type=Any,
            module=cls.__module__,
            locals={'__class__': cls},
        )

        fget = self._fget
        fset = self._fset
        fdel = self._fdel

        # emulate a normal attribute w/o restrictions
        if not (fget or fset or fdel):
            if not (flag_set or flag_del):
                return delattr(cls, name)

            prop = property(
                create_fn(
                    'subscribable_field_fget',
                    ['self'],
                    [
                        f'try:',
                        f'  return self.__cache__["{name}"]',
                        f'except KeyError:',
                        f'  raise AttributeError(f"{{__class__.__name__!r}} object has no attribute {name!r}") from None'
                    ],
                ),
                create_fn(  # type: ignore
                    'subscribable_field_fset',
                    ['self', 'value'],
                    [
                        f'self.__cache__["{name}"] = value',
                        f'self.{Subscribable.notify.__name__}("{name}", {flag_set})' if flag_set else ''
                    ]
                ),
                create_fn(  # type: ignore
                    'subscribable_field_fdel',
                    ['self'],
                    [
                        f'try:',
                        f'  del self.__cache__[{name}]',
                        f'except KeyError:',
                        f'  raise AttributeError(f"{{__class__.__name__!r}} object has no attribute {name!r}") from None',
                        f'self.{Subscribable.notify.__name__}("{name}", {flag_del})' if flag_del else '',
                    ]
                )
            )
        # act like a proper built-in property object
        else:
            if not (flag_set or flag_del):
                return setattr(cls, name, property(fget, fset, fdel, self.__doc__))

            if flag_set:
                if fset is None:
                    raise ValueError(f"'on_set' is True, but no {name!r} does not have a setter")
                fset = functools.update_wrapper(
                    create_fn(
                        fset.__name__,
                        ['self', 'value'],
                        [
                            f'_fn(self, value)',
                            f'self.{Subscribable.notify.__name__}("{name}", {flag_set})',
                        ],
                        locals={'__class__': cls, '_fn': fset}
                    ),
                    fset
                )
            if flag_del:
                if fdel is None:
                    raise ValueError(f"'on_del' is True, but no {name!r} does not have a deleter")
                fdel = functools.update_wrapper(
                    create_fn(
                        fdel.__name__,
                        ['self'],
                        [
                            f'_fn(self)',
                            f'self.{Subscribable.notify.__name__}("{name}", {flag_del})',
                        ],
                        locals={'__class__': cls, '_fn': fdel}
                    ),
                    fdel
                )
            prop = property(
                fget,
                fset,
                fdel,
                self.__doc__
            )

        _set_subscribable_member(cls, name, flag_set | flag_del)

        setattr(cls, name, prop)


@overload
def subscribable_field(*, on_set: bool = ..., on_del: bool = ...) -> Property[Any]: ...
@overload
def subscribable_field(fget: None = ..., /, fset: Callable[[Any, Any], Any] | None = ..., fdel: Callable[[Any], Any] | None = ..., doc : str | None = ..., *, on_set: bool = ..., on_del: bool = ...) -> Property[Any]: ...
@overload
def subscribable_field(fget: Callable[[Any], T], /, fset: Callable[[Any, Any], Any] | None = ..., fdel: Callable[[Any], Any] | None = ..., doc : str | None = ..., *, on_set: bool = ..., on_del: bool = ...) -> Property[T]: ...
def subscribable_field(fget: Any = None, /, *args, **kwargs) -> Any:
    """Returns a `property` object that enables notifications to be sent when
    the target member is updated. Can be used as a decorator.

        >>> class Object(Subscribable):
        ...     x = subscribable_field()
        ...
        ...     @subscribable_field
        ...     def y(self):
        ...         return self._y
        ...     @y.setter
        ...     def y(self, value):
        ...         self._y = value
        ...
        ...     def __init__(self):
        ...         self.__cache__ = {}
        >>>
        >>> values = []
        >>>
        >>> def callback(subscribable, field, event):
        ...     values.append((event, field, getattr(subscribable, field)))
        >>>
        >>> o = Object()
        >>> o.subscribe("x", EventFlag.ON_SET, callback)
        >>> o.subscribe("y", EventFlag.ON_SET, callback)
        >>> o.x = 8
        >>> o.y = 6
        >>>
        >>> values
        [(4, 'x', 8), (4, 'y', 6)]

    Args:
    :type fget: ``
    :param fget: Mirrors `property().fget`. Defaults to None.

    :type fset: ``
    :param fset: Mirrors `property().fset`. Defaults to None.

    :type fdel: ``
    :param fdel: Mirrors `property().fdel`. Defaults to None.

    :type doc: ``
    :param doc: Mirrors `property().__doc__`. Defaults to None.

    :type on_set: ``
    :param on_set: If True, allows subscribers to register callbacks to the
        member's `EventType.ON_SET` events, firing when the target attribute
        is set. Defaults to None.

    :type on_del: ``
    :param on_del: If True, allows subscribers to register callbacks to the
        member's `EventType.ON_DEL` events, firing when the target attribute
        is deleted. Defaults to None.


    The behavior of the returned descriptor varies depending on its' `.fget`,
    `.fset`, and `.fdel` attributes at the time the defining class is created.
    If ALL of them are None, they are ALL automatically created; the member
    acts like a normal instance attribute without restrictions, but with the
    added behavior of sending notifications to subscribers as they are set
    and/or deleted. Otherwise, only the getter, setter and deleter found on
    the descriptor are used -- the setter and/or deleter will be updated to
    manage notifications if they are set. In this case, a setter or deleter
    must be set if `on_set` or `on_del` is True respectively, since they won't
    be automatically created if they are missing.

    The member's field name is the name of the descriptor's `.fget` function
    (if set), falling back to the name of the variable the descriptor is
    assigned to, at the time the defining class is created.

    If the descriptor is added to a class' dictionary after the class itself
    has been created, the descriptor's `__set_name__` method must be called
    manually.

    Use the descriptor returned by this function as if it were an instance
    of `property`.

    If *on_set* and *on_del* are both omitted, *on_set* will default to True
    and *on_del* will default to False. Otherwise, omitted keyword-only
    arguments default to False.

    When used as a decorator, "calling" it e.g. `@subscribable_field()` is
    optional. However, it must be called when it is desired to include keyword
    arguments (refer to the above behavior when not calling it e.g. omitting all
    keyword-only arguments).
    """
    return _SubscribableField(fget, *args, **kwargs)



class _SubscribableMethod:
    __slots__ = ('_fn', '_on_pre_call', '_on_post_call')

    def __init__(self, fn: Any = None, /, *, on_pre_call: Any = None, on_post_call: Any = None):
        self._fn = fn
        if on_pre_call is None and on_post_call is None:
            self._on_pre_call  = False
            self._on_post_call = True
        else:
            self._on_pre_call  = bool(on_pre_call)
            self._on_post_call = bool(on_post_call)

    _MISSING = object()

    def __call__(self, fn: Any = _MISSING, *args, **kwargs) -> Any:
        if self._fn is not None:
            self._fn = fn
            return self
        # for if someone decides to call the decorated method within the class
        # definition, adhering to the `subscribable_method` function's signature
        if fn is not self._MISSING:
            args = (fn, *args)
        return self._fn(*args, **kwargs)

    def __set_name__(self, cls: type['Subscribable'], name: str):
        assert getattr(cls, name) is self
        _verify_subscribable_type(cls)

        flag_pre  = 0 if not self._on_pre_call else int(EventFlag.ON_PRE_CALL)
        flag_post = 0 if not self._on_post_call else int(EventFlag.ON_POST_CALL)

        fn = self._fn

        if not (flag_pre or flag_post):
            return setattr(cls, name, fn)

        mthd_sig = inspect.signature(fn)
        # TODO:
        #   - build w/real arg signature to prevent variadic unpacking overhead
        # FIXME:
        #   - The method does not exist within the class body on definition, so
        #   zero-argument super() calls fail due to __class__ missing in closure
        #   cells. This is not a simple fix.
        notif_method = functools.update_wrapper(
            _shared.create_function(
                fn.__name__,
                ('self', '*args', '**kwargs'),
                (
                    f'self.notify("{fn.__name__}", {flag_pre})' if flag_pre else '',
                    'res = _fn(self, *args, **kwargs)',
                    f'self.notify("{fn.__name__}", {flag_post})' if flag_post else '',
                    'return res'
                ),
                mthd_sig.return_annotation,
                fn.__module__,
                locals={
                    '_fn'  : fn,
                }
            ),
            fn
        )

        _set_subscribable_member(cls, name, flag_pre | flag_post)

        setattr(cls, name, notif_method)


SubscribableMethodT = TypeVar("SubscribableMethodT", bound=Callable)

@overload
def subscribable_method(*, on_pre_call: bool = ..., on_post_call: bool = ...) -> Callable[[SubscribableMethodT], SubscribableMethodT]: ...
@overload
def subscribable_method(fn: SubscribableMethodT, /, *, on_pre_call: bool = ..., on_post_call: bool = ...) -> SubscribableMethodT: ...
def subscribable_method(*args, **kwargs) -> Any:  # type: ignore
    """Wraps a method to send pre and/or post-call notifications. Can be used as
    a decorator.

    Args:
    :type fn: ``
    :param fn: The method in which subscriptions will be enabled for.

    :type on_pre_call: ``
    :param on_pre_call: If True, allows subscribers to register callbacks to the
        method's `EventType.ON_PRE_CALL` events. Defaults to None.

    :type on_post_call: ``
    :param on_post_call: If True, allows subscribers to register callbacks to the
        methods's `EventType.ON_POST_CALL` events. Defaults to None.


    `EventType.ON_PRE_CALL` events occur right before the method is called, while
    `EventType.ON_POST_CALL` events immediately follow the method call.

    If *on_pre_call* and *on_post_call* are both omitted, *on_post_call* will
    default to True and *on_pre_call* will default to False. Otherwise, omitted
    arguments default to False.

    When used as a decorator, "calling" it e.g. `@subscribable_method()` is
    optional. However, it must be called when it is desired to include keyword
    arguments (refer to the above behavior when not calling it e.g. omitting all
    keyword arguments).

    The target method's name considered the member's "field" name.

    Note that zero-argument `super()` calls within the target method will not
    function correctly. It's arguments must be explicitly passed.
    """
    return _SubscribableMethod(*args, **kwargs)




EventCallback  = Callable[['Subscribable', str, EventFlag | int], Any]
EventCallbackT = TypeVar('EventCallbackT', bound=EventCallback)

class _Subscribable(Protocol):
    __slots__ = ()

    # Using a separate cache prevents the framework state from
    # getting mangled with the user/inst state, and allows for
    # easier integration of instances without managed dictionaries.
    __cache__: MutableMapping[str, Any]

class Subscribable(_Subscribable):
    """A mixin class allowing subclasses to implement members that notify
    subscribers of various events via callbacks. Such members are defined
    using the `subscribable_field` and `subscribable_method` functions.

    Instances of subclasses must have a readable `__cache__` attribute that
    is resolvable to a mutable mapping. It is used internally to store various
    framework states in addition to the states of subscribable fields.

    >>> class Object(Subscribable):
    ...     x = subscribable_field()
    ...
    ...     @subscribable_field
    ...     def y(self) -> int:
    ...         return self._y
    ...     @y.setter
    ...     def y(self, value):
    ...         self._y = value
    ...
    ...     @subscribable_method
    ...     def z(self):
    ...         return 3.14
    ...
    ...     def __init__(self):
    ...         self.__cache__ = {}
    >>>
    >>>
    >>> values = []
    >>>
    >>> def callback(subscribable, field, event):
    ...     value = getattr(subscribable, field)
    ...     if callable(value):
    ...         value = value.__name__
    ...     values.append((EventFlag(event), field, value))
    >>>
    >>> o = Object()
    >>> o.subscribe("x", EventFlag.ON_SET, callback)
    >>> o.subscribe("y", EventFlag.ON_SET, callback)
    >>> o.subscribe("z", EventFlag.ON_CALL, callback)
    >>> o.x = 8
    >>> o.y = 6
    >>> o.z()
    >>> values
    [(<EventFlag.ON_SET: 4>, 'x', 8), (<EventFlag.ON_SET: 4>, 'y', 6), (<EventFlag.ON_CALL: 16>, 'z', 'z')]

    >>> class Object(Subscribable):
    ...     x = subscribable_field()
    ...
    ...     @subscribable_field
    ...     def y(self):
    ...         return self._y
    ...     @y.setter
    ...     def y(self, value):
    ...         self._y = value
    ...
    ...     @subscribable_method
    ...     def z(self):
    ...         return 3.14
    ...
    ...     def __init__(self):
    ...         self.__cache__ = {}
    >>>
    >>> values = []
    >>>
    >>> def callback(subscribable, field, event):
    ...     values.append((EventFlag(event), field, getattr(subscribable, field)))
    >>>
    >>> o = Object()
    >>> o.subscribe("x", EventFlag.ON_SET, callback)
    >>> o.subscribe("y", EventFlag.ON_SET, callback)
    >>> o.x = 8
    >>> o.y = 6
    >>>
    >>> values

    """
    __slots__ = ()

    __event_fields__: ClassVar[Mapping[str, EventFlag]]  # set internally

    @property
    def __mutex__(self) -> threading.Lock:
        try:
            return self.__cache__['__mutex__']
        except KeyError:
            pass

        mutex = self.__cache__['__mutex__'] = threading.Lock()
        return mutex

    @property
    def __events__(self) -> Mapping[tuple[str, EventFlag], list[EventCallback]]:
        try:
            return self.__cache__['__events__']
        except KeyError:
            pass

        with self.__mutex__:
            cache = self.__cache__['__events__'] = {}
            for field, flags in self.__event_fields__.items():
                for flag in EventFlag:
                    if flags & flag:
                        cache[field, flag] = []

        return cache

    __EVENT_FLAGS = tuple(int(f) for f in EventFlag)

    def _unsupported_subscription_err(self, field: str, flag: int):
        return ValueError(
            f'{field!r} member of {type(self).__name__!r} object does '
            f'not support {EventFlag(flag)} subscriptions'
        )

    def _iter_queue_keys(self, field: str, event_flags: EventFlag | int, *, __flags=__EVENT_FLAGS):
        yield from ((field, flag) for flag in __flags if event_flags & flag)


    @property
    def is_muted(self):
        """[Get] the notification state of the instance. While muted, it will not
        notify its' subscribers when events of interest occur.

        Subscribables are not muted by default e.g. `self.is_muted == False`. The
        instance's notification state is updated via the `.mute`, `.unmute`, and
        `.suppressed` methods.
        """
        try:
            return self.__cache__['_is_muted']
        except KeyError:
            self.__cache__['_is_muted'] = False
        return False

    def mute(self):
        """Mute the instance. While muted, it will not notify its' subscribers
        when events of interest occur.

        Does nothing if the instance is already muted.
        """
        self.__cache__['_is_muted'] = True

    def unmute(self):
        """Unmute the instance.

        Does nothing if the instance is not muted.
        """
        self.__cache__['_is_muted'] = False

    @contextlib.contextmanager
    def suppressed(self):
        """Context manager that mutes the instance for the duration of the
        statement's execution, then restores its' prior notification state
        (the instance is NOT explicitly unmuted).
        """
        cache    = self.__cache__
        is_muted = cache['_is_muted']
        try:
            cache['_is_muted'] = True
            yield self
        finally:
            cache['_is_muted'] = is_muted


    def _notify(self, field: str, event_flags, *, __flags=__EVENT_FLAGS):
        events = self.__events__
        for flag in __flags:
            if event_flags & flag:
                try:
                    queue = events[field, flag]
                except KeyError:
                    raise self._unsupported_subscription_err(field, flag) from None

                for callback in queue:
                    callback(self, field, event_flags)

    def notify(self, field: str, event_flags: EventFlag | int):
        """Invoke a member's subscription callbacks for the given event type(s).

        Does nothing when the instance is muted.

        :type field: ``
        :param field: The name of a member that supports subscriptions.

        :type event_flags: ``
        :param event_flags: Supported event type(s) as a bitmask of event flags.


        This method is used internally to run subscription callbacks (mentioned
        for transparency).

        Note that subscription callbacks may also trigger notifications, resulting
        in infinate recursion. To avoid this, use the `.notify_once` method instead.
        """
        if not self.is_muted:
            self._notify(field, event_flags)

    def notify_once(self, field: str, event_flags: EventFlag | int):
        """Invoke a member's subscription callbacks for the given event type(s)
        and suppress all notifications triggered during the process.

        Does nothing when the instance is muted.

        :type field: `str`
        :param field: The name of a member that supports subscriptions.

        :type event_flags: `EventFlag | int`
        :param event_flags: Supported event type(s) as a bitmask of event flags.


        This method is not used internally.

        """
        if not self.is_muted:
            with self.suppressed():
                self._notify(field, event_flags)


    def subscribe(self, field: str, event_flags: EventFlag | int, callback: EventCallbackT) -> EventCallbackT:
        """Register a callback to run when a subscribable member is updated or
        called.

        The `.notify` and `.notify_once` methods are responsible for executing
        registered callbacks.

        :type field: `str`
        :param field: The name of a member that supports subscriptions.

        :type event_flags: `EventFlag | int`
        :param event_flags: Supported event type(s) as a bitmask of event flags.

        :type callback: `EventCallback`
        :param callback: A callable that accepts 3 positional arguments; the
            subscribable object, the member name, and the flag representing the
            type of event that triggered the callback.

        :return `EventCallback`:


        Event types supported by a member depends on the flags that were set
        when it was defined.

        A callback that calls or updates the instances subscribable fields can
        trigger additional event notifications, resulting in a `RecursionError`.
        This can be prevented by muting the instance while working with it.
        """
        mutex  = self.__mutex__
        events = self.__events__

        for key in self._iter_queue_keys(field, event_flags):
            try:
                queue = events[key]
            except KeyError:
                raise self._unsupported_subscription_err(field, key[1]) from None

            with mutex:
                if callback not in queue:
                    events[key].append(callback)

        return callback

    def unsubscribe(self, field: str, event_flags: EventFlag | int, callback: EventCallback):
        """Deregister a callback for the given member and event type(s).

        Does nothing if the callback is not registered for any of the field's
        subscribable events.

        :type field: `str`
        :param field: The name of a member that supports subscriptions.

        :type event_flags: `EventFlag | int`
        :param event_flags: Supported event type(s) as a bitmask of event flags.

        :type callback: `EventCallback`
        :param callback: The callback that was registered
        """
        mutex  = self.__mutex__
        events = self.__events__

        for key in self._iter_queue_keys(field, event_flags):
            try:
                queue = events[key]
            except KeyError:
                raise self._unsupported_subscription_err(field, key[1]) from None

            with mutex:
                try:
                    queue.remove(callback)
                except ValueError:
                    pass

    def unsubscribe_all(self, field: str | None = None, event_flags: EventFlag | int = 0):
        """Deregister multiple callbacks from one or all fields.

        :type field: `str | None`
        :param field: The name of a member that supports subscriptions. If None,
            callbacks from all subscribable fields will be deregistered. Defaults
            to None.

        :type event_flags: `EventFlag | int`
        :param event_flags: Supported event type(s) as a bitmask of event flags.
            If not 0, only callbacks registered for specific events are
            deregistered. Otherwise, all callbacks are deregistered regardless of
            the event type. Defaults to 0.
        """
        mutex  = self.__mutex__
        events = self.__events__

        if field is None and not event_flags:
            for queue in events.values():
                with mutex:
                    queue.clear()
            return

        if field is None:
            fields = type(self).__event_fields__
        else:
            fields = (field,)

        for (field, flag), queue in events.items():
            if field not in fields:
                continue
            if not event_flags or event_flags & flag:
                with mutex:
                    queue.clear()
