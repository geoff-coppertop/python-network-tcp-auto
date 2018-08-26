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

loop = None

is_connected = False

data_gen_task = None

def main():
    global client
    global server
    global data_gen_task
    global loop

    role = None

    setup_logging()

    args = setup_args()

    loop = asyncio.get_event_loop()

    port = 11111
    service_type = '_bob._tcp.local.'

    if args.type == 'server':
        # Starting a client
        logging.debug('Starting a server')
        server = Server(loop, service_type, port)
        server.connection_changed += connection_changed
        server.start()

        role = server
    else:
        logging.debug('Starting a client')
        client = Client(loop, service_type, port)
        client.connection_changed += connection_changed
        client.data_rx += data_rx
        client.start()

        role = client
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logging.debug("Stopping...")
        role.stop()

        if data_gen_task:
            loop.run_until_complete(data_gen_task)
    finally:
        loop.close()

def connection_changed(sender, connections):
    global is_connected
    global loop

    if sender == 'client':
        if connections > 0:
            global data_gen_task

            logging.debug('CONNECTED')

            is_connected = True

            data_gen_task = loop.create_task(gen_data())
        else:
            logging.debug('DISCONNECTED')

            is_connected = False
    elif sender == 'server':
        logging.debug('Server connected')
    else:
        raise ValueError('Sender {0} not supported.'.format(sender))

def data_rx(sender, data):
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
