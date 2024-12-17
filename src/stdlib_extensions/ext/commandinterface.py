import sys
import copy
import time
import types
import logging
import functools
import dataclasses
import collections
from ..typing import (
    overload,
    T,
    T_co,
    T_contra,
    Any,
    Self,
    Generic,
    TypeVar,
    TypeAliasType,
    Callable,
    Iterable,
    Protocol,
    Literal,
)


_T = TypeVar('_T', infer_variance=True)

class _SupportsReadT(Protocol[_T]):
    def read(self) -> _T: ...

class _SupportsWriteT(Protocol[_T]):
    def write(self, s: _T, /) -> Any: ...




class Runner:
    def __init__(
        self,
        queue: Iterable[Callable[[Self], Any]] | None = None,
        *,
        maxlen: int | None = None,
        histlen: int | None = 32,
        timer: Callable[[], float] = time.perf_counter,
    ):
        self._running = False
        self._savestate = None

        self.timer = timer
        self.clock = 0.0
        self.queue = collections.deque(queue or (), maxlen=maxlen)
        self.qhist = collections.deque(maxlen=histlen)

    def __len__(self):
        return len(self.queue)

    def __iter__(self):
        return iter(self.queue)

    def __call__(self, runner: Any = None, /) -> Any:
        try:
            return self.pop()(self)
        except IndexError:
            pass

    def push(self, c: Callable[[Self], Any]) -> Callable[[Self], Any]:
        self.queue.append(c)
        return c

    def pop(self):
        res = self.queue.popleft()
        try:
            if res != self.qhist[0]:
                self.qhist.appendleft(res)
        except IndexError:
            self.qhist.appendleft(res)
        return res

    # [ state management ]

    def __setstate__(self, state: dict[str, Any]) -> None:
        self.__dict__.update(state)

    def savestate(self) -> tuple[float, Iterable[Callable[[Self], Any]]]:
        """Return the runner's timeclock and reduced queue."""
        return self.clock, tuple(copy.deepcopy(obj) for obj in self.queue)

    def loadstate(self, state: tuple[float, Iterable[Callable[[Self], Any]]] | None = None):
        """Update the runner's timeclock and queue states.

        Args:
            * state (optional): A 2-tuple containing the runner
            clock value and queue of `Task`s.

        If *state* is None, the runner's state will be restored
        to as it was the first time its' `.start` method was
        called (no-op if it has yet to be called).
        """
        if state is None:
            if self._savestate is None:
                return
            state = self._savestate

        clock, queue = state
        queue = collections.deque(queue, maxlen=self.queue.maxlen)
        self.__setstate__({'clock': clock, 'queue': queue})

    # [ runtime ]

    @property
    def running(self):
        return self._running

    def start(self):
        if self._running:
            raise RuntimeError('runner is already running')

        if self._savestate is None:
            self._savestate = self.savestate()

        self._running = True
        while self._running:
            self.clock = self.timer()
            self()

    def stop(self):
        self._running = False

    # [ stdout ]

    @staticmethod
    def _get_stream_logger():
        try:
            return Runner._logger  # type: ignore
        except AttributeError:
            pass

        logger = logging.getLogger(Runner.__name__)
        logger.setLevel(logging.INFO)

        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(logging.Formatter("%(message)s\n"))
        logger.addHandler(sh)

        sh = logging.StreamHandler()
        sh.setLevel(logging.DEBUG)
        sh.setFormatter(logging.Formatter(
            "[ %(levelname)s | %(name)s | %(lineno)d ] %(message)s"
        ))
        sh.addFilter(types.SimpleNamespace(  # type: ignore
            filter=lambda record: record.levelno == logging.DEBUG
        ))
        logger.addHandler(sh)

        Runner._logger = logger  # type: ignore

        return logger

    @property
    def logger(self) -> logging.Logger:
        return self._get_stream_logger()

    def write(self, s: str, level: int | str = logging.INFO, /, **kwargs) -> None:
        if isinstance(level, str):
            try:
                level = getattr(logging, level.upper())
            except AttributeError:
                raise ValueError(
                    f"{level!r} is not a valid logging level"
                ) from None

        self.logger.log(level, s, **kwargs)  # type: ignore


_RunnerT = TypeVar('_RunnerT', bound=Runner)
_Callback = TypeAliasType('_Callback', Callable[[_RunnerT], Any], type_params=(_RunnerT,))


@dataclasses.dataclass(slots=True)
class Action(Generic[_RunnerT]):
    title   : str
    callback: Callable[[_RunnerT], Any]

    def __call__(self, runner: _RunnerT):
        return self.callback(runner)

    def __eq__(self, other: Self | Any):
        try:
            return (self.title, self.callback) == (other.title, other.callback)
        except:
            return False

    def __le__(self, other: Self):
        return self.title <= other.title

    def __lt__(self, other: Self):
        return self.title < other.title

    def __gt__(self, other: Self):
        return self.title > other.title

    def __ge__(self, other: Self):
        return self.title >= other.title


