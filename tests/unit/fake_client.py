#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# fake_client.py
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import logging

from axel import Event

class FakeClient(object):
    """
    """

    def __init__(self):
        """
        """
        self.__logger = logging.getLogger(__name__)

        self.__is_running = False

        self.data_rx = Event()
        self.connection_changed = Event()

    def start(self):
        self.__logger.debug('Starting client')

        self.__is_running = True

    def stop(self):
        self.__logger.debug('Stopping client')

        self.__is_running = False

    def is_running(self):
        return self.__is_running

    def send(self, data, length):
        self.__logger.debug('Sending data back')

        self.data_rx(data, length)
