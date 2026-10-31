"""Route through three L3 switches using two transit VLANs."""

from nest.topology import *


s1 = L3Switch("s1")
s2 = L3Switch("s2")
s3 = L3Switch("s3")
h1 = Node("h1")
h3 = Node("h3")

s1_h1, h1_s1 = connect(s1, h1)
s3_h3, h3_s3 = connect(s3, h3)
s1_s2, s2_s1 = connect(s1, s2)
s2_s3, s3_s2 = connect(s2, s3)

s1.set_access_vlan(s1_h1, 10)
s3.set_access_vlan(s3_h3, 30)
s1.set_trunk_vlans(s1_s2, [101])
s2.set_trunk_vlans(s2_s1, [101])
s2.set_trunk_vlans(s2_s3, [102])
s3.set_trunk_vlans(s3_s2, [102])

s1.create_svi(10, "10.10.0.1/24")
s1.create_svi(101, "10.101.0.1/30")
s2.create_svi(101, "10.101.0.2/30")
s2.create_svi(102, "10.102.0.1/30")
s3.create_svi(102, "10.102.0.2/30")
s3.create_svi(30, "10.30.0.1/24")

s1_transit = s1.get_svi(101)
s2_transit1 = s2.get_svi(101)
s2_transit2 = s2.get_svi(102)
s3_transit = s3.get_svi(102)

h1_s1.set_address("10.10.0.10/24")
h3_s3.set_address("10.30.0.30/24")
h1.add_route("DEFAULT", h1_s1, "10.10.0.1")
h3.add_route("DEFAULT", h3_s3, "10.30.0.1")
s1.add_route("10.30.0.0/24", s1_transit, "10.101.0.2")
s2.add_route("10.10.0.0/24", s2_transit1, "10.101.0.1")
s2.add_route("10.30.0.0/24", s2_transit2, "10.102.0.2")
s3.add_route("10.10.0.0/24", s3_transit, "10.102.0.1")

print(h1.ping("10.30.0.30"))