class View(Action):
    _ac_options: tuple[Action | None] | tuple[Action, ...]

    def __init__(
        self,
        title: str,
        prelude: str = '',
        *,
        options: Iterable[Action] = (),
    ):
        self._ac_options = (None,)

        self.title   = title
        self.prelude = prelude
        self.set_options(options)

    def __getstate__(self):
        state = super().__getstate__()  # type: ignore
        state[1].pop('callback')  # type: ignore
        return state

    @property
    def callback(self):  # type: ignore
        return self.__call__

    def _hasoptions(self):
        options = self._ac_options
        try:
            return (len(options) > 1) or options[0] is not None  # type: ignore
        except IndexError:
            return False

    def itercommands(self):
        """Yield all command-to-action pairs that are
        available to users.
        """
        ac_default, *ac_options = self._ac_options
        for i, ac in enumerate(ac_options):
            yield i+1, ac
        if ac_default is not None:
            yield 0, ac_default

    def _itertree(
        self,
        memo = None,
        prefix: str = '',
        *,
        # prefixes
        SPACE = '    ',
        BRANCH = '│   ',
        # "pointers"
        TEE = '├── ',
        LAST = '└── '
    ):
        if memo is None:
            memo = set()
            yield self.title

        memo.add(id(self))

        views = tuple(
            ac for _, ac in self.itercommands()
            if isinstance(ac, View)
        )
        ptrs = [TEE] * (len(views) - 1) + [LAST]
        for ptr, view in zip(ptrs, views):
            yield prefix + ptr + view.title

            vid = id(view)

            if view._hasoptions():
                ext = BRANCH if ptr == TEE else SPACE
                if vid in memo:
                    yield prefix+ext+LAST+'(...)'
                else:
                    memo.add(vid)
                    yield from view._itertree(memo, prefix+ext)
            else:
                memo.add(vid)

    def tree(self):
        """Return the hierarchy structure this view and
        its' children as a GNU directory tree string."""
        return '\n'.join(self._itertree())

    def show(self, stream: _SupportsWriteT[str] = sys.stdout, /):
        """Display the menu.

        Available user options and their command inputs are
        listed starting from the oldest option registered,
        except the option set as command input "0" which is
        always listed last.
        """
        output = '\n' + '\n'.join((
            self.prelude or self.title,
            *(f'[{i}] {ac.title}' for i, ac in self.itercommands())
        ))
        stream.write(output)

    prompt = '>>> '

    def read(self, prompt: object | None = None) -> Action[Any]:
        """Block the calling thread and await user input.
        Returns the action paired with the associated
        command input or raises `ValueError`.
        """
        if prompt is None:
            prompt = self.prompt

        options  = self._ac_options
        commands = tuple(str(i) for i in range(len(options)))

        cmd = input(prompt).strip()
        if cmd in commands:
            action = options[int(cmd)]
            if action is not None:
                return action
        raise ValueError(cmd)

    # [ overloads ]

    def __repr__(self):
        return (
            f'{type(self).__name__}'
            f'({self.title=}, {self.prelude=})'
        ).replace('self.', '')

    def __eq__(self, other: Self | Any):
        try:
            return (
                self.title,
                self._ac_options
            ) == (
                other.title,
                other._ac_options
            )
        except:
            pass
        return False

    def __call__(self, runner: Runner) -> None:
        runner.write(f'Active view is {self.title!r}.', logging.DEBUG)

        if not self._hasoptions():
            return

        self.show(runner)
        try:
            action = self.read()
        except ValueError as e:
            runner.write(f'Invalid command {e.args[0]!r}!', logging.ERROR)
            action = self

        if isinstance(action, View):
            runner.write(f'Passing control to view {action.title!r}...', logging.DEBUG)
            runner.push(action)
            return

        # Give the action an opportunity to push the next
        # view. Otherwise, we maintain this one.
        qlen = len(runner.queue)

        runner.write(f'Running action {action.title!r}...', logging.DEBUG)
        action(runner)

        if len(runner.queue) == qlen:
            runner.push(self)

    # [ option management ]

    def __len__(self):
        if self._ac_options[0] is None:
            return len(self._ac_options) - 1
        return len(self._ac_options)

    def __iter__(self):
        if self._ac_options[0] is None:
            return iter(self._ac_options[1:])
        return iter(self._ac_options)

    @overload
    def __getitem__(self, index: int, /) -> Action[Any]: ...
    @overload
    def __getitem__(self, index: Literal[0], /) -> Action[Any] | None: ...  # pyright: ignore[reportOverlappingOverload]
    def __getitem__(self, index, /):
        try:
            return self._ac_options[index]
        except IndexError:
            raise ValueError(f'invalid command value {index!r}')

    @overload
    def __setitem__(self, index: int, value: Action, /) -> None: ...
    @overload
    def __setitem__(self, index: Literal[0], value: Action | None, /) -> None: ...
    def __setitem__(self, index, value, /):
        options = list(self._ac_options)
        options[index] = value
        self._ac_options = tuple(options)  # type: ignore

    @overload
    def add_option(self, option: Action | Iterable[Action], /, default: bool = ...) -> None: ...
    @overload
    def add_option(self, option: Action | None | Iterable[Action | None], /, default: Literal[True]) -> None: ...
    def add_option(self, options, /, default = False):
        """Register one or more actions as user options.

        Command input numbers are automatically assigned based
        on when the option is registered and cannot be set
        otherwise, except the action ran on command input zero
        ("0").

        When *default* is set, *option* (or the first action,
        if iterable) will be set to run on command input "0"
        (note: this can be `None`). Remaining options are
        registered normally.
        """
        if isinstance(options, Action):
            options = (options,)

        if default:
            self._ac_options = (options[0], *self._ac_options[1:], *options[1:])  # type: ignore
        else:
            self._ac_options = (*self._ac_options, *options)  # type: ignore

    def del_option(self, option: Action):
        options = self._ac_options
        for i, opt in enumerate(options):
            if opt == option:
                if i == 0:
                    self._ac_options = (None, *options[1:])  # type: ignore
                else:
                    self._ac_options = options[:i] + options[i+1:]  # type: ignore
                break

    @overload
    def set_options(self, option: Iterable[Action], /, default: bool = ...) -> None: ...
    @overload
    def set_options(self, option: Iterable[Action | None], /, default: Literal[True]) -> None: ...
    def set_options(self, options, /, default = False):
        """Clear all registered options and set new ones.

        When *default* is set, the first action in *options*
        is assigned to command input "0" (note: this can be
        `None`). Otherwise, the current action set to command
        input "0" is not changed.
        """
        if not default:
            options = (self._ac_options[0], *options)
        else:
            options = tuple(options)
        self._ac_options = options

    def insert_option(self, index: int, option: Action):
        if index < 0:
            raise ValueError("'index' must be positive")

        options = self._ac_options
        if index == 0:
            default, *options = options
            if default is not None:
                self._ac_options = (option, *options, default)
            else:
                self._ac_options = (option, *options)
            return
        self._ac_options = (*options[:index], option, *options[index:])  # type: ignore


