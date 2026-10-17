# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 NITK Surathkal

########################
# SHOULD BE RUN AS ROOT
########################
from nest.topology import *
from nest.topology.l3switch import L3Switch

# Create hosts and the Layer 3 switch
h1 = Node("h1")
h2 = Node("h2")
s1 = L3Switch("s1")

# Connect hosts to the switch using NeST's connect helper
h1_eth1, s1_eth1 = connect(h1, s1)
h2_eth1, s1_eth2 = connect(h2, s1)

# Assign host IP addresses and set their SVI gateways as default routes
h1_eth1.set_address("10.0.10.1/24")
h1.add_route("DEFAULT", h1_eth1, "10.0.10.254")

h2_eth1.set_address("10.0.20.1/24")
h2.add_route("DEFAULT", h2_eth1, "10.0.20.254")

# Configure SVIs and assign access ports on the switch
s1.create_svi(vlan_id=10, address="10.0.10.254/24")
s1.create_svi(vlan_id=20, address="10.0.20.254/24")

s1.set_access_vlan(s1_eth1, 10)
s1.set_access_vlan(s1_eth2, 20)

# Ping h2 from h1 using the native NeST API
h1.ping(h2_eth1.address)