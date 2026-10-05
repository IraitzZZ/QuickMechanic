"""Widgets de Qt que traducen el texto que reciben.

La app escribe sus etiquetas en español dentro del codigo. En vez de envolver a
mano cada cadena con :func:`quickmechanic.i18n.tr`, los modulos de interfaz
importan estos widgets (mismos nombres, mismos metodos) y aqui se traduce el
texto antes de entregarlo a Qt: constructores con texto, ``setText``,
``setToolTip``, ``addTab``, los avisos de ``QMessageBox``, etc.

Ventajas: el codigo sigue siendo naturalmente legible en español, cualquier
cadena nueva funciona igual (si falta la traduccion se ve el español) y no hay
riesgo de que un widget se quede sin traducir por un despiste.

Uso::

    from PyQt6.QtWidgets import QVBoxLayout      # lo que no lleva texto
    from .qt_i18n import QLabel, QPushButton     # lo que sí lo lleva
"""
from __future__ import annotations

from PyQt6 import QtGui, QtWidgets

from .i18n import translate

__all__ = [
    "QAction",
    "QCheckBox",
    "QComboBox",
    "QDialog",
    "QDoubleSpinBox",
    "QFileDialog",
    "QFrame",
    "QGroupBox",
    "QInputDialog",
    "QLabel",
    "QLineEdit",
    "QListWidget",
    "QMainWindow",
    "QMenu",
    "QMessageBox",
    "QPushButton",
    "QRadioButton",
    "QScrollArea",
    "QSlider",
    "QSpinBox",
    "QTabWidget",
    "QToolButton",
    "QWidget",
    "text_kwargs",
]

_TEXT_KWARGS = ("text", "title", "label", "caption", "message")
_TEXT_METHODS = (
    "setText",
    "setToolTip",
    "setStatusTip",
    "setWhatsThis",
    "setWindowTitle",
    "setPlaceholderText",
    "setInformativeText",
    "addTab",
    "setTabText",
    "setTabToolTip",
    "addAction",
    "addMenu",
    "setTitle",
    "addButton",
)
#: Metodos que no deben traducirse aunque existan en el widget (llevan datos).
_DATA_METHODS = ("addItem", "addItems", "setCurrentText", "setEchoMode", "insertItems")


def text_kwargs(kwargs: dict) -> dict:
    """Traduce los argumentos con nombre que llevan texto visible."""
    if not kwargs:
        return kwargs
    return {
        key: (translate(value) if key in _TEXT_KWARGS and isinstance(value, str) else value)
        for key, value in kwargs.items()
    }


def _translate_args(args: tuple, *, skip: int = 0) -> tuple:
    if not args:
        return args
    return tuple(
        translate(value) if (isinstance(value, str) and index >= skip) else value
        for index, value in enumerate(args)
    )


def _method(original):
    def wrapper(self, *args, **kwargs):
        return original(self, *_translate_args(args), **text_kwargs(kwargs))

    wrapper.__name__ = getattr(original, "__name__", "wrapper")
    wrapper.__qualname__ = wrapper.__name__
    return wrapper


def _constructor(base, *, first_arg_is_text: bool):
    original = base.__init__

    def __init__(self, *args, **kwargs):  # noqa: N807 (API de Qt)
        if first_arg_is_text and args and isinstance(args[0], str):
            args = (translate(args[0]), *args[1:])
        original(self, *args, **text_kwargs(kwargs))

    return __init__


def _build(name: str, base, *, text_first: bool = False, skip: tuple[str, ...] = ()):
    namespace = {"__module__": __name__, "__doc__": f"Copia traducible de {base.__name__}."}
    if text_first:
        namespace["__init__"] = _constructor(base, first_arg_is_text=True)
    for method in _TEXT_METHODS:
        if method in skip or method in _DATA_METHODS:
            continue
        original = getattr(base, method, None)
        if callable(original):
            namespace[method] = _method(original)
    return type(name, (base,), namespace)


# ---------------------------------------------------------------- widgets
QLabel = _build("QLabel", QtWidgets.QLabel, text_first=True)
QPushButton = _build("QPushButton", QtWidgets.QPushButton, text_first=True)
QCheckBox = _build("QCheckBox", QtWidgets.QCheckBox, text_first=True)
QRadioButton = _build("QRadioButton", QtWidgets.QRadioButton, text_first=True)
QToolButton = _build("QToolButton", QtWidgets.QToolButton, text_first=True)
QGroupBox = _build("QGroupBox", QtWidgets.QGroupBox, text_first=True)
QAction = _build("QAction", QtGui.QAction, text_first=True)
QComboBox = _build("QComboBox", QtWidgets.QComboBox)
QDialog = _build("QDialog", QtWidgets.QDialog)
QDoubleSpinBox = _build("QDoubleSpinBox", QtWidgets.QDoubleSpinBox)
QFrame = _build("QFrame", QtWidgets.QFrame)
QLineEdit = _build("QLineEdit", QtWidgets.QLineEdit, skip=("setText",))
QListWidget = _build("QListWidget", QtWidgets.QListWidget, skip=("setText",))
QMainWindow = _build("QMainWindow", QtWidgets.QMainWindow)
QMenu = _build("QMenu", QtWidgets.QMenu, text_first=True)
QScrollArea = _build("QScrollArea", QtWidgets.QScrollArea)
QSlider = _build("QSlider", QtWidgets.QSlider)
QSpinBox = _build("QSpinBox", QtWidgets.QSpinBox)
QTabWidget = _build("QTabWidget", QtWidgets.QTabWidget)
QWidget = _build("QWidget", QtWidgets.QWidget)


# ------------------------------------------------------------ avisos y dialogos
def _static_wrapper(original):
    def wrapper(*args, **kwargs):
        return original(*_translate_args(args), **text_kwargs(kwargs))

    wrapper.__name__ = getattr(original, "__name__", "wrapper")
    wrapper.__qualname__ = wrapper.__name__
    return wrapper


class QMessageBox(QtWidgets.QMessageBox):
    """``QMessageBox`` que traduce titulos, textos y botones."""

    information = staticmethod(_static_wrapper(QtWidgets.QMessageBox.information))
    warning = staticmethod(_static_wrapper(QtWidgets.QMessageBox.warning))
    critical = staticmethod(_static_wrapper(QtWidgets.QMessageBox.critical))
    question = staticmethod(_static_wrapper(QtWidgets.QMessageBox.question))
    about = staticmethod(_static_wrapper(QtWidgets.QMessageBox.about))


class QInputDialog(QtWidgets.QInputDialog):
    """``QInputDialog`` que traduce el titulo y la pregunta."""

    getText = staticmethod(_static_wrapper(QtWidgets.QInputDialog.getText))
    getItem = staticmethod(_static_wrapper(QtWidgets.QInputDialog.getItem))
    getInt = staticmethod(_static_wrapper(QtWidgets.QInputDialog.getInt))


class QFileDialog(QtWidgets.QFileDialog):
    """``QFileDialog`` que traduce titulos y filtros (nunca la ruta elegida)."""

    getOpenFileName = staticmethod(_static_wrapper(QtWidgets.QFileDialog.getOpenFileName))
    getSaveFileName = staticmethod(_static_wrapper(QtWidgets.QFileDialog.getSaveFileName))
    getExistingDirectory = staticmethod(_static_wrapper(QtWidgets.QFileDialog.getExistingDirectory))
    getOpenFileNames = staticmethod(_static_wrapper(QtWidgets.QFileDialog.getOpenFileNames))
