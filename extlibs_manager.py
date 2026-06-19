# -*- coding: utf-8 -*-
"""Provision third-party Python deps not shipped with QGIS, matching the
running interpreter — modeled on the farm_tools extlibs approach.

Smart-Map needs scikit-learn (+ its joblib / threadpoolctl deps). Those are NOT
shipped with QGIS and are ABI-locked to the Python version, so they live in a
local ``extlibs/`` folder that ``__init__.py`` puts on ``sys.path`` BEFORE the
plugin is imported. numpy / pandas / scipy / matplotlib DO come with QGIS and
must never be shadowed from extlibs/. skfuzzy, pysal and krig are vendored in
the plugin tree (relative imports) and need no provisioning.

Strategy, in order:
  1. Extract the bundled ``sklearn<pyminor>.zip`` (e.g. sklearn312.zip) into
     ``extlibs/`` — fast, offline, the common path.
  2. Fall back to running pip to install scikit-learn into ``extlibs/``.
  3. Otherwise report failure (a dialog shows manual instructions).

The active build is recorded in ``extlibs/.ready`` with its interpreter tag, so
a QGIS Python upgrade (different tag) re-provisions automatically.
"""

import importlib
import os
import subprocess
import sys
import sysconfig
import zipfile

_PLUGIN_DIR = os.path.dirname(__file__)
EXTLIBS_PATH = os.path.join(_PLUGIN_DIR, 'extlibs')
_SENTINEL = os.path.join(EXTLIBS_PATH, '.ready')

# Import names that MUST resolve from extlibs/ for the plugin to work.
_REQUIRED_PACKAGES = ('sklearn', 'joblib')
_PIP_NAME = 'scikit-learn'

# Suppress the transient console window the pip subprocess pops on Windows.
_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


def current_tag():
    """e.g. 'cp312-win_amd64' for the running interpreter."""
    plat = sysconfig.get_platform().replace('-', '_').replace('.', '_')
    return 'cp{}{}-{}'.format(sys.version_info.major, sys.version_info.minor, plat)


def ensure_on_path():
    """Put extlibs/ at the front of sys.path (idempotent)."""
    if os.path.isdir(EXTLIBS_PATH) and EXTLIBS_PATH not in sys.path:
        sys.path.insert(0, EXTLIBS_PATH)


def _read_ready():
    try:
        with open(_SENTINEL, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception:
        return None


def _importable(name):
    ensure_on_path()
    try:
        importlib.import_module(name)
        return True
    except Exception:
        return False


def _all_present():
    return all(_importable(n) for n in _REQUIRED_PACKAGES)


def needs_provision():
    """True if extlibs must be (re)built for the running interpreter."""
    if _read_ready() != current_tag():
        return True
    return not _all_present()


def _bundled_zip():
    """Path to the sklearn zip matching this Python minor, or None."""
    ver = '{}{}'.format(sys.version_info.major, sys.version_info.minor)
    candidate = os.path.join(_PLUGIN_DIR, 'sklearn{}.zip'.format(ver))
    return candidate if os.path.isfile(candidate) else None


def _extract_bundled():
    """Extract the bundled sklearn zip into extlibs/."""
    zip_path = _bundled_zip()
    if not zip_path:
        return False
    try:
        os.makedirs(EXTLIBS_PATH, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(EXTLIBS_PATH)
        importlib.invalidate_caches()
        return _all_present()
    except Exception as exc:  # pragma: no cover - defensive
        print('Smart-Map extlibs: bundled extract failed:', exc)
        return False


def _pip_executable():
    """Best-effort path to the QGIS Python interpreter for pip."""
    for cand in (
        os.path.join(sys.prefix, 'python3.exe'),
        os.path.join(sys.prefix, 'python.exe'),
        os.path.join(sys.prefix, 'bin', 'python3'),
        os.path.join(sys.prefix, 'bin', 'python'),
    ):
        if os.path.isfile(cand):
            return cand
    return sys.executable


def _pip_install():
    """Fall back to pip installing scikit-learn into extlibs/."""
    try:
        os.makedirs(EXTLIBS_PATH, exist_ok=True)
        subprocess.check_call(
            [_pip_executable(), '-m', 'pip', 'install', '--upgrade',
             '--target', EXTLIBS_PATH, _PIP_NAME],
            creationflags=_NO_WINDOW,
        )
        importlib.invalidate_caches()
        return _all_present()
    except Exception as exc:  # pragma: no cover - defensive
        print('Smart-Map extlibs: pip fallback failed:', exc)
        return False


def _write_sentinel():
    try:
        os.makedirs(EXTLIBS_PATH, exist_ok=True)
        with open(_SENTINEL, 'w', encoding='utf-8') as f:
            f.write(current_tag())
    except Exception:
        pass


def provision():
    """(Re)provision extlibs for the running interpreter. Returns True on success."""
    ensure_on_path()
    if not needs_provision():
        return True

    ok = _extract_bundled() or _pip_install()
    if ok:
        _write_sentinel()
    else:
        _warn_manual()
    return ok


def _warn_manual():
    """Tell the user how to install deps manually if provisioning failed."""
    try:
        from qgis.PyQt.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle('Smart-Map')
        msg.setText(
            'scikit-learn could not be provisioned automatically.\n\n'
            'Install it into the QGIS Python environment, e.g.:\n'
            '    python -m pip install scikit-learn\n\n'
            'See https://github.com/gustavowillam/SmartMapPlugin for details.'
        )
        msg.exec_()
    except Exception:
        print('Smart-Map: scikit-learn could not be provisioned. '
              'Install it with: python -m pip install scikit-learn')
