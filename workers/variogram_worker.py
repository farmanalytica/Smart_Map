# -*- coding: utf-8 -*-
"""Background worker for variogram (re)computation.

Runs the pure semivariogram math (Exp_Semiv / Fit / Gamma) off the UI thread.
The controller applies the result to widgets and redraws the plot in its
finished slot — Qt widgets and matplotlib's pyplot are not thread-safe.

Used in a single-flight pattern: the controller keeps at most one worker
running and remembers only the latest pending request, so rapid slider drags
never pile up threads and the last requested state is the one that renders.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal


class VariogramWorker(QThread):
    """Run a pure compute callable(semiv, request) off the UI thread."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, compute_fn, semiv, request):
        super().__init__()
        self._compute_fn = compute_fn
        self._semiv = semiv
        self._request = request

    def run(self):
        try:
            result = self._compute_fn(self._semiv, self._request)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))
