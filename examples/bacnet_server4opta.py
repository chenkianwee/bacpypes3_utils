"""
R1000 BACnet Device Example
==========================

This script initializes a minimal BACnet server device using BACpypes3.
It is ideal for rapid prototyping and testing with BACnet client tools
or supervisory platforms. You can easily add or remove objects to fit your use case.

Included Objects:
-----------------
- 1 Commandable Analog Value (AV)
- 1 Commandable Binary Value (BV)

Commandable Points:
-------------------
Commandable AV and BV points support writes via the BACnet priority array.
They emulate real-world control points, such as thermostat setpoints, damper commands, etc.

Usage:
------
Run the script with the device name, instance ID, and optional debug flag:

    python mini-device-revisited.py --name BensServerTest --instance 3456789 --debug

Arguments:
----------
- --name       : The BACnet device name (e.g., "BensServerTest")
- --instance   : The BACnet device instance ID (e.g., 3456789)
- --address    : Optional — override the automatically detected IP address and port.
                 Requires ifaddr package for auto-detection.
                 See: https://bacpypes3.readthedocs.io/en/latest/gettingstarted/addresses.html#bacpypes3-addresses
- --debug      : Enables verbose debug logging (built-in to BACpypes3)

"""
import asyncio
import sys
from enum import Enum
from time import sleep
from datetime import date

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.local.binary import BinaryValueObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.debugging import bacpypes_debugging, ModuleLogger

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException

#------------------------------------------------------------------------------------------------------------
# FUNCTIONS
#------------------------------------------------------------------------------------------------------------
def write_register(client: ModbusTcpClient, addr: int, value: int) -> None:
    """Write a register."""
    try:
        rr = client.write_register(addr, value)
        print(f"write is {rr}, Value = {value}")
    except ModbusException as exc:
        print(f"Modbus exception: {exc!s}")

def read_register(client: ModbusTcpClient, addr: int, format: str, reg_type: str = 'Holding Register') -> int:
    """
    read a register.
 
    Parameters
    ----------
    client : ModbusTcpClient
        modbus client object
    
    addr: int
        address of the register

    format: str
        h=int16, H=uint16, i=int32 ,I=uint32, q=int64, Q=uint64, f=float32, d=float64, s=string, bits
    
    reg_type: str, optional
        default is Holding Register. Options are Input Register
    
    Returns
    -------
    vertices : np.ndarray
        np.ndarray(shape(number of edges, number of points in an edge, 3)) vertices of the line
    """
    value = None
    data_type = get_data_type(format)
    # print(data_type)
    count = data_type.value[1]
    var_type = data_type.name
    # print(f"*** Reading register({var_type})")
    try:
        if reg_type == 'Holding Register':
            rr = client.read_holding_registers(address=addr, count=1, device_id=1)
        elif reg_type == 'Input Register':
            rr = client.read_input_registers(address=addr, count=count, device_id=1)
        value = client.convert_from_registers(rr.registers, data_type)
    except ModbusException as exc:
        print(f"Modbus exception: {exc!s}")
    return value

def get_data_type(format: str) -> Enum:
    """Return the ModbusTcpClient.DATATYPE according to the format"""
    for data_type in ModbusTcpClient.DATATYPE:
        if data_type.value[0] == format:
            return data_type
#------------------------------------------------------------------------------------------------------------
#------------------------------------------------------------------------------------------------------------
# Modbus TCP/IP parameters
HOST = "10.0.0.227" # change it to the modbus device of interest
PORT = 502
setpt_addr = 0 #holding registers
airtemp_addr = 0 #input registers
htrelay_addr = 1 #input registers
clgrelay_addr = 2 #input registers
setpt_scalg = 0.01
airtemp_scalg = 0.01

# Debug logging setup
_debug = 0
_log = ModuleLogger(globals())

# Interval for updating values
INTERVAL = 5.0

@bacpypes_debugging
class CommandableAnalogValueObject(Commandable, AnalogValueObject):
    """Commandable Analog Value Object"""

@bacpypes_debugging
class CommandableBinaryValueObject(Commandable, BinaryValueObject):
    """Commandable Binary Value Object"""

