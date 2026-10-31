"""Route between host VLANs through a dedicated transit VLAN."""

from nest.topology import *


sw1 = L3Switch("s1")
sw2 = L3Switch("s2")
h1 = Node("h1")
h2 = Node("h2")

s1_h1, h1_s1 = connect(sw1, h1)
s2_h2, h2_s2 = connect(sw2, h2)
trunk1, trunk2 = connect(sw1, sw2)
sw1.set_access_vlan(s1_h1, 10)
sw2.set_access_vlan(s2_h2, 20)
sw1.set_trunk_vlans(trunk1, [100])
sw2.set_trunk_vlans(trunk2, [100])

sw1.create_svi(10, "10.10.0.1/24")
sw1.create_svi(100, "10.100.0.1/30")
sw2.create_svi(20, "10.20.0.1/24")
sw2.create_svi(100, "10.100.0.2/30")

transit1 = sw1.get_svi(100)
transit2 = sw2.get_svi(100)

h1_s1.set_address("10.10.0.10/24")
h2_s2.set_address("10.20.0.10/24")
h1.add_route("DEFAULT", h1_s1, "10.10.0.1")
h2.add_route("DEFAULT", h2_s2, "10.20.0.1")
sw1.add_route("10.20.0.0/24", transit1, "10.100.0.2")
sw2.add_route("10.10.0.0/24", transit2, "10.100.0.1")

print(h1.ping("10.20.0.10"))
