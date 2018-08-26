#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# fake_server.py
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import logging

from axel import Event

class FakeServer(object):
    """
    """

    def __init__(self):
        """
        """
        self.__logger = logging.getLogger(__name__)

        self.__is_running = False

        self.connection_changed = Event()

    def start(self):
        self.__logger.debug('Starting server')

        self.__is_running = True

    def stop(self):
        self.__logger.debug('Stopping server')

        self.__is_running = False

    def is_running(self):
        return self.__is_running
