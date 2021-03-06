#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# server.py
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import asyncio
import logging
import socket
import uuid
import netifaces

from aiozeroconf import ServiceBrowser, ServiceStateChange, Zeroconf
from axel import Event

class Client(object):
    '''TCP client object that searches for a server using zeroconf'''

    def __init__(self, service_type, port):
        '''Create a TCP client'''
        self.__logger = logging.getLogger(__name__)

        self.connection_changed = Event(sender='client')
        self.data_rx = Event(sender='client')

        self.__service_type = service_type
        self.__loop = None
        self.__browser = None
        self.__port = port
        self.__queue = asyncio.Queue()
        self.__server_connection = None
        self.__shutdown_in_progress = False

    def start(self, loop):
        '''Start the client'''
        # Exit here if we're already running, we don't want to randomly
        # restart, log as warning
        if self.is_running():
            return

        self.__loop = loop

        # Start zeroconf service broadcast
        self.__start_service_discovery()

    async def stop(self):
        '''Stop the client'''
        self.__shutdown_in_progress = True

        if self.__is_browsing():
            self.__logger.debug("I'm going to stop browsing now...")

            # Stop zeroconf service discovery first so that we don't collect more
            # clients as were trying to shutdown
            await self.__stop_service_discovery()

        # Only do this next bit if we're actually connected
        if self.__is_connected():
            self.__logger.debug("I'm going to start disconnecting now...")

            await self.__stop_server_connection()

        self.__shutdown_in_progress = False

    def is_running(self):
        '''Inidication that the client is running'''
        return self.__is_browsing() or self.__is_connected()

    async def __stop_server_connection(self):
        # Pushing an empty byte into the queue will cause the write_task to
        # end, and should take the read_task with it... fingers crossed...
        self.__queue.put_nowait(b'')

        self.__logger.debug('About to wait for server connection to terminate')

        await self.__server_connection

        self.__logger.debug('Server connection terminated')

    def send(self, data):
        '''Send data on the client interface'''
        try:
            self.__queue.put_nowait(data)
        except asyncio.QueueFull:
            self.__logger.warning('Queue full, data lost')

    def __is_browsing(self):
        '''Indication that the client is browsing for a server'''
        return (self.__browser is not None)

    def __is_connected(self):
        '''Indication that the client is connected to a server'''
        return (self.__server_connection is not None)

    def __on_service_state_change(self, zc, service_type, name, state_change):
        '''
        Handle service changes

        If we 'Added' a service then intiate a connection
        '''
        self.__logger.debug(
            'Service {0} of type {1} state changed: {2}'.format(
                name,
                service_type,
                state_change))

        if state_change is ServiceStateChange.Added:
            self.__loop.create_task(self.__found_service(name))

    async def __found_service(self, name):
        '''
        Start connection process

        Found the service we were looking for, start the connection process
        '''
        info = await self.__zc.get_service_info(self.__service_type, name)

        if info:
            self.__logger.debug("Address: %s:%d" % (socket.inet_ntoa(info.address), info.port))
            self.__logger.debug("Server: %s" % (info.server,))

            try:
                reader, writer = await asyncio.open_connection(
                    socket.inet_ntoa(info.address),
                    info.port,
                    loop=self.__loop)

                self.__server_connection = self.__loop.create_task(self.__connected_process(reader, writer))
                self.__server_connection.add_done_callback(self.__disconnected_process)
            except ConnectionRefusedError:
                self.__logger.debug('Connection refused')

    def __start_service_discovery(self):
        '''Start zeroconf service discovery'''
        self.__zc = Zeroconf(self.__loop, address_family = [netifaces.AF_INET])
        self.__browser = ServiceBrowser(
            self.__zc,
            self.__service_type,
            handlers=[self.__on_service_state_change])

    async def __stop_service_discovery(self):
        '''Stop zeroconf service discovery'''
        self.__browser.cancel()
        await self.__zc.close()
        self.__browser = None
        self.__zc = None

    async def __handle_server_read(self, reader):
        '''Server read process'''
        # Keep reading until we encounter a null byte
        while not reader.at_eof():
            # Read the size bytes first
            data = await reader.read(4)

            # If data is not null byte read data from stream
            if data:
                size = int.from_bytes(data, 'little')

                data = await reader.read(size)

                # Send data to receiving process
                self.data_rx(data)

        # If we aren't shutting dow (because of a client.stop) put a null byte
        # in the buffer to cause the write process to terminate
        if not self.__shutdown_in_progress:
            self.__queue.put_nowait(b'')

    async def __handle_server_write(self, writer):
        '''Server write process'''
        while True:
            # Wait for new data from the queue
            data = await self.__queue.get()

            if data:
                # send the size first so that the receiver knows how many bytes
                # to expect
                size = len(data)

                writer.write(size.to_bytes(4, 'little'))

                await writer.drain()

                # Now write the data out
                writer.write(data)

                # Pause the process to let the write out happen
                await writer.drain()

            self.__queue.task_done()

            if not data:
                break

        # Close the writer/transport, this may need to be paired with a
        # write_eof
        writer.close()

    async def __connected_process(self, reader, writer):
        '''
        Process that runs on connect
            1. Stop service discovery, we've already foudn someone that wants
               to talk to us
            2. Setup tasks to handle communication R/W with the server and then
               wait
        '''
        self.__logger.debug('connection changed')

        self.connection_changed(1)

        self.__logger.debug('stopping service discovery')

        # Stop service discovery because we've found something
        await self.__stop_service_discovery()

        self.__logger.debug('set up server r/w processes')

        await asyncio.gather(*[
            self.__handle_server_read(reader),
            self.__handle_server_write(writer)])

        self.__logger.debug('connected process complete')

    def __disconnected_process(self, task):
        '''
        Process that runs on disconnect
            1. Invalidate server connection
            2. Notify external actor that we are disconnected
            3. If not shutting down restart service discovery

        Task is not used.
        '''
        self.__server_connection = None

        self.connection_changed(0)

        if not self.__shutdown_in_progress:
            # Start service discovery because we disconnected not because the
            # client is being shutdown
            self.__start_service_discovery()
