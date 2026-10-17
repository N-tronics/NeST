# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2019-2022 NITK Surathkal

########################
# SHOULD BE RUN AS ROOT
########################
from nest.topology import *

# This program combines VLAN trunking across two switches with inter-VLAN
# routing. Hosts `h1` and `h3` are in VLAN 10 and host `h2` is in VLAN 20.
# `h1` and `h2` are on switch `s1`, while `h3` and the router `r1` are on
# switch `s2`. The two switches are joined by a trunk carrying both VLANs,
# and the router is attached to `s2` through another trunk (router on a
# stick). Two experiments are run:
#   1. `h1` pings `h2`: different VLANs, so the packets go through `r1`.
#   2. `h3` pings `h1`: same VLAN, so the packets cross the s1-s2 trunk
#      without involving the router.

################################################################################
#                           Network Topology                                   #
#                                                                              #
#   h1 -- access, VLAN 10 --+                                                  #
#   192.168.10.1/24         |                                                  #
#                           s1 ===== trunk ===== s2 -- access, VLAN 10 -- h3   #
#                           |     (VLAN 10, 20)  ||     192.168.10.2/24        #
#   h2 -- access, VLAN 20 --+                    || trunk (VLAN 10, 20)        #
#   192.168.20.1/24                              ||                            #
#                                                r1                            #
#   r1 sub-interfaces:  etr1_10 = 192.168.10.3/24  (VLAN 10)                   #
#                       etr1_20 = 192.168.20.2/24  (VLAN 20)                   #
################################################################################

# Create three hosts, `h1`, `h2` and `h3`.
h1 = Node("h1")
h2 = Node("h2")
h3 = Node("h3")

# Create two VLAN-aware switches, `s1` and `s2`.
s1 = Switch("s1")
s2 = Switch("s2")

# Create a router `r1` to route between the VLANs.
r1 = Router("r1")

# Connect the hosts to their switches. In each pair, the first returned
# interface belongs to the first node given (so for `connect(s2, h3)`,
# `ets2a` is the switch port and `eth3` is the host interface).
eth1, ets1a = connect(h1, s1)
eth2, ets1b = connect(h2, s1)
ets2a, eth3 = connect(s2, h3)

# Connect the two switches (the inter-switch trunk). `ets1c` is the port on
# `s1` and `ets2b` is the port on `s2`.
ets1c, ets2b = connect(s1, s2)

# Connect the router to `s2`. `etr1` is the router's physical interface and
# `ets2c` is the port on `s2`. This single link carries both VLANs.
etr1, ets2c = connect(r1, s2)

# Configure the VLANs on `s1` using `add_vlan_tag(port, vlan_id, access)`.
# Access ports (access=True) carry one VLAN untagged and face the hosts.
# Trunk ports (access=False) carry several VLANs with their 802.1Q tags.
s1.add_vlan_tag(ets1a, 10, True)
s1.add_vlan_tag(ets1b, 20, True)
s1.add_vlan_tag(ets1c, 10, False)
s1.add_vlan_tag(ets1c, 20, False)

# Remove the default VLAN (VLAN 1) membership that every port starts with.
s1.rem_vlan_tag(ets1a, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1b, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1c, Switch.DEFAULT_VLAN)

# Configure `s2`. `ets2a` faces `h3` (access, VLAN 10). `ets2b` is the trunk
# to `s1`, and `ets2c` is the trunk to the router. Both trunks carry
# VLAN 10 and VLAN 20.
s2.add_vlan_tag(ets2a, 10, True)
s2.add_vlan_tag(ets2b, 10, False)
s2.add_vlan_tag(ets2b, 20, False)
s2.add_vlan_tag(ets2c, 10, False)
s2.add_vlan_tag(ets2c, 20, False)

# Remove the default VLAN membership on all of `s2`'s ports.
s2.rem_vlan_tag(ets2a, Switch.DEFAULT_VLAN)
s2.rem_vlan_tag(ets2b, Switch.DEFAULT_VLAN)
s2.rem_vlan_tag(ets2c, Switch.DEFAULT_VLAN)

# Create one 802.1Q sub-interface on the router per VLAN, on top of its
# physical interface `etr1`. Each one handles the tagged traffic of its VLAN.
etr1_10 = r1.create_vlan_subif(etr1, 10)
etr1_20 = r1.create_vlan_subif(etr1, 20)

# Assign IPv4 addresses to the hosts. VLAN 10 uses 192.168.10.0/24 and
# VLAN 20 uses 192.168.20.0/24. `add_address` adds an address to the
# interface (unlike `set_address`, which replaces the existing ones).
eth1.add_address("192.168.10.1/24")
eth2.add_address("192.168.20.1/24")
eth3.add_address("192.168.10.2/24")

# Give each router sub-interface an address in its VLAN's subnet. These are
# the default gateways for the hosts in the respective VLANs.
etr1_10.add_address("192.168.10.3/24")
etr1_20.add_address("192.168.20.2/24")

# Make the router the default gateway of each host. The `add_route` API takes
# the destination ("DEFAULT" means any address), the outgoing interface and
# the next-hop address. `h1` and `h3` share VLAN 10, so they use the VLAN 10
# sub-interface; `h2` uses the VLAN 20 sub-interface.
h1.add_route("DEFAULT", eth1, etr1_10.address)
h2.add_route("DEFAULT", eth2, etr1_20.address)
h3.add_route("DEFAULT", eth3, etr1_10.address)

# `Ping` from `h1` to `h2` (different VLANs).
# Path: h1 -> s1 -> trunk -> s2 -> trunk -> r1 (etr1_10) -> routed ->
# r1 (etr1_20) -> trunk -> s2 -> trunk -> s1 -> h2.
h1.ping(eth2.address)

# `Ping` from `h3` to `h1` (same VLAN).
# Path: h3 -> s2 -> trunk -> s1 -> h1. Since both hosts are in the same
# subnet, the packets are switched directly and never reach the router.
h3.ping(eth1.address)
