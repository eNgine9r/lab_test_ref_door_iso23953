import argparse
import json
import os
from pathlib import Path

from logger import get_test_logger
from modbus_client import ModbusClientFactory
from relay_controller import RelayController
from scheduler import StartScheduler
from test_logic import ISO23953DoorTest


def load_config(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def apply_cli_overrides(config: dict, args):
    if args.mode:
        config['mode'] = args.mode.upper()
    if args.doors is not None:
        config['doors'] = args.doors
    if args.debug:
        config['debug'] = True
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', default='config.json')
    parser.add_argument('--mode', choices=['LT', 'MT'])
    parser.add_argument('--doors', type=int)
    parser.add_argument('--debug', action='store_true')
    args = parser.parse_args()

    config = apply_cli_overrides(load_config(args.config), args)
    logger = get_test_logger()
    logger.info('application start')
    logger.info('loaded config %s', config)

    schedule_cfg = config.get('schedule', {})
    scheduler = StartScheduler(logger)
    scheduler.apply_start_delay(int(config.get('start_delay_sec', 0)))
    scheduler.wait_for_schedule(bool(schedule_cfg.get('enabled', False)), schedule_cfg.get('start_time', '22:00'))

    simulation_mode = bool(config.get('simulation', False))
    modbus_cfg = config.get('modbus', {})

    if modbus_cfg.get('port'):
        os.environ['MODBUS_PORT'] = str(modbus_cfg['port'])
    if modbus_cfg.get('baudrate'):
        os.environ['MODBUS_BAUDRATE'] = str(modbus_cfg['baudrate'])
    if modbus_cfg.get('slave_id'):
        os.environ['MODBUS_SLAVE_ID'] = str(modbus_cfg['slave_id'])
    if modbus_cfg.get('backend'):
        os.environ['MODBUS_BACKEND'] = str(modbus_cfg['backend'])

    controller = ModbusClientFactory.create(simulation_mode=simulation_mode)

    if hasattr(controller, '_port') and modbus_cfg.get('port'):
        controller._port = modbus_cfg['port']

    relay = RelayController(controller, logger)
    if not relay.connect():
        logger.error('modbus connect failed')
        raise SystemExit(1)

    test = ISO23953DoorTest(config, relay, logger)
    try:
        test.run()
    finally:
        relay.close_all_relays()
        controller.close()
        logger.info('application stop')


if __name__ == '__main__':
    main()