@bacpypes_debugging
class SampleApplication:
    def __init__(self, args):
        if _debug:
            _log.debug("Initializing SampleApplication")

        self.app = Application.from_args(args)

        self.setpt = CommandableAnalogValueObject(
            objectIdentifier=("analogValue", 1),
            objectName="tstat-setpt",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            units="degreesCelsius",
            description="Setpoint Temperature of the Belimo Tstat",
        )

        self.airtemp = AnalogValueObject(
            objectIdentifier=("analogValue", 2),
            objectName="read-only-tstat-airtemp",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            units="degreesCelsius",
            description="Air Temperature of the Belimo Tstat",
        )

        self.htrelay = AnalogValueObject(
            objectIdentifier=("analogValue", 3),
            objectName="read-only-tstat-ht",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            description="htg device On/Off status",
        )

        self.clgrelay = AnalogValueObject(
            objectIdentifier=("analogValue", 4),
            objectName="read-only-tstat-clg",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            description="clg device On/Off status",
        )

        for obj in [
            self.setpt,
            self.airtemp,
            self.htrelay,
            self.clgrelay
        ]:
            self.app.add_object(obj)

        _log.info("BACnet Objects initialized.")
        asyncio.create_task(self.update_values())

    async def update_values(self):
        prev_setpt = 0
        while True:
            await asyncio.sleep(INTERVAL)
            # get the present setpt value of bacnet
            setpt_val = self.setpt.presentValue
            airtemp_val = self.airtemp.presentValue
            htg_present_val = self.htrelay.presentValue
            clg_present_val = self.clgrelay.presentValue
            # get the tstat val
            client: ModbusTcpClient = ModbusTcpClient(
                host=HOST,
                port=PORT
            )
            client.connect()
            sleep(1)
            modbus_setpt_val = read_register(client, 0, 'H')
            modbus_airtemp_val = read_register(client, 0, 'H', reg_type='Input Register')
            mb_ht_relay_val = read_register(client, 1, 'H', reg_type='Input Register')
            mb_clg_relay_val = read_register(client, 2, 'H', reg_type='Input Register')
            print(modbus_setpt_val)
            print(modbus_airtemp_val)
            print(mb_ht_relay_val)
            print(mb_clg_relay_val)
            if modbus_setpt_val != None:
                modbus_setpt_val_flt = modbus_setpt_val*setpt_scalg
                if setpt_val == 0.0:
                    # it means this is the 1st loop
                    self.setpt.presentValue = modbus_setpt_val_flt
                    prev_setpt = modbus_setpt_val_flt
                else:
                    # this is not the 1st loop prev_setpt cannt be 0
                    if setpt_val != prev_setpt: # new write to the bacnet setpt
                        if modbus_setpt_val_flt != prev_setpt: # new write from the thermostat
                            # thermostat always take priority, overwrite bacnet
                            self.setpt.presentValue = modbus_setpt_val_flt
                            prev_setpt = modbus_setpt_val_flt
                        elif modbus_setpt_val_flt == prev_setpt: # no new write from thermostat
                            write_register(client, setpt_addr, int(setpt_val/setpt_scalg))
                            prev_setpt = setpt_val
                    else: # no write from bacnet
                        if modbus_setpt_val_flt != prev_setpt: # new write from the thermostat
                            # expose the thermostat setpt
                            self.setpt.presentValue = modbus_setpt_val_flt
                            prev_setpt = modbus_setpt_val_flt
            
            if modbus_airtemp_val != None:
                modbus_airtemp_val_flt = modbus_airtemp_val*airtemp_scalg
                if modbus_airtemp_val_flt != airtemp_val:
                    # expose the thermostat air temp
                    self.airtemp.presentValue = modbus_airtemp_val_flt

            if mb_ht_relay_val != None:
                if mb_ht_relay_val != htg_present_val: # new update from arduino
                    self.htrelay.presentValue = mb_ht_relay_val

            if mb_clg_relay_val != None:
                if mb_clg_relay_val != clg_present_val: # new update from arduino
                    self.clgrelay.presentValue = mb_clg_relay_val

            client.close()

            if _debug:
                _log.debug(f"Setpoint: {self.setpt.presentValue}")
                _log.debug(f"Air Temp: {self.airtemp.presentValue}")
                _log.debug(f"Htg Relay: {self.htrelay.presentValue}")
                _log.debug(f"Clg Relay: {self.clgrelay.presentValue}")

async def main():
    global _debug

    parser = SimpleArgumentParser()
    args = parser.parse_args()

    if args.debug:
        _debug = 1
        _log.set_level("DEBUG")
        _log.debug("Debug mode enabled")

    if _debug:
        _log.debug(f"Parsed arguments: {args}")

    app = SampleApplication(args)
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _log.info("Keyboard interrupt received, shutting down.")
        sys.exit(0)
