# -*- coding: utf-8 -*-
"""Background worker for long-running interpolation tasks.

The worker runs only the pure compute (numpy/scipy/sklearn) off the UI thread.
Plotting, table fills, pixmap and QGIS-layer work stay on the main thread in the
controller's completion slot — matplotlib's pyplot and Qt widgets are not
thread-safe.
"""

from qgis.PyQt.QtCore import QThread, pyqtSignal


class InterpolationWorker(QThread):
    """Async worker for kriging and SVM interpolation.

    finished carries the raw compute result (ndarray / tuple), so the slot it
    connects to must accept a Python object, not a dict.
    """

    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    # Tasks that report per-iteration progress (leave-one-out loops).
    _PROGRESS_TASKS = ('kriging_cv', 'svm_cv')

    def __init__(self, interpolation_manager, task_type, **kwargs):
        super().__init__()
        self.interpolation_manager = interpolation_manager
        self.task_type = task_type
        self.kwargs = kwargs
        self._is_running = True

    def run(self):
        """Execute the interpolation task off the UI thread."""
        try:
            kwargs = dict(self.kwargs)
            if self.task_type in self._PROGRESS_TASKS:
                kwargs.setdefault('progress_cb', self._emit_progress)

            if self.task_type == 'kriging':
                result = self.interpolation_manager.execute_kriging(**kwargs)
            elif self.task_type == 'kriging_cv':
                result = self.interpolation_manager.execute_cross_validation_kriging(**kwargs)
            elif self.task_type == 'svm':
                result = self.interpolation_manager.execute_svm(**kwargs)
            elif self.task_type == 'svm_cv':
                result = self.interpolation_manager.execute_cross_validation_svm(**kwargs)
            else:
                raise ValueError(f'Unknown task type: {self.task_type}')

            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def _emit_progress(self, value):
        """Forward per-iteration progress from the manager loop to the UI."""
        if self._is_running:
            self.progress.emit(int(value))

    def stop(self):
        """Cancel: stop emitting; downstream slots ignore late signals."""
        self._is_running = False
