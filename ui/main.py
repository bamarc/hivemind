"""Hivemind Kirigami UI — Entry point.

Initialises the QGuiApplication, sets up the BackendEngine with proper
QML import paths for both PySide6 and system-installed Kirigami, and
loads the main QML window.
"""

from __future__ import annotations

import logging
import os
import sys

# Ensure the parent Hivemind project is on sys.path so core.* modules
# can be imported.  This works whether or not hivemind is installed as
# an editable package in the UI venv.
_UI_ROOT = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_UI_ROOT)
if _PARENT not in sys.path:
    sys.path.insert(0, _PARENT)

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from backend.engine import BackendEngine

logger = logging.getLogger(__name__)

# System QML paths where Kirigami modules may live (distribution-dependent)
_KIRIGAMI_PATHS = [
    "/usr/lib/x86_64-linux-gnu/qt6/qml",   # Debian/Ubuntu
    "/usr/lib64/qt6/qml",                   # openSUSE
    "/usr/lib/qt6/qml",                     # Fedora
    "/usr/local/lib/qt6/qml",               # macOS (Homebrew)
]


def _find_kirigami_path() -> str | None:
    """Return the first existing system QML path that contains Kirigami."""
    for p in _KIRIGAMI_PATHS:
        candidate = os.path.join(p, "org", "kde", "kirigami")
        if os.path.isdir(candidate):
            return p
    return None


def _setup_import_paths(engine: QQmlApplicationEngine) -> None:
    """Configure QML import paths so that Kirigami and our components resolve.

    Qt searches import paths in order and picks the first compatible module.
    PySide6's bundled QtQuick.Controls (v6.11) must take priority over the
    system version (typically v6.8), or Fusion/Material/Universal styles won't
    be found. We therefore put PySide6's qml directory first, the system
    Kirigami path second, then everything else.
    """
    paths = engine.importPathList()
    pyside_paths = [p for p in paths if "PySide6" in p]
    other_paths = [p for p in paths if "PySide6" not in p]

    # Discover the qml source tree for local QML files
    ui_root = os.path.dirname(os.path.abspath(__file__))
    qml_dirs = [
        os.path.join(ui_root, "qml"),
        os.path.join(ui_root, "qml", "pages"),
        os.path.join(ui_root, "qml", "components"),
        os.path.join(ui_root, "qml", "dialogs"),
    ]

    kirigami_system_path = _find_kirigami_path()

    combined = list(pyside_paths)
    if kirigami_system_path:
        combined.append(kirigami_system_path)
    combined.extend(qml_dirs)
    combined.extend(other_paths)
    engine.setImportPathList(combined)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Hivemind")
    app.setOrganizationName("Hivemind")

    engine = QQmlApplicationEngine()
    _setup_import_paths(engine)

    backend = BackendEngine()
    engine.rootContext().setContextProperty("backend", backend)

    qml_path = QUrl.fromLocalFile(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "qml", "main.qml")
    )
    engine.load(qml_path)

    if not engine.rootObjects():
        logger.error("Failed to load QML: %s", qml_path)
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
