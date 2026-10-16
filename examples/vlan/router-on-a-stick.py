from nest.topology import *

h1 = Node("h1")
h2 = Node("h2")

s1 = Switch("s1")

r1 = Router("r1")

eth1, ets1a = connect(h1, s1)
eth2, ets1b = connect(h2, s1)

ets1c, etr1 = connect(s1, r1)

eth1.set_address("192.168.1.2/24")
eth2.set_address("192.168.2.2/24")

s1.add_vlan_tag(ets1a, 10, True)
s1.add_vlan_tag(ets1b, 20, True)
s1.add_vlan_tag(ets1c, 10, False)
s1.add_vlan_tag(ets1c, 20, False)
s1.rem_vlan_tag(ets1a, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1b, Switch.DEFAULT_VLAN)
s1.rem_vlan_tag(ets1c, Switch.DEFAULT_VLAN)

etr1_10 = r1.create_vlan_subif(etr1, 10)
etr1_20 = r1.create_vlan_subif(etr1, 20)

etr1_10.add_address("192.168.1.1/24")
etr1_20.add_address("192.168.2.1/24")

h1.add_route("DEFAULT", eth1, etr1_10.address)
h2.add_route("DEFAULT", eth2, etr1_20.address)

h1.ping(eth2.address)
