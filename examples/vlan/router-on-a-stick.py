# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2019-2022 NITK Surathkal

########################
# SHOULD BE RUN AS ROOT
########################
from nest.topology import *

# This program emulates inter-VLAN routing using the "router on a stick"
# technique. Two hosts `h1` and `h2` are connected to a single switch `s1`,
# but they belong to different VLANs (10 and 20), so the switch alone cannot
# forward traffic between them. A router `r1` is connected to the switch
# through ONE physical link (the "stick") that carries both VLANs. The router
# has one virtual sub-interface per VLAN and routes packets between them.
# Five ping packets are sent from `h1` to `h2`, and the success/failure of
# these packets is reported.

#######################################################################
#                          Network Topology                           #
#                                                                     #
#   h1 -------------- access, VLAN 10 --+                             #
#   192.168.1.2/24                      |                             #
#                                       s1 ====== trunk ====== r1     #
#                                       |      (VLAN 10, 20)          #
#   h2 -------------- access, VLAN 20 --+                             #
#   192.168.2.2/24                                                    #
#                                                                     #
#   r1 sub-interfaces:  etr1_10 = 192.168.1.1/24  (VLAN 10)           #
#                       etr1_20 = 192.168.2.1/24  (VLAN 20)           #
#######################################################################

# Create two hosts, `h1` and `h2`.
h1 = Node("h1")
h2 = Node("h2")

# Create a switch `s1`. A `Switch` is a VLAN-aware bridge, so VLAN
# membership can be configured on each of its ports.
s1 = Switch("s1")
s1.enable_vlan_filtering()

# Create a router `r1`. A `Router` is a node that forwards IP packets
# between its interfaces.
r1 = Router("r1")

# Connect each host to the switch. `connect` returns the interface at each
# end of the link, in the order the nodes were given. So `eth1` is on `h1`
# and `ets1a` is the switch port it is plugged into (likewise for `h2`).
eth1, ets1a = connect(h1, s1)
eth2, ets1b = connect(h2, s1)

# Connect the switch to the router. `ets1c` is the switch port, and `etr1`
# is the router's physical interface. This single link will carry both VLANs.
ets1c, etr1 = connect(s1, r1)

# Assign IPv4 addresses to the hosts. The hosts are in different subnets,
# one per VLAN, which is why they need a router to talk to each other.
eth1.set_address("192.168.1.2/24")
eth2.set_address("192.168.2.2/24")

# Configure the VLANs on the switch with `add_vlan_tag(port, vlan_id, access)`.
#
# Access ports (access=True) belong to exactly one VLAN. Frames leave the
# port untagged, and untagged frames arriving on it are placed in that VLAN.
# Hosts are plugged into access ports and are unaware of VLANs.
s1.add_vlan_tag(ets1a, 10, True)
s1.add_vlan_tag(ets1b, 20, True)

# Trunk ports (access=False) can carry several VLANs. Frames keep their
# 802.1Q tag so the receiver can tell which VLAN they belong to. The port
# facing the router carries both VLAN 10 and VLAN 20.
s1.add_vlan_tag(ets1c, 10, False)
s1.add_vlan_tag(ets1c, 20, False)

# By default every switch port is a member of VLAN 1 (the default VLAN).
# Remove that membership so the ports only belong to the VLANs set above.
s1.rem_vlan_tag(ets1a, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1b, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1c, Switch.DEFAULT_VLAN)

# Create one 802.1Q sub-interface on the router per VLAN, on top of its
# physical interface `etr1`. Each sub-interface sends and receives frames
# tagged with its own VLAN ID, so the router sees the "stick" as two
# separate links.
etr1_10 = r1.create_vlan_subif(etr1, 10)
etr1_20 = r1.create_vlan_subif(etr1, 20)

# Give each sub-interface an address in its VLAN's subnet. These act as the
# default gateways for the hosts in the respective VLANs.
etr1_10.add_address("192.168.1.1/24")
etr1_20.add_address("192.168.2.1/24")

# Make the router the default gateway of each host. The `add_route` API takes
# the destination ("DEFAULT" means any address), the outgoing interface and
# the next-hop address.
h1.add_route("DEFAULT", eth1, etr1_10.address)
h2.add_route("DEFAULT", eth2, etr1_20.address)

# `Ping` from `h1` to `h2`.
# The packet path is: h1 -> s1 (VLAN 10) -> trunk -> r1 (etr1_10) -> routed
# -> r1 (etr1_20) -> trunk -> s1 (VLAN 20) -> h2. The reply takes the
# reverse path.
h1.ping(eth2.address)
