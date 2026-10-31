"""Route traffic between two VLANs on a single L3 switch."""

from nest.topology import *


switch = L3Switch("sw")
h10 = Node("h10")
h20 = Node("h20")

sw_h10, h10_sw = connect(switch, h10)
sw_h20, h20_sw = connect(switch, h20)
switch.set_access_vlan(sw_h10, 10)
switch.set_access_vlan(sw_h20, 20)

switch.create_svi(10, "10.10.0.1/24")
switch.create_svi(20, "10.20.0.1/24")
h10_sw.set_address("10.10.0.10/24")
h20_sw.set_address("10.20.0.10/24")
h10.add_route("DEFAULT", h10_sw, "10.10.0.1")
h20.add_route("DEFAULT", h20_sw, "10.20.0.1")

print(h10.ping("10.20.0.10"))