def action(title: str) -> Callable[[Callable[[_RunnerT], Any]], Action[_RunnerT]]:
    def capture_callback(callback):
        return Action(title=title, callback=callback)
    return capture_callback


# [ actions ]

@action('(home)')
def ac_navhome(runner: Runner):
    runner.loadstate()


@action('(prev)')
def ac_navprev(runner: Runner):
    views = 0
    seen  = set()
    for obj in runner.qhist:
        obj_id = id(obj)
        if obj_id in seen:
            continue
        seen.add(obj_id)

        if isinstance(obj, View):
            views += 1
        if views >= 2:
            return runner.push(obj)
    # not enough history - return to main menu
    ac_navhome(runner)


@action('(quit)')
def ac_quit(runner: Runner):
    runner.stop()




if __name__ == "__main__":
    import functools


    def echo(s: str, runner: Runner):
        runner.write(s)

    @action('List Nav History')
    def ac_list_history(runner: Runner):
        runner.write('\n'.join(str(q) for q in runner.qhist))


    vsub1 = View('Sub Menu', 'This is sub menu 1. Enter a command.')
    vsub1.add_option((
        ac_quit,
        ac_list_history,
        ac_navhome,
        ac_navprev,
    ), default=True)

    vsub1_1 = View('Nested Menu')
    vsub1_1.add_option((
        ac_quit,
        vsub1,
        ac_navhome,
        ac_navprev,
    ), default=True)
    vsub1.insert_option(1, vsub1_1)

    vmain = View('Main Menu')
    vmain.add_option(
        Action(f"echo {s!r}", functools.partial(echo, s))
        for s in ("Hello World", "The cake is a lie", "Happy Tree Friends")
    )
    vmain.add_option(vsub1)
    vmain.add_option(vsub1_1)
    vmain.add_option(ac_quit, default=True)


    runner = Runner()
    runner.push(vmain)
    runner.logger.setLevel('DEBUG')
    print(vmain.tree())
    runner.start()
