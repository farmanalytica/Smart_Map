# -*- coding: utf-8 -*-
"""Background worker for long-running interpolation tasks."""

from qgis.PyQt.QtCore import QThread, pyqtSignal


class InterpolationWorker(QThread):
    """Async worker for kriging and SVM interpolation."""

    # Signals
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, interpolation_manager, task_type, **kwargs):
        super().__init__()
        self.interpolation_manager = interpolation_manager
        self.task_type = task_type
        self.kwargs = kwargs
        self._is_running = True

    def run(self):
        """Execute interpolation task."""
        try:
            if self.task_type == "kriging":
                result = self.interpolation_manager.execute_kriging(**self.kwargs)
            elif self.task_type == "kriging_cv":
                result = self.interpolation_manager.execute_cross_validation_kriging(**self.kwargs)
            elif self.task_type == "svm":
                result = self.interpolation_manager.execute_svm(**self.kwargs)
            elif self.task_type == "svm_cv":
                result = self.interpolation_manager.execute_cross_validation_svm(**self.kwargs)
            else:
                raise ValueError(f"Unknown task type: {self.task_type}")

            if self._is_running:
                self.finished.emit(result)
        except Exception as e:
            if self._is_running:
                self.error.emit(str(e))

    def stop(self):
        """Cancel running task."""
        self._is_running = False
