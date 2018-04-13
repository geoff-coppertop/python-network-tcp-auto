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

from aiozeroconf import ServiceInfo, Zeroconf

class Server(object):
    '''TCP server object that broadcasts its availability using zeroconf'''

    def __init__(self, loop, service_type, port):
        '''Create a TCP server'''
        self.__logger = logging.getLogger('server')

        # this keeps track of all the clients that connected to our
        # server.  It can be useful in some cases, for instance to
        # kill client connections or to broadcast some data to all
        # clients...
        self.__clients = {} # task -> (reader, writer)
        self.__port = port
        self.__server = None
        self.__loop = loop
        self.__shutdown_in_progress = False
        self.__queue = asyncio.Queue()
        self.__info = ServiceInfo(
            service_type,
            'TTC-%s.%s' % (
                uuid.uuid3(uuid.NAMESPACE_DNS, socket.gethostname()),
                service_type),
            socket.inet_aton(
                socket.gethostbyname(socket.gethostname())),
            self.__port,
            0,
            0,
            {},
            socket.gethostname() + '.')

    def start(self):
        '''Start the server'''
        self.__logger.debug('Server started')

        # Exit here if we're already running, we don't want to randomly
        # restart, log as warning
        if self.is_running():
            return

        # Start TCP server
        start_tcp_task = self.__loop.create_task(self.__start_tcp())
        start_tcp_task.add_done_callback(self.__start_broadcast)

    def stop(self):
        '''
        Stop the server

        Stop zeroconf advertising and close listening socket(s). This method
        runs the loop until the server sockets are closed.
        '''
        if self.is_running():
            self.__shutdown_in_progress = True

            # Stop zeroconf service broadcast first so that we don't collect more
            # clients as were trying to shutdown
            self.__loop.run_until_complete(self.__stop_broadcast())

            self.__queue.put_nowait(b'')

            self.__loop.run_until_complete(self.__server.wait_closed())

            self.__server = None

        self.__shutdown_in_progress = False


    def is_running(self):
        '''Inidication that the server is running'''
        return (self.__server is not None)

    async def __start_tcp(self):
        '''
        Start the TCP server process

        Starts a TCP streaming server that services all interfaces on the device
        Starts the write process to service the incoming message queue
        '''
        self.__server = await asyncio.start_server(
            self.__accept_client,
            '0.0.0.0',
            self.__port,
            loop=self.__loop)

        self.__loop.create_task(self.__write_process())

    def __accept_client(self, reader, writer):
        '''
        Handles incoming client connections
        '''
        # Start a new asyncio.Task to handle this specific client connection
        task = self.__loop.create_task(self.__handle_client_read(reader))

        # Store a tuple for the client connection indexed by the task for the
        # connection
        self.__clients[task] = (reader, writer)

        self.__logger.debug('Client(s) connected: {0}'.format(len(self.__clients)))

        # Add the client_done callback to be run when the future becomes done
        task.add_done_callback(self.__client_done)

    def __client_done(self, task):
        '''
        Client cleanup process
        '''
        # When the tasks that handles the specific client connection is done
        client = self.__clients[task]
        client[1].close()

        del self.__clients[task]

        self.__logger.debug('Client(s) connected: {0}'.format(len(self.__clients)))

        if not self.__clients and self.__shutdown_in_progress:
            self.__server.close()

    async def __handle_client_read(self, reader):
        '''
        Client read process
        '''
        while not reader.at_eof():
            data = await reader.read(4)

            if data:
                size = int.from_bytes(data, 'little')

                data = await reader.read(size)

                try:
                    self.__queue.put_nowait(data)
                except asyncio.QueueFull:
                    self.__logger.warning('Queue full, data lost')

    async def __write_process(self):
        '''
        Client write process
        '''
        while True:
            # Wait for new data from the queue
            data = await self.__queue.get()

            if data:
                # Valid data gets repeated to all clients including the one who produced it?
                for client in self.__clients:
                    # Pull the writer out of the client tuple (reader, writer)
                    writer = self.__clients[client][1]

                    # send the size first so that the receiver knows how many bytes
                    # to expect
                    size = len(data)

                    writer.write(size.to_bytes(4, 'little'))

                    await writer.drain()

                    # Now write the data out
                    writer.write(data)

                    await writer.drain()

            self.__queue.task_done()

            if not data:
                for client in self.__clients:
                    # Pull the writer out of the client tuple (reader, writer)
                    writer = self.__clients[client][1]

                    # Close the writer/transport, this may need to be paired with a
                    # write_eof
                    writer.close()

                break

        if not self.__clients and self.__shutdown_in_progress:
            # There are no clients connected so shutdown the server
            self.__server.close()

    def __start_broadcast(self, task):
        '''Start zeroconf service broadcast'''
        self.__zc = Zeroconf(self.__loop, address_family = [netifaces.AF_INET])
        self.__loop.create_task(self.__zc.register_service(self.__info))

    async def __stop_broadcast(self):
        '''Stop zeroconf service broadcast'''
        await self.__zc.unregister_service(self.__info)
        await self.__zc.close()



