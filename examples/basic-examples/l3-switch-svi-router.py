from nest.topology import *

sw1 = L3Switch("sw1")
sw2 = L3Switch("sw2")
h1 = Node("h1")
h2 = Node("h2")
 
# Links. For a switch, the first returned interface is its own port.
sw1_h1, h1_sw1 = connect(sw1, h1)
sw2_h2, h2_sw2 = connect(sw2, h2)
trunk1, trunk2 = connect(sw1, sw2)  # the trunk link between the switches
 
###### VLAN CONFIGURATION ######
 
# Host-facing ports are untagged access ports
sw1.set_access_vlan(sw1_h1, 10)
sw2.set_access_vlan(sw2_h2, 20)
 
# The inter-switch link is a trunk that carries the transit VLAN 100 tagged
sw1.set_trunk_vlans(trunk1, [100])
sw2.set_trunk_vlans(trunk2, [100])
 
###### SVIs (Layer 3 interface of each VLAN) ######
 
sw1.create_svi(10, "10.0.10.1/24")  # gateway of h1
sw1.create_svi(100, "10.0.100.1/24")  # transit towards sw2
svi100_sw1 = sw1.get_svi(100)
 
sw2.create_svi(20, "10.0.20.1/24")  # gateway of h2
sw2.create_svi(100, "10.0.100.2/24")  # transit towards sw1
svi100_sw2 = sw2.get_svi(100)
 
###### HOSTS ######
 
h1_sw1.set_address("10.0.10.10/24")
h2_sw2.set_address("10.0.20.10/24")
 
# Each host sends everything off-subnet to its own SVI
h1.add_route("DEFAULT", h1_sw1, "10.0.10.1")
h2.add_route("DEFAULT", h2_sw2, "10.0.20.1")

###### ROUTES BETWEEN THE SWITCHES ######

# sw1: anything for h2's subnet goes to sw2 over the trunk (VLAN 100)
sw1.add_route("10.0.20.0/24", svi100_sw1, "10.0.100.2")

# sw2: anything for h1's subnet goes to sw1 over the trunk (VLAN 100)
sw2.add_route("10.0.10.0/24", svi100_sw2, "10.0.100.1")

###### TEST ######

print(h1.ping("10.0.20.10"))   # h1 -> h2, routed sw1 -> sw2
print(h2.ping("10.0.10.10"))   # h2 -> h1, routed sw2 -> sw1