"""Pestañas del editor."""
from .aids_tab import AidsTab
from .advanced_tab import AdvancedTab
from .chassis_tab import ChassisTab
from .dashboard_tab import DashboardTab
from .engine_tab import MotorTab
from .gearbox_tab import GearboxTab
from .info_tab import InfoTab

__all__ = [
    "DashboardTab",
    "MotorTab",
    "GearboxTab",
    "ChassisTab",
    "InfoTab",
    "AidsTab",
    "AdvancedTab",
]
