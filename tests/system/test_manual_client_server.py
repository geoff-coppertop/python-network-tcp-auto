#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# test_manual_client_server.py
#
# From the root directory this can be run using the following command:
#   python -m tests.system.app.net.manual_test_client_server -t server
#   python -m tests.system.app.net.manual_test_client_server -t client
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import argparse
import asyncio
import logging
import random

from auto_tcp_network import Client, Server

client = None
server = None

is_connected = False

data_gen_task = None

def main():
    global client
    global server
    global data_gen_task

    role = None

    setup_logging()

    args = setup_args()

    loop = asyncio.get_event_loop()

    port = 11111
    service_type = '_bob._tcp.local.'

    if args.type == 'server':
        # Starting a client
        print('Starting a server')
        server = Server(loop, service_type, port)
        server.start()

        role = server
    else:
        print('Starting a client')
        client = Client(loop, service_type, port)
        client.start(connected, disconnected, data_rx)

        role = client
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("Stopping...")
        role.stop()

        if data_gen_task:
            loop.run_until_complete(data_gen_task)
    finally:
        loop.close()

def connected():
    logging.debug('CONNECTED')

    global is_connected
    global data_gen_task

    is_connected = True

    loop = asyncio.get_event_loop()

    data_gen_task = loop.create_task(gen_data())

def disconnected():
    logging.debug('DISCONNECTED')

    global is_connected

    is_connected = False

def data_rx(data):
    logging.debug('RX: {0}'.format(data))

async def gen_data():
    global client
    global is_connected

    while is_connected:
        data = random.randint(0, 10).to_bytes(1,'little')
        logging.debug('TX: {0}'.format(data))
        client.send(data)

        await asyncio.sleep(2)

def setup_logging():
    logging.basicConfig(level=logging.DEBUG)

def setup_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        '-t',
        '--type',
        choices=['server','client'],
        help='Role to start')

    return parser.parse_args()

if __name__ == '__main__':
    main()
