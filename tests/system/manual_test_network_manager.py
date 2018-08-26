#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# manual_test_network_manager.py
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import asyncio
import logging
import random

from auto_tcp_network import Client, Server, NetworkManager

loop = None
data_gen_task = None
netman = None
is_connected = False

def main():
    global data_gen_task
    global loop
    global netman

    setup_logging()

    loop = asyncio.get_event_loop()

    port = 11111
    service_type = '_bob._tcp.local.'

    logging.debug('Starting a server')
    server = Server(service_type, port)

    logging.debug('Starting a client')
    client = Client(service_type, port)

    logging.debug('Starting the network manager')
    netman = NetworkManager(loop, client, server)

    netman.connection_changed += connection_changed
    netman.data_rx += data_rx

    logging.debug('Starting discovery')
    netman.start()

    try:
        loop.run_forever()
    except KeyboardInterrupt:
        logging.debug("Stopping...")

        netman.stop()

        if data_gen_task:
            logging.debug("Waiting for data generation to end.")

            loop.run_until_complete(data_gen_task)

            logging.debug("Data generation task completed")
    finally:
        logging.debug('Collecting pending tasks')

        pending = asyncio.Task.all_tasks()

        logging.debug('Waiting for pending tasks to complete')

        try:
            loop.run_until_complete(asyncio.gather(*pending))
        except asyncio.CancelledError:
            logging.debug('task cancelled')

def data_rx(sender, data):
    logging.debug('RX: {0}'.format(data))

async def gen_data():
    global netman
    global is_connected

    logging.debug("Starting data generation")

    while is_connected:
        data = random.randint(0, 10).to_bytes(1,'little')

        logging.debug('TX: {0}'.format(data))

        netman.send(data)

        await asyncio.sleep(random.randint(1, 10))

    logging.debug('Terminating data generation')

def connection_changed(state):
    global loop
    global is_connected
    global data_gen_task

    logging.debug('Connection state: {}'.format(state))

    if state is 'connected':
        is_connected = True

        data_gen_task = loop.create_task(gen_data())
    else:
        is_connected = False

def setup_logging():
    logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    main()
