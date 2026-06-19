# -*- coding: utf-8 -*-
"""
/***************************************************************************
 smart_mapAbout
                                 A QGIS plugin
 Interpolation using Kriging and Machine Learning and generate Management Zones
 for a set of soil samples.
                             -------------------
        begin                : 2018-08-15
        copyright            : (C) 2018 by Gustavo Willam Pereira (IFSUDESTE-MG) /
                               Domingos Sárvio Magalhães Valente (UFV) /
                               Daniel Marçal de Queiroz (UFV) /
                               Andre Luiz de Freitas Coelho (UFV) /
                               Sandro Manuel Carmelino Hurtado (UFU)
        email                : gustavowillam@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/

Pure-PyQt about dialog (no Qt Designer .ui file).
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox
)
from qgis.PyQt.QtCore import Qt


class smart_mapAbout(QDialog):
    """Credits / about dialog, built programmatically in pure PyQt."""

    def __init__(self, parent=None):
        super(smart_mapAbout, self).__init__(parent)
        self.setWindowTitle('Smart-Map')
        self.setMinimumWidth(460)

        layout = QVBoxLayout()

        title = QLabel('Smart-Map')
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            'Interpolation using Kriging and Machine Learning and\n'
            'generation of Management Zones for soil samples.'
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        credits = QLabel(
            '<br><b>Authors</b><br>'
            'Gustavo Willam Pereira (IFSUDESTE-MG)<br>'
            'Domingos Sárvio Magalhães Valente (UFV)<br>'
            'Daniel Marçal de Queiroz (UFV)<br>'
            'André Luiz de Freitas Coelho (UFV)<br>'
            'Sandro Manuel Carmelino Hurtado (UFU)<br>'
            '<br>'
            'Contact: gustavowillam@gmail.com'
        )
        credits.setTextFormat(Qt.RichText)
        credits.setAlignment(Qt.AlignCenter)
        credits.setWordWrap(True)
        layout.addWidget(credits)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.setLayout(layout)
