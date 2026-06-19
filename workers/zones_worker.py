# -*- coding: utf-8 -*-
"""Background worker for zone calculation tasks."""

from qgis.PyQt.QtCore import QThread, pyqtSignal


class ZonesWorker(QThread):
    """Async worker for fuzzy c-means clustering."""

    # Signals
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, zones_manager, task_type, **kwargs):
        super().__init__()
        self.zones_manager = zones_manager
        self.task_type = task_type
        self.kwargs = kwargs
        self._is_running = True

    def run(self):
        """Execute zone calculation task."""
        try:
            if self.task_type == "ideal_zones":
                result = self.zones_manager.calculate_ideal_zones(**self.kwargs)
            elif self.task_type == "calculate_zones":
                result = self.zones_manager.calculate_zones(**self.kwargs)
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
