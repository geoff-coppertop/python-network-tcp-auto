#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# network_manager.py
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import logging
import random

from transitions.extensions import LockedMachine as Machine
from transitions.extensions.states import add_state_features, Timeout

@add_state_features(Timeout)
class NetworkManager(Machine):
    """Object for managing network resources for the node"""

    DISCOVERY_TIMEOUT_S =           10
    DISCOVERY_TIMEOUT_RAND_FACTOR = 0.25

    def __init__(
        self,
        client,
        server=None,
        discovery_timeout=DISCOVERY_TIMEOUT_S,
        randomize_timeout=True):
        """Create a network manager"""
        self.__logger = logging.getLogger('network_manager')

        self.discovery_timeout = discovery_timeout

        self.__connection_count = {}
        self.__connection_count['client'] = 0
        self.__connection_count['server'] = 0

        self.__init_state_machine(randomize_timeout)

        # Required to provide a client
        if None == client:
            raise AttributeError('Client must be specified')

        self.__client = client

        self.data_rx = self.__client.data_rx

        self.__server = server

    def send(self, data, length):
        """Send data using active role"""
        if self.state is not 'connected':
            raise SystemError('System must be connected to send data')

        self.__logger.debug('Queing data for transmission')

        self.__client.send(data, length)

        self.__logger.debug('Data queued')

    def _stop(self):
        '''Stop the client and server (if it exists)'''
        self.__logger.debug('Stopping')

        # Stop client first, so that it doesn't rejoin another server as the
        # network heals itself
        if self.__client.is_running():
            self.__logger.debug('Stopping client')

            try:
                self.__client.connection_changed -= self.__connection_changed
            except ValueError as e:
                self.__logger.debug(e)

            self.__connection_count['client'] = 0
            self.__client.stop()

            self.__logger.debug('Client stopped')
        else:
            self.__logger.debug('Client already stopped')


        # If there is a running server stop it
        if self.__server is not None:
            if self.__server.is_running():
                self.__logger.debug('Stopping server')

                self.__server.connection_changed -= self.__connection_changed
                self.__connection_count['server'] = 0
                self.__server.stop()

                self.__logger.debug('Server stopped')
            else:
                self.__logger.debug('Server already stopped')
        else:
            self.__logger.debug('Cannot stop server, not supported')

        # Invalidate the threshold used for connection counting
        self.__threshold = 0

        self.__logger.debug('Stop completed')

    def _start_client(self):
        """Start the client role"""
        if not self.__client.is_running():
            self.__logger.debug('Staring client')

            self.__connection_count['client'] = 0
            # a client on its own can only connect to a single other server
            self.__threshold += 1

            self.__client.connection_changed += self.__connection_changed
            self.__client.start()

            self.__logger.debug('Client started')
        else:
            self.__logger.debug('Client already started')

    def _start_server(self):
        '''Start the server role if available'''
        if self.__server is not None:
            if not self.__server.is_running():
                self.__logger.debug('Staring server')

                self.__connection_count['server'] = 0
                # a server must show two connections, one from the client
                # associated with the server and another client
                self.__threshold += 2

                self.__server.connection_changed += self.__connection_changed
                self.__server.start()

                self.__logger.debug('Server started')
            else:
                self.__logger.debug('Server already started')
        else:
            # We are purposefully ignoring the else case because there may be
            # nodes where we don't want to act as a server
            self.__logger.debug('Cannot start server, not supported')

    def __init_state_machine(self, randomize):
        '''
        '''
        if randomize:
            self.discovery_timeout = random.uniform(
                (self.discovery_timeout * (1 - NetworkManager.DISCOVERY_TIMEOUT_RAND_FACTOR)),
                (self.discovery_timeout * (1 + NetworkManager.DISCOVERY_TIMEOUT_RAND_FACTOR)))

        self.__STATES = [
            { 'name': 'initializing',
                'on_enter':     '_stop' },
            { 'name': 'searching',
                'timeout':      self.discovery_timeout,
                'on_timeout':   '_start_server',
                'on_enter':     [ '_stop',
                                  '_start_client' ]},
            { 'name': 'connected' },
        ]

        self.__TRANSITIONS = [
            { 'trigger': 'search',          'source': 'initializing',   'dest': 'searching' },
            { 'trigger': '_connected',      'source': 'searching',      'dest': 'connected' },
            { 'trigger': '_disconnected',   'source': 'connected',      'dest': 'searching' },
            { 'trigger': 'shutdown',        'source': '*',              'dest': 'initializing' }
        ]

        Machine.__init__(
            self,
            states=self.__STATES,
            transitions=self.__TRANSITIONS,
            initial='initializing',
            auto_transitions=False)

    def __connection_changed(self, sender, connections):
        '''Monitor connection status by counting connections against a threshold

        Threshold is set based on active roles:
         - Client only requires 1 connection
         - Client and server requires 3 connections, one from the client and 2
           from the server
        '''
        self.__logger.debug('Connection changed. Bob')

        self.__logger.debug('{0}: {1}'.format(sender, connections))

        self.__logger.debug('Threshold: {0}'.format(self.__threshold))

        self.__connection_count[sender] = connections

        count = self.__connection_count['client'] + self.__connection_count['server']

        self.__logger.debug('Count: {0}'.format(count))

        if self.__threshold == 0:
            raise ValueError('No connection threshold set')
        else:
            if count >= self.__threshold:
                self._connected()
            else:
                self._disconnected()
