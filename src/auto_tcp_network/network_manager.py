#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# network_manager.py
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import asyncio
import logging
import random

from axel import Event
from threading import Thread
from transitions.extensions import LockedMachine as Machine
from transitions.extensions.states import add_state_features, Timeout

@add_state_features(Timeout)
class NetworkManager(Machine):
    """Object for managing network resources for the node"""

    DISCOVERY_TIMEOUT_S =           10
    DISCOVERY_TIMEOUT_RAND_FACTOR = 0.25

    def __init__(
        self,
        loop,
        client,
        server=None,
        discovery_timeout=DISCOVERY_TIMEOUT_S,
        randomize_timeout=True):
        """Create a network manager"""
        self.__logger = logging.getLogger(__name__)

        self.discovery_timeout = discovery_timeout
        self.connection_changed = Event()

        self.__loop = loop

        self.__threshold = 0

        self.__connection_count = {}
        self.__connection_count['client'] = 0
        self.__connection_count['server'] = 0

        self.__init_state_machine(randomize_timeout)

        # Required to provide a client
        if None == client:
            raise AttributeError('Client must be specified')

        self.__service_list = {}
        self.__service_list['client'] = client
        self.__service_list['server'] = server

        self.__SERVICE_CONNECTION_THRESHOLD = {}
        self.__SERVICE_CONNECTION_THRESHOLD['client'] = 1
        self.__SERVICE_CONNECTION_THRESHOLD['server'] = 2

        self.data_rx = self.__service_list['client'].data_rx

    def send(self, data):
        """Send data using active role"""
        if self.state is not 'connected':
            self.__logger.warning('System must be connected to send data')
            return

        self.__logger.debug('Queing data for transmission')

        self.__service_list['client'].send(data)

        self.__logger.debug('Data queued')

    def _stop(self):
        '''Stop the client and server (if it exists)'''
        self.__logger.debug('Stopping')

        self.__loop.create_task(self.__stop_process())

        self.__logger.debug('Stopped')

    async def __stop_process(self):
        '''
        '''
        self.__logger.debug('gathering services to stop')

        stop_tasks = [self.__stop_service(service_name) for service_name in ['client','server']]

        self.__logger.debug('waiting for services to stop')

        # schedule the tasks and retrieve results
        await asyncio.gather(*stop_tasks)

        self.__logger.debug('services stopped')

        self.__threshold = 0

        self._stopped()

        self.__logger.debug('Stop process complete')

    def _start_client(self):
        '''Start the client role'''
        self.__start_service('client')

    def _start_server(self):
        '''Start the server role if available'''
        self.__start_service('server')

    def _update_connection_state(self):
        self.connection_changed(self.state)

    def __init_state_machine(self, randomize):
        '''
        '''
        if randomize:
            self.discovery_timeout = random.uniform(
                (self.discovery_timeout * (1 - NetworkManager.DISCOVERY_TIMEOUT_RAND_FACTOR)),
                (self.discovery_timeout * (1 + NetworkManager.DISCOVERY_TIMEOUT_RAND_FACTOR)))

        self.__STATES = [
            { 'name': 'initialized' },
            { 'name': 'searching',
                'timeout':      self.discovery_timeout,
                'on_timeout':   '_start_server',
                'on_enter':     '_start_client' },
            { 'name': 'connected' },
            { 'name': 'disconnecting',
                'on_enter':     '_stop' },
            { 'name': 'stopping',
                'on_enter':     '_stop' },
        ]

        self.__TRANSITIONS = [
            { 'trigger': 'start',           'source': 'initialized',    'dest': 'searching' },
            { 'trigger': '_connected',      'source': 'searching',      'dest': 'connected' },
            { 'trigger': '_disconnected',   'source': 'connected',      'dest': 'disconnecting' },
            { 'trigger': 'stop',            'source': [
                                                'searching',
                                                'connected'],           'dest': 'stopping' },
            { 'trigger': '_stopped',        'source': 'stopping',       'dest': 'initialized'},
            { 'trigger': '_stopped',        'source': 'disconnecting',  'dest': 'searching'}
        ]

        Machine.__init__(
            self,
            states=self.__STATES,
            transitions=self.__TRANSITIONS,
            initial='initialized',
            auto_transitions=False,
            after_state_change='_update_connection_state',
            ignore_invalid_triggers=True)

    def __connection_changed(self, sender, connections):
        '''Monitor connection status by counting connections against a threshold

        Threshold is set based on active roles:
         - Client only requires 1 connection
         - Client and server requires 3 connections, one from the client and 2
           from the server
        '''
        self.__logger.debug('Connection changed.')

        self.__logger.debug('{0}: {1}'.format(sender, connections))

        self.__logger.debug('Threshold: {0}'.format(self.__threshold))

        self.__connection_count[sender] = connections

        count = self.__connection_count['client'] + self.__connection_count['server']

        self.__logger.debug('Count: {0}'.format(count))

        if self.__threshold == 0:
            raise ValueError('No connection threshold set')
        else:
            if count >= self.__threshold:
                if self.state is not 'connected':
                    self.__logger.debug('Connected')
                    self._connected()
            else:
                if self.state is 'connected':
                    self.__logger.debug('Disconnected')
                    self._disconnected()

    async def __stop_service(self, service_name):
        '''
        '''
        self.__logger.debug('Attempting to stop {0}'.format(service_name))

        service = self.__service_list[service_name]

        if service is not None:
            if service.is_running():
                self.__logger.debug('Stopping {0}'.format(service_name))

                await service.stop()

                service.connection_changed -= self.__connection_changed

                self.__logger.debug('{0} stopped'.format(service_name))
            else:
                self.__logger.debug('{0} already stopped'.format(service_name))
        else:
            self.__logger.debug('{0} not available'.format(service_name))

    def __start_service(self, service_name):
        '''
        '''
        service = self.__service_list[service_name]

        if service is not None:
            if not service.is_running():
                self.__logger.debug('Starting {0}'.format(service_name))

                self.__connection_count[service_name] = 0

                # a client on its own can only connect to a single other server
                self.__threshold += self.__SERVICE_CONNECTION_THRESHOLD[service_name]

                service.connection_changed += self.__connection_changed
                service.start(self.__loop)

                self.__logger.debug('{0} started'.format(service_name))
            else:
                self.__logger.debug('{0} already started'.format(service_name))
        else:
            self.__logger.debug('{0} not available'.format(service_name))
