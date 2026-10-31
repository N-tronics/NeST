# L3 switch examples

These examples exercise the VLAN, SVI, access-port, trunk-port, and routing
APIs provided by `nest.topology.L3Switch`.

Run them from the repository's normal NeST environment with the required
Linux network namespace privileges. The OSPF example additionally requires a
working FRR or Quagga installation.

They use the same import style as the existing basic examples:

```bash
sudo python3 01_single_switch_inter_vlan.py
```

Examples:

1. `01_single_switch_inter_vlan.py` — inter-VLAN routing on one switch.
2. `02_two_switches_routed_transit.py` — two switches connected through a
   routed transit VLAN.
3. `03_vlan_extension_over_trunk.py` — one VLAN extended across a trunk.
4. `04_multi_vlan_trunk.py` — two VLANs carried over one trunk.
5. `05_three_switch_routed_chain.py` — three L3 switches with two transit
   VLANs.
6. `06_ospf_over_svis.py` — dynamic routing over SVI transit links.
