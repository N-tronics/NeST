# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 NITK Surathkal

"""Layer 3 switch and switched virtual interface support."""

from typing import TYPE_CHECKING

from nest import config, engine
from nest.input_validator import input_validator
from nest.topology.device.vlan import validate_vlan_id
from nest.topology.interface import BaseInterface
from nest.topology.interface.svi import SVI
from nest.topology_map import TopologyMap

from .switch import Switch
from nest.routing.l3switch import L3RoutingNode

if TYPE_CHECKING:  # pragma: no cover
    from nest.routing.routing_helper import RoutingHelper


class L3Switch(Switch):
    """A bridge-backed Layer 3 switch with VLAN SVIs."""

    @input_validator
    def __init__(self, name: str, ipv4: bool = True, ipv6: bool = True):
        self._svis = {}
        super().__init__(name)
        self.enable_ip_forwarding(ipv4=ipv4, ipv6=ipv6)

    @property
    def svi(self):
        """Return the bridge representing the native VLAN 1 SVI."""
        return self

    @property
    def svis(self):
        """Return a copy of the VLAN ID to SVI mapping."""
        return self._svis.copy()

    _validate_vlan_id = staticmethod(validate_vlan_id)

    def _validate_port(self, interface):
        if not isinstance(interface, BaseInterface):
            raise TypeError("interface must be a BaseInterface")
        if interface.node_id != self.id:
            raise ValueError("interface must belong to this L3 switch")
        if interface is self or isinstance(interface, SVI):
            raise ValueError("the bridge and SVIs cannot be configured as ports")

    @input_validator
    def create_svi(self, vlan_id: int, address=None, name: str = ""):
        """Create and return an SVI for ``vlan_id``."""
        self._validate_vlan_id(vlan_id)
        if vlan_id == 1:
            raise ValueError(
                "VLAN 1 is represented by the switch bridge; "
                "assign its address directly to the switch"
            )
        if vlan_id in self._svis:
            raise ValueError(f"An SVI for VLAN {vlan_id} already exists")
        name = name or f"{self.name}-svi{vlan_id}"

        self._device.enable_vlan_filtering()
        self._device.add_vlan(vlan_id)
        try:
            svi = SVI(self, vlan_id, name)
            if address is not None:
                svi.set_address(address)
        except Exception:
            if "svi" in locals():
                engine.delete_interface(self.id, svi.id)
                if svi.id in TopologyMap.get_devices(self.id):
                    TopologyMap.delete_device(self.id, svi.id)
            engine.delete_bridge_vlan(
                self.id, self._device.id, vlan_id, self_port=True
            )
            raise

        self._svis[vlan_id] = svi
        self._interfaces.append(svi)
        return svi

    add_svi = create_svi

    @input_validator
    def get_svi(self, vlan_id: int):
        """Return the SVI for ``vlan_id`` or ``None`` if absent."""
        self._validate_vlan_id(vlan_id)
        return self._svis.get(vlan_id)

    @input_validator
    def delete_svi(self, vlan_id: int):
        """Delete and return the SVI for ``vlan_id``."""
        self._validate_vlan_id(vlan_id)
        svi = self._svis.get(vlan_id)
        if svi is None:
            raise ValueError(f"No SVI exists for VLAN {vlan_id}")

        engine.delete_bridge_vlan(
            self.id, self._device.id, vlan_id, self_port=True, check=True
        )
        engine.delete_interface(self.id, svi.id, check=True)
        del self._svis[vlan_id]
        self._interfaces.remove(svi)
        TopologyMap.delete_device(self.id, svi.id)
        svi._device._ipv4_address = []  # pylint: disable=protected-access
        svi._device._ipv6_address = []  # pylint: disable=protected-access
        return svi

    @input_validator
    def set_access_vlan(self, interface: BaseInterface, vlan_id: int):
        """Make a switch port an untagged access port."""
        self._validate_vlan_id(vlan_id)
        self._validate_port(interface)
        return self._device.set_access_vlan(interface, vlan_id)

    @input_validator
    def set_trunk_vlans(
        self, interface: BaseInterface, vlan_ids: list, native_vlan: int = 1
    ):
        """Allow tagged ``vlan_ids`` on a switch port."""
        self._validate_port(interface)
        self._validate_vlan_id(native_vlan)
        for vlan_id in vlan_ids:
            self._validate_vlan_id(vlan_id)
        return self._device.set_trunk_vlans(interface, vlan_ids, native_vlan)

    @input_validator
    def remove_port_vlan(self, interface: BaseInterface, vlan_id: int):
        """Remove a VLAN from a switch port."""
        self._validate_vlan_id(vlan_id)
        self._validate_port(interface)
        return self._device.remove_port_vlan(interface, vlan_id)

    def enable_routing(self, routing_protocol: "RoutingHelper"):
        """Run dynamic routing daemons on addressed switch interfaces."""
        from nest.routing.routing_helper import RoutingHelper

        if not isinstance(routing_protocol, RoutingHelper):
            raise TypeError("routing_protocol must be a RoutingHelper instance")
        if routing_protocol.protocol == "static":
            raise NotImplementedError(
                "Static routing on an L3Switch is not supported by the "
                "current static-routing implementation"
            )
        if config.get_value("routing_suite") == "bird":
            raise NotImplementedError(
                "Dynamic routing on an L3Switch needs the 'frr' or 'quagga' "
                "routing suite, not 'bird'"
            )

        with TopologyMap.lock:
            routers = TopologyMap.get_routers()
            hosts = TopologyMap.get_hosts()
            if self not in routers:
                routers.append(self)
            while self in hosts:
                hosts.remove(self)
        while self in routing_protocol.hosts:
            routing_protocol.hosts.remove(self)

        view = next(
            (
                router
                for router in routing_protocol.routers
                if isinstance(router, L3RoutingNode) and router.switch is self
            ),
            None,
        )
        view = view or L3RoutingNode(self, routing_protocol)
        routing_protocol.routers[:] = [
            view if router is self else router for router in routing_protocol.routers
        ]
        if view not in routing_protocol.routers:
            routing_protocol.routers.append(view)
        return routing_protocol
