# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 NITK Surathkal

########################
# SHOULD BE RUN AS ROOT
########################

"""Two VLANs, two SVIs, two hosts, and one router.

The h1-to-h2 ping is an inter-VLAN routing test. It must pass through the
L3 switch SVIs; a Layer 2 bridge alone cannot provide this connectivity.
"""

from nest.topology import L3Switch, Node, Router, connect


######################################################################
#                          Network Topology                          #
#                                                                    #
# VLAN 10: 10.10.10.0/24       VLAN 20: 10.20.20.0/24               #
#                                                                    #
# h1 ------------------ s1 ------------------ h2                   #
# 10.10.10.11/24       |                      10.20.20.12/24       #
#                       |                                           #
#                 SVI 10: 10.10.10.1/24                            #
#                 SVI 20: 10.20.20.1/24                            #
#                       |                                           #
#                       +---------------------- r1                  #
#                                              10.20.20.254/24       #
#                                                                    #
# h1 is in VLAN 10 and h2 is in VLAN 20.                           #
# h1 -> h2 verifies inter-VLAN routing on s1.                       #
######################################################################

# Create two hosts, one Layer 3 switch, and one router.
h1 = Node("h1")
h2 = Node("h2")
s1 = L3Switch("s1")
r1 = Router("r1")

# Connect the hosts and router to the L3 switch.
eth1, s1_h1 = connect(h1, s1)
eth2, s1_h2 = connect(h2, s1)
s1_r1, etr1 = connect(s1, r1)

# Create one SVI for each routed VLAN.
svi10 = s1.create_svi(10, address="10.10.10.1/24")
svi20 = s1.create_svi(20, address="10.20.20.1/24")

# Configure the host ports as untagged access ports in different VLANs.
s1.set_access_vlan(s1_h1, 10)
s1.set_access_vlan(s1_h2, 20)

# Attach the router to VLAN 20.
s1.set_access_vlan(s1_r1, 20)

# Assign addresses to the hosts and router interface.
eth1.set_address("10.10.10.11/24")
eth2.set_address("10.20.20.12/24")
etr1.set_address("10.20.20.254/24")

# Configure each host to use its VLAN SVI as the default gateway.
h1.add_route("DEFAULT", eth1, svi10.address)
h2.add_route("DEFAULT", eth2, svi20.address)

# Same-VLAN gateway checks.
assert h1.ping(svi10.address, packets=10, verbose=1)
assert h2.ping(svi20.address, packets=10, verbose=1)

# The actual inter-VLAN routing test: VLAN 10 -> SVI 10 -> SVI 20 -> VLAN 20.
assert h1.ping(eth2.address, packets=1, verbose=1)

# Confirm VLAN 20 can also reach the router on its local VLAN.
assert h2.ping(etr1.address, packets=1, verbose=1)

print("INTER-VLAN ROUTING TEST PASSED: h1 (VLAN 10) reached h2 (VLAN 20)")
