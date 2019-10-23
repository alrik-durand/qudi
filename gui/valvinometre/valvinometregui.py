# -*- coding: utf-8 -*-

"""
This file contains the QuDi main GUI for pulsed measurements.

QuDi is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

QuDi is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with QuDi. If not, see <http://www.gnu.org/licenses/>.

Copyright (c) the Qudi Developers. See the COPYRIGHT.txt file at the
top-level directory of this distribution and at <https://github.com/Ulm-IQO/qudi/>
"""

import numpy as np
import os
import pyqtgraph as pg
import datetime

from core.connector import Connector
from core.statusvariable import StatusVar
from core.util import units
from core.util.helpers import natural_sort
from gui.colordefs import QudiPalettePale as palette
from gui.fitsettings import FitSettingsDialog
from gui.guibase import GUIBase
from qtpy import QtCore, QtWidgets, uic
from qtwidgets.scientific_spinbox import ScienDSpinBox, ScienSpinBox
from enum import Enum

class ValvinometreMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_valvinometre_maingui.ui')

        # Load it
        super(ValvinometreMainWindow, self).__init__()

        uic.loadUi(ui_file, self)
        self.show()


class SettingsTab(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_valvinometre_settings.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        
class CameraTab(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_valvinometre_camera.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)

class TraceTab(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_valvinometre_trace.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        
class BgTab(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_valvinometre_bg.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)

class SpectroTab(QtWidgets.QWidget):
    def __init__(self):
        # Get the path to the *.ui file
        this_dir = os.path.dirname(__file__)
        ui_file = os.path.join(this_dir, 'ui_valvinometre_spectro.ui')
        # Load it
        super().__init__()
        uic.loadUi(ui_file, self)
        
class ValvinometreGui(GUIBase):   
    """ This is the main GUI Class for pulsed measurements. """
    ## declare connectors
    valvinologic = Connector(interface='CounterLogic')

    # status var

    def __init__(self, config, **kwargs):
        super().__init__(config=config, **kwargs)
        
    def on_activate(self):
        """ Initialize, connect and configure the spectrometer GUI.

        Establish general connectivity and activate the different tabs of the
        GUI.
        """
        self._mw = ValvinometreMainWindow()
        self._st = SettingsTab()
        self._ct = CameraTab()
        self._tt = TraceTab()
        self._bt = BgTab()
        self._spt = SpectroTab()
        
        self._mw.tabWidget.addTab(self._st, 'Settings')
        self._mw.tabWidget.addTab(self._ct, 'Camera')
        self._mw.tabWidget.addTab(self._tt, 'Trace')
        self._mw.tabWidget.addTab(self._bt, 'Background')
        self._mw.tabWidget.addTab(self._spt, 'Spectrometer')
        
        self._activate_main_ui()
        self._activate_settings_ui()
        self._activate_camera_ui()
        self._activate_trace_ui()
        self._activate_bg_ui()
        self._activate_spectro_ui()
        
        self._connect_main_window_signals()
        self._connect_settings_signals()
        self._connect_camera_signals()
        self._connect_trace_signals()
        self._connect_bg_signals()
        self._connect_spectro_signals()
        self._connect_logic_signals()
        
        self.show()
        return
    
    def on_deactivate(self):
        """ Undo the Definition, configuration and initialisation of the 
        spectrometer GUI.

        This deactivation disconnects all the graphic modules, which were
        connected in the initUI method.
        """
        self._deactivate_main_ui()
        self._deactivate_settings_ui()
        self._deactivate_camera_ui()
        self._deactivate_trace_ui()
        self._deactivate_bg_ui()
        self._deactivate_spectro_ui()
        
        self._disconnect_main_window_signals()
        self._disconnect_settings_signals()
        self._disconnect_camera_signals()
        self._disconnect_trace_signals()
        self._disconnect_bg_signals()
        self._disconnect_spectro_signals()
        self._disconnect_logic_signals()
        
        self._mw.close()
        return
    
    def show(self):
        """Make main window visible and put it above all other windows. """
        QtWidgets.QMainWindow.show(self._mw)
        self._mw.activateWindow()
        self._mw.raise_()
        return
    
    def _activate_main_ui(self):
        pass
    
    def _activate_settings_ui(self):
        pass
    
    def _activate_camera_ui(self):
        pass
    
    def _activate_trace_ui(self):
        pass
    
    def _activate_bg_ui(self):
        pass
    
    def _activate_spectro_ui(self):
        pass
        
    def _connect_main_window_signals(self):
        pass
    
    def _connect_settings_signals(self):
        pass
 
    def _connect_camera_signals(self):
        pass
 
    def _connect_trace_signals(self):
        pass
    
    def _connect_bg_signals(self):
        pass
    
    def _connect_spectro_signals(self):
        pass
    
    def _connect_logic_signals(self):
        pass
    
    def _deactivate_main_ui(self):
        pass
   
    def _deactivate_settings_ui(self):
        pass
    
    def _deactivate_camera_ui(self):
        pass
    
    def _deactivate_trace_ui(self):
        pass
    
    def _deactivate_bg_ui(self):
        pass
    
    def _deactivate_spectro_ui(self):
        pass
       
    def _disconnect_main_window_signals(self):
        pass
    
    def _disconnect_settings_signals(self):
        pass
    
    def _disconnect_camera_signals(self):
        pass
    
    def _disconnect_trace_signals(self):
        pass
    
    def _disconnect_bg_signals(self):
        pass
    
    def _disconnect_spectro_signals(self):
        pass
    
    def _disconnect_logic_signals(self):
        pass
   
       
       
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        