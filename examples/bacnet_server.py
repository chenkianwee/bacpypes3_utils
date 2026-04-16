import asyncio
import random
import sys

from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.local.binary import BinaryValueObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.debugging import bacpypes_debugging, ModuleLogger

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

        self.read_only_av = AnalogValueObject(
            objectIdentifier=("analogValue", 1),
            objectName="read-only-av",
            presentValue=4.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            units="degreesFahrenheit",
            description="Simulated Read-Only Analog Value",
        )

        self.read_only_bv = BinaryValueObject(
            objectIdentifier=("binaryValue", 1),
            objectName="read-only-bv",
            presentValue="active",
            statusFlags=[0, 0, 0, 0],
            description="Simulated Read-Only Binary Value",
        )

        self.commandable_av = CommandableAnalogValueObject(
            objectIdentifier=("analogValue", 2),
            objectName="commandable-av",
            presentValue=0.0,
            statusFlags=[0, 0, 0, 0],
            covIncrement=1.0,
            units="degreesFahrenheit",
            description="Commandable Analog Value (Simulated)",
        )

        self.commandable_bv = CommandableBinaryValueObject(
            objectIdentifier=("binaryValue", 2),
            objectName="commandable-bv",
            presentValue="inactive",
            statusFlags=[0, 0, 0, 0],
            description="Commandable Binary Value (Simulated)",
        )

        for obj in [
            self.read_only_av,
            self.read_only_bv,
            self.commandable_av,
            self.commandable_bv
        ]:
            self.app.add_object(obj)

        _log.info("BACnet Objects initialized.")
        asyncio.create_task(self.update_values())

    async def update_values(self):
        test_values = [
            ("active", 1.0),
            ("inactive", 2.0),
            ("active", 3.0),
            ("inactive", 4.0),
        ]
        while True:
            await asyncio.sleep(INTERVAL)
            prob = random.random()
            if prob < 0.3:
                next_value = test_values.pop(0)
                test_values.append(next_value)

                self.read_only_av.presentValue = next_value[1]
                self.read_only_bv.presentValue = next_value[0]

            if _debug:
                _log.debug(f"Read-Only AV: {self.read_only_av.presentValue}")
                _log.debug(f"Read-Only BV: {self.read_only_bv.presentValue}")
                _log.debug(f"Commandable AV: {self.commandable_av.presentValue}")
                _log.debug(f"Commandable BV: {self.commandable_bv.presentValue}")

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
