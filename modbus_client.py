import os

from hardware_simulator import HardwareSimulator
from modbus_controller import ModbusController


class ModbusClientFactory:
    @staticmethod
    def create(simulation_mode: bool = False):
        if simulation_mode or os.getenv('SIMULATION_MODE', '0') in {'1', 'true', 'True'}:
            return HardwareSimulator()
        return ModbusController()
