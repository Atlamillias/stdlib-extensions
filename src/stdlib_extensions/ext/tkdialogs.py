"""Custom (modern) implementations of tkinter's common dialogs.

The implementation of dialogs defined in this module differ from
the original. By default, they all share the same parenting window.
However, a different parent can be set per-instance by setting their
`parent` attributes. Additionally, the result of calling the `.show`
method may be None if no selection was made or the dialog was closed
prior to making a selection. Dialogs that previously returned file-
paths now return `Path` objects. Lastly, the `wantobjects` attribute
of `Tk` object acting as a dialog's parent *must* be True - parsing
the Tcl strings directly is not supported.

Displayed dialogs are those native to the operating system, so the
behavior of each may vary between systems.

Dialogs will have one or more of the following options:

:type title: `str` (optional)
:param title: The name of the dialog.

:type parent: `Tk` (optional)
:param parent: The dialog's root widget. A global
    default parent is shared between all dialogs created from objects
    in this module.

:type initialfile: `str` (optional)
:param initialfile: The default value for the dialog's
    file name input field when showing the dialog. *initialfile* is
    updated whenever `.show()` returns a single, non-None result.

:type initialdir: `str` (optional)
:param initialdir: The directory opened when the
    `.show` method is called. *initialdir* is updated whenever `.show()`
    returns a non-None result.

:type initialcolor: `str` (optional)
:param initialcolor: A 7-character hexidecimal color
    code (e.g. "#ffffff" for white, etc.) indicating the default
    selection when showing the dialog. *initialcolor* is updated
    whenever `.show()` returns a single, non-None result.

:type filetypes: `tuple[tuple[str, str], ...]` (optional)
:param filetypes: A sequence
    of 2-tuples containing a descriptive name and file extension(s)
    of valid selections e.g. `[("Text Files", "*.txt"), ...]`.
    When including multiple extensions per file type, each extension
    should be delimited by a single space e.g. `[("Text Files", "*.txt
    *.text"), ...]` -- Alternatively, additional 2-tuples can be
    included with the same file type name specifying other extensions,
    as `[("Text Files", "*.txt"), ("Text Files", "*.text"), ...]`, etc.
    On Windows, wildcard symbols found in each extension value are
    used to filter valid selections from view - the extension value
    `*.*` will consider any file a valid selection.

:type defaultextension: `str` (optional)
:param defaultextension: Appended to the non-None result
    of `.show()` if a file extension is not explicitly given.

:type multiple: `bool` (optional)
:param multiple: If True, the user will be allowed to
    select multiple files within the same directory. When one or more
    selections are confirmed, `.show()` will return a tuple of `Path`
    objects for each.

:type mustexist: `bool` (optional)
:param mustexist: If True, any user selected path(s)
    must point to an existing file or directory.

"""
from tkinter import Tk
from pathlib import Path
import abc
import dataclasses
from .. import _shared
from ..typing import (
    Any, T,
    Callable, ClassVar,
    dataclass_transform, cast, overload
)

__all__ = [
    "Dialog",
    "Open",
    "SaveAs",
    "Directory",
    "ColorPicker",
]




_DIALOG_ROOT = Tk()
_DIALOG_ROOT.withdraw()
_DIALOG_ROOT.attributes('-topmost', True)




class _dialog:
    __slots__ = ('tk_command',)

    @property
    def parent(self: Any) -> Tk:
        return self.options.get('parent', _DIALOG_ROOT)
    @parent.setter
    def parent(self: Any, value):
        if not value:
            value = _DIALOG_ROOT
        self.options['parent'] = value

    @property
    def filetypes(self: Any):
        return self.options['filetypes']
    @filetypes.setter
    def filetypes(self: Any, value):
        if not value:
            value = ()
        else:
            try:
                value = tuple((desc, ext) for desc, ext in value)
            except ValueError:
                raise ValueError(
                    f"expected a sequence of 2-tuples for 'filetypes', got ({value!r})."
                ) from None
        self.options['filetypes'] = value

    @property
    def initialcolor(self: Any):
        return self.options.get('initialcolor', '')
    @initialcolor.setter
    def initialcolor(self: Any, value: str | None):
        if not value:
            self.options.pop('initialcolor', '')
        else:
            self.options['initialcolor'] = value

    def __init__(self, tk_command: str):
        self.tk_command = tk_command

    @dataclass_transform(kw_only_default=True)
    def __call__(self, cls: type[T]) -> type[T]:
        if '__slots__' not in cls.__dict__ or 'options' not in cls.__slots__:  # type: ignore
            ns = dict(cls.__dict__)
            ns.pop('__dict__', None)
            ns.pop('__weakref__', None)
            ns['__slots__'] = getattr(cls, '__slots__', ())
            cls = type(cls)(  # type: ignore
                cls.__name__,
                cls.__bases__,
                ns,
            )
            for member in cls.__dict__.values():
                _shared.ammend_closure(cls, member)

        if '__init__' in cls.__dict__:
            cls = dataclasses.dataclass(cls)  # no `__init__` generated
        else:
            cls = dataclasses.dataclass(cls)
            init = _shared.create_function(
                "__init__",
                ("self", "*args", "**kwargs"),
                (
                    "self.options = {'parent': _DIALOG_ROOT}",
                    "__tk_init__(self, *args, **kwargs)",
                ),
                None,
                globals=globals(),
                locals={
                    "__class__"   : cls,
                    "__tk_init__" : cls.__init__,
                    "_DIALOG_ROOT": _DIALOG_ROOT,
                }
            )
            cls.__init__ = init

        fset_body = "return self.options['{option}']"
        fset_body = "self.options['{option}'] = value"
        for field in cls.__dataclass_fields__.values():  #type: ignore
            f_name = field.name
            if isinstance(getattr(cls, f_name, None), property):
                continue

            prop = getattr(type(self), f_name, None)
            if prop:
                prop = property(
                    prop.fget,
                    prop.fset,
                    prop.fdel,
                    getattr(prop, 'doc', None),
                )
            if not prop:
                fget = _shared.create_function(
                    f"{f_name}_getter",
                    ("self",),
                    (fset_body.format(option=f_name),),
                    field.type,
                )
                fset = _shared.create_function(
                    f'{f_name}_setter',
                    ("self", "value",),
                    (fset_body.format(option=f_name),),
                    None,
                )
                prop = property(fget, fset)
            try:
                setattr(cls, f_name, prop)
            except AttributeError:
                # Read-only metaclass property (probably `parent`). Time to do
                # some sketchy shit, do-da ~
                tp      = type(cls)
                tp_desc = getattr(tp, f_name)
                delattr(tp, f_name)
                setattr(cls, f_name, prop)
                setattr(tp, f_name, tp_desc)

        setattr(cls, 'command', self.tk_command)
        return cls


