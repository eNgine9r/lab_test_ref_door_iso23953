import argparse

import serial


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', default='/dev/ttyUSB0')
    parser.add_argument('--baudrate', type=int, default=9600)
    parser.add_argument('--timeout', type=float, default=1.0)
    args = parser.parse_args()

    ser = serial.Serial(args.port, args.baudrate, timeout=args.timeout)
    try:
        ser.write(b'hello')
        print(f'Port opened: {ser.is_open}')
    finally:
        ser.close()


if __name__ == '__main__':
    main()
