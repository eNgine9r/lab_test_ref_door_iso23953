import argparse

import minimalmodbus


def build_instrument(port: str, slave: int):
    instrument = minimalmodbus.Instrument(port, slave)
    instrument.serial.baudrate = 9600
    instrument.serial.bytesize = 8
    instrument.serial.parity = minimalmodbus.serial.PARITY_NONE
    instrument.serial.stopbits = 1
    instrument.serial.timeout = 1
    return instrument


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='/dev/ttyUSB0')
    parser.add_argument('--slave', type=int, default=1)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()

    instrument = build_instrument(args.port, args.slave)
    print('Read bits:', instrument.read_bits(0, 1))
    if args.write:
        instrument.write_bit(0, 1)
        print('Write bit OK')


if __name__ == '__main__':
    main()
