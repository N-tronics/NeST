"""Carry one access VLAN between two switches over a trunk."""

from nest.topology import *


sw1 = L3Switch("s1")
sw2 = L3Switch("s2")
h1 = Node("h1")
h2 = Node("h2")

s1_h1, h1_s1 = connect(sw1, h1)
s2_h2, h2_s2 = connect(sw2, h2)
trunk1, trunk2 = connect(sw1, sw2)
sw1.set_access_vlan(s1_h1, 30)
sw2.set_access_vlan(s2_h2, 30)
sw1.set_trunk_vlans(trunk1, [30])
sw2.set_trunk_vlans(trunk2, [30])

# Both hosts are in the same extended Layer-2 VLAN.
h1_s1.set_address("10.30.0.10/24")
h2_s2.set_address("10.30.0.20/24")

print(h1.ping("10.30.0.20"))
