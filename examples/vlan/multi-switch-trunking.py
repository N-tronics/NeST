# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2019-2022 NITK Surathkal

########################
# SHOULD BE RUN AS ROOT
########################
from nest.topology import *

# This program emulates VLANs spanning two switches connected by a trunk
# link. Hosts `h1` and `h3` are in VLAN 10, and `h2` is in VLAN 20. `h1`
# and `h2` are plugged into switch `s1`, and `h3` into switch `s2`. The
# trunk between `s1` and `s2` carries both VLANs, so `h1` and `h3` can talk
# to each other as if they were on the same switch, while `h2` stays
# isolated from them. There is no router in this topology, so VLAN 10 and
# VLAN 20 cannot reach each other at all.

###################################################################################
#                          Network Topology                                       #
#                                                                                 #
#   h1 -- access, VLAN 10 --+                                                     #
#   192.168.10.1/24         |                                                     #
#                           s1 ======= trunk ======= s2 -- access, VLAN 10 -- h3  #
#                           |       (VLAN 10, 20)           192.168.10.2/24       #
#   h2 -- access, VLAN 20 --+                                                     #
#   192.168.20.1/24                                                               #
###################################################################################

# Create three hosts, `h1`, `h2` and `h3`.
h1 = Node("h1")
h2 = Node("h2")
h3 = Node("h3")

# Create two VLAN-aware switches, `s1` and `s2`.
s1 = Switch("s1")
s2 = Switch("s2")

# Connect the hosts to their switches. In each pair, the first returned
# interface belongs to the first node given. Note the order of `s2` and
# `h3` in the third call, so there `ets2a` is the switch port and `eth3`
# is the host interface.
eth1, ets1a = connect(h1, s1)
eth2, ets1b = connect(h2, s1)
ets2a, eth3 = connect(s2, h3)

# Connect the two switches. `ets1c` is the port on `s1` and `ets2b` is the
# port on `s2`. This is the trunk link.
ets1c, ets2b = connect(s1, s2)

# Configure the VLANs on `s1` using `add_vlan_tag(port, vlan_id, access)`.
# Access ports (access=True) carry a single VLAN, untagged, and face hosts.
# Trunk ports (access=False) carry tagged frames for several VLANs.
s1.add_vlan_tag(ets1a, 10, True)
s1.add_vlan_tag(ets1b, 20, True)
s1.add_vlan_tag(ets1c, 10, False)
s1.add_vlan_tag(ets1c, 20, False)

# Remove the default VLAN (VLAN 1) membership that every port starts with.
s1.rem_vlan_tag(ets1a, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1b, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1c, Switch.DEFAULT_VLAN)

# Configure `s2`. The port towards `h3` is an access port in VLAN 10, and
# the port towards `s1` is a trunk. The trunk must allow the same VLANs as
# the other end (10 and 20), otherwise frames for the missing VLAN are
# dropped when they arrive at this switch.
s2.add_vlan_tag(ets2a, 10, True)
s2.add_vlan_tag(ets2b, 10, False)
s2.add_vlan_tag(ets2b, 20, False)

# Remove the default VLAN membership on `s2`'s ports too.
s2.rem_vlan_tag(ets2a, Switch.DEFAULT_VLAN)
s2.rem_vlan_tag(ets2b, Switch.DEFAULT_VLAN)

# Assign IPv4 addresses to the hosts. The addresses are chosen so that each
# VLAN has its own subnet: 192.168.10.0/24 for VLAN 10 and 192.168.20.0/24
# for VLAN 20. `add_address` adds an address to the interface (unlike
# `set_address`, which replaces the existing ones).
eth1.add_address("192.168.10.1/24")
eth2.add_address("192.168.20.1/24")
eth3.add_address("192.168.10.2/24")

# `Ping` from `h1` to `h2`.
# `h1` (VLAN 10) and `h2` (VLAN 20) are in different VLANs and different
# subnets, and there is no router or default route, so these pings are
# expected to FAIL. This demonstrates VLAN isolation.
# To see the trunk working, ping `h3` instead: h1.ping(eth3.address)
h1.ping(eth2.address)
