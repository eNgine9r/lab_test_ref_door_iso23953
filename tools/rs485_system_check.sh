#!/usr/bin/env bash
set -euo pipefail

echo '=== lsusb ==='
lsusb || true
echo

echo '=== dmesg | grep -i usb ==='
dmesg | grep -i usb || true
echo

echo '=== dmesg | grep tty ==='
dmesg | grep tty || true
echo

echo '=== serial devices ==='
ls /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA* /dev/ttyS* 2>/dev/null || true
echo

echo '=== /dev/ttyUSB0 permissions ==='
ls -l /dev/ttyUSB0 2>/dev/null || true
