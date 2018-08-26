# auto-tcp-network
The auto-tcp-network is a self healing client-server network that uses zeroconf
networking to find nodes of the correct service type.
## network manager
The network manager is responsible for providing a simple application interface
no the consuming application. It provides,
 * an event that broadcasts the state of the connection
 * an event that broadcasts received data
 * a method for sending data, raises an error if data is sent while not
 connected
The connection mechanism operates according to the following state machine:

![network manager connection state diagram](https://github.com/geoff-coppertop/python-auto-tcp-network/network_manager_state_diagram.png)
## client

## server