# `dataclass_transform` decorators can only be functions. The
# signature is lost when the decorator is a class, so a helper
# is needed to get a proper signature.
@dataclass_transform(kw_only_default=True)
def dialog(tk_command: str) -> Callable[[type[T]], type[T]]:
    return _dialog(tk_command)




class DialogType(abc.ABCMeta):
    @property
    def parent(self):
        return _DIALOG_ROOT

    @property
    def iconbitmap(self):
        return _DIALOG_ROOT.wm_iconbitmap


class Dialog(metaclass=DialogType):
    # `cls.iconbitmap -> _DIALOG_ROOT.wm_iconbitmap`
    # `self.iconbitmap -> (...) -> self.parent.iconbitmap(...)`
    def iconbitmap(self, bitmap: Any | None = None, default: str | None = None) -> str:
        return self.parent.wm_iconbitmap(bitmap, default)  # type: ignore

    __slots__ = ('options',)

    command: ClassVar[str] = ''
    options: dict[str, Any]

    def __delattr__(self, name: str):
        if name in self.options:
            del self.options[name]
        else:
            super().__delattr__(name)

    def show(self, **options):
        options = self.options | options  # type: ignore
        parent  = cast(Tk, options.get('parent', _DIALOG_ROOT))

        result = parent.tk.call(
            self.command,
            *parent._options(options)  # type: ignore
        )
        return self.post_selection_hook(result)

    @abc.abstractmethod
    def post_selection_hook(self, result: Any) -> Any: ...




# [ DIALOGS ]

@dialog("tk_getSaveFile")
class SaveAs(Dialog):
    title           : str                         = 'Save As'
    initialfile     : str                         = ''
    initialdir      : str                         = ''
    filetypes       : tuple[tuple[str, str], ...] = ()
    defaultextension: str                         = ''
    parent          : Tk                          = _DIALOG_ROOT

    def post_selection_hook(self, result) -> Path | None:
        if not result:
            return None
        result = Path(result)
        self.options["initialdir"]  = str(result.parent)
        self.options["initialfile"] = str(result.name)
        return result


@dialog("tk_getOpenFile")
class Open(Dialog):
    title           : str                         = 'Select File'
    initialfile     : str                         = ''
    initialdir      : str                         = ''
    filetypes       : tuple[tuple[str, str], ...] = ()
    defaultextension: str                         = ''
    multiple        : bool                        = False
    parent          : Tk                          = _DIALOG_ROOT

    @overload
    def post_selection_hook(self, result: tuple[str, ...]) -> tuple[Path, ...]: ...
    @overload
    def post_selection_hook(self, result: str) -> Path | None: ...
    def post_selection_hook(self, result) -> Path | tuple[Path, ...] | None:
        if not result:
            return None
        if isinstance(result, tuple):  # multiple == True
            result = tuple(Path(fp) for fp in result)
            result = tuple([getattr(r, "string", r) for r in result])
            initialdir  = str(result[0].parent)
            initialfile = ''
        else:
            initialfile = result
            result      = Path(result)
            initialdir  = str(result.parent)
        self.options['initialdir']  = initialdir
        self.options['initialfile'] = initialfile
        return result


@dialog("tk_chooseDirectory")
class Directory(Dialog):
    title     : str  = 'Select Folder'
    initialdir: str  = ''
    mustexist : bool = False
    parent    : Tk   = _DIALOG_ROOT

    def post_selection_hook(self, result) -> Path | None:
        if not result:
            return None
        self.options['initialdir'] = result
        return Path(result)


@dialog("tk_chooseColor")
class ColorPicker(Dialog):
    title       : str = "Select Color"
    initialcolor: str = ''
    parent      : Tk  = _DIALOG_ROOT

    def post_selection_hook(self, result) -> str | None:
        if not result:
            return None
        self.options['initialcolor'] = result
        return result
