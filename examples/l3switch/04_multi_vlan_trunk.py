"""Carry two VLANs over one trunk, with an SVI gateway on the first switch."""

from nest.topology import *


sw1 = L3Switch("s1")
sw2 = L3Switch("s2")
h10 = Node("h10")
h20 = Node("h20")

s1_h10, h10_s1 = connect(sw1, h10)
s2_h20, h20_s2 = connect(sw2, h20)
trunk1, trunk2 = connect(sw1, sw2)
sw1.set_access_vlan(s1_h10, 10)
sw2.set_access_vlan(s2_h20, 20)
sw1.set_trunk_vlans(trunk1, [10, 20])
sw2.set_trunk_vlans(trunk2, [10, 20])

sw1.create_svi(10, "10.10.0.1/24")
sw1.create_svi(20, "10.20.0.1/24")
h10_s1.set_address("10.10.0.10/24")
h20_s2.set_address("10.20.0.20/24")
h10.add_route("DEFAULT", h10_s1, "10.10.0.1")
h20.add_route("DEFAULT", h20_s2, "10.20.0.1")

print(h10.ping("10.20.0.20"))
