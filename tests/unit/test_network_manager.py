#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#-------------------------------------------------------------------------------
# test_network_manager.py
#
# G. Thomas
# 2018
#-------------------------------------------------------------------------------

import logging
import pytest
import time

from network_tcp_auto import NetworkManager
from .fake_client import FakeClient
from .fake_server import FakeServer

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
#-------------------------------------------------------------------------------
# Test fixtures
#-------------------------------------------------------------------------------
@pytest.fixture
def client():
    """Create a fake client object"""
    return FakeClient()

@pytest.fixture
def server():
    """Create a fake server object"""
    return FakeServer()

@pytest.fixture(name='net_man_co')
def net_manager_client_only(client):
    return NetworkManager(client)

@pytest.fixture(name='net_man_cs')
def net_manager_client_server(client, server):
    return NetworkManager(client, server)

#-------------------------------------------------------------------------------
# Init tests
#-------------------------------------------------------------------------------
def test_invalid_client_init():
    """Ensure that initialization with an invalid client fails"""
    with pytest.raises(AttributeError):
        NetworkManager(None)

def test_discovery_timeout_randomizer(net_man_co):
    """Check that discovery timeout randomizer falls within limits"""
    assert ((NetworkManager.DISCOVERY_TIMEOUT_S * (1 - NetworkManager.DISCOVERY_TIMEOUT_RAND_FACTOR)) <=
            net_man_co.discovery_timeout <=
            (NetworkManager.DISCOVERY_TIMEOUT_S * (1 + NetworkManager.DISCOVERY_TIMEOUT_RAND_FACTOR)))

#-------------------------------------------------------------------------------
# Client only tests
#-------------------------------------------------------------------------------
def test_co_search_sub_timeout(net_man_co, client, server):
    """Test that a client only implementation does not try and start a server"""
    net_man_co.search()
    time.sleep(net_man_co.discovery_timeout - 0.05)
    assert 'searching' == net_man_co.state
    assert client.is_running()
    assert not server.is_running()

def test_co_search_timeout(net_man_co, client, server):
    """Test network manager stays in search state after discovery timeout"""
    net_man_co.search()
    time.sleep(net_man_co.discovery_timeout + 0.05)
    assert 'searching' == net_man_co.state
    assert client.is_running()
    assert not server.is_running()

def test_co_connected(net_man_co, client, server):
    """Test network manager stays in search state after discovery timeout"""
    net_man_co.search()
    time.sleep(net_man_co.discovery_timeout - 0.5)
    client.connection_changed('client', 1)
    assert 'connected' == net_man_co.state

#-------------------------------------------------------------------------------
# Client server tests
#-------------------------------------------------------------------------------
def test_cs_search_timeout(net_man_cs, client, server):
    """Test network manager stays in search state after discovery timeout"""
    net_man_cs.search()
    time.sleep(net_man_cs.discovery_timeout + 0.05)
    assert 'searching' == net_man_cs.state
    assert client.is_running()
    assert server.is_running()

def test_cs_client_connected(net_man_cs, client, server):
    """Test network manager stays in search state after discovery timeout"""
    net_man_cs.search()
    time.sleep(net_man_cs.discovery_timeout + 0.5)
    client.connection_changed('client', 1)
    assert 'searching' == net_man_cs.state

def test_cs_client_server_connected(net_man_cs, client, server):
    """Test network manager stays in search state after discovery timeout"""
    net_man_cs.search()
    time.sleep(net_man_cs.discovery_timeout + 0.5)
    client.connection_changed('client', 1)
    client.connection_changed('server', 1)
    assert 'searching' == net_man_cs.state

def test_cs_connected(net_man_cs, client, server):
    """Test network manager stays in search state after discovery timeout"""
    net_man_cs.search()
    time.sleep(net_man_cs.discovery_timeout + 0.5)
    client.connection_changed('client', 1)
    client.connection_changed('server', 2)
    assert 'connected' == net_man_cs.state
