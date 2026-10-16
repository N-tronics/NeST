# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 NITK Surathkal

"""Layer 3 switch and switched virtual interface (SVI) support."""

from nest import engine
from nest.input_validator import input_validator
from nest.topology.device import Device
from nest.topology.interface import BaseInterface
from nest.topology_map import TopologyMap

from .switch import Switch


class _SVIDevice(Device):
    """Linux VLAN device used by :class:`SVI`."""

    def __init__(self, name, node_id, parent_id, vlan_id):
        super().__init__(name, node_id)
        engine.exec_subprocess(
            f"ip netns exec {node_id} ip link add link {parent_id} "
            f"name {self.id} type vlan id {vlan_id}"
        )
        engine.set_interface_mode(node_id, self.id, "up")


class SVI(BaseInterface):
    """A switched virtual interface attached to an :class:`L3Switch`.

    An SVI is a Linux VLAN interface on the switch bridge. It supports the
    complete ``BaseInterface`` API, including IPv4/IPv6 addresses, MTU,
    qdiscs, packet operations, and interface state changes.
    """

    @input_validator
    def __init__(self, switch: "L3Switch", vlan_id: int, name: str):
        self._switch = switch
        self._vlan_id = vlan_id
        super().__init__(name, _SVIDevice(name, switch.id, switch.id, vlan_id))

    @property
    def switch(self):
        """The L3 switch that owns this SVI."""

        return self._switch

    @property
    def vlan_id(self):
        """The 802.1Q VLAN identifier of this SVI."""

        return self._vlan_id

    def delete(self):
        """Delete this SVI from its switch."""

        return self._switch.delete_svi(self._vlan_id)

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r}, vlan_id={self.vlan_id})"


class L3Switch(Switch):
    """A Layer 3 switch with bridge-backed SVIs.

    The inherited bridge is the native, untagged SVI and remains available as
    ``switch.svi`` for compatibility with the existing switch API. Additional
    VLAN SVIs are created with :meth:`create_svi`. Ports can be assigned to
    access VLANs or configured as trunks with :meth:`set_access_vlan` and
    :meth:`set_trunk_vlans`.
    """

    @input_validator
    def __init__(self, name: str, ipv4: bool = True, ipv6: bool = True):
        self._svis = {}
        super().__init__(name)
        self.enable_ip_forwarding(ipv4=ipv4, ipv6=ipv6)

    @property
    def svi(self):
        """Return the switch bridge, which is the native SVI."""

        return self

    @property
    def svis(self):
        """Return a copy of the VLAN ID to SVI mapping."""

        return self._svis.copy()

    @staticmethod
    def _validate_vlan_id(vlan_id):
        if isinstance(vlan_id, bool) or not isinstance(vlan_id, int):
            raise TypeError("vlan_id must be an integer")
        if not 1 <= vlan_id <= 4094:
            raise ValueError("vlan_id must be between 1 and 4094")

    def _enable_vlan_filtering(self):
        engine.exec_subprocess(
            f"ip netns exec {self.id} ip link set dev {self.id} "
            "type bridge vlan_filtering 1"
        )

    def _add_bridge_vlan(self, vlan_id):
        """Allow a VLAN on the bridge device itself (the SVI side)."""

        self._validate_vlan_id(vlan_id)
        engine.exec_subprocess(
            f"ip netns exec {self.id} bridge vlan add dev {self.id} "
            f"vid {vlan_id} self"
        )

    @input_validator
    def create_svi(self, vlan_id: int, address=None, name: str = ""):
        """Create and return an SVI for ``vlan_id``.

        ``address`` may be one address or a list of IPv4/IPv6 addresses. The
        optional ``name`` is the user-visible Linux interface name. If omitted,
        a stable name based on the switch name and VLAN ID is used.
        """

        self._validate_vlan_id(vlan_id)
        if vlan_id in self._svis:
            raise ValueError(f"An SVI for VLAN {vlan_id} already exists")

        if name == "":
            name = f"{self.name}-svi{vlan_id}"

        self._enable_vlan_filtering()
        self._add_bridge_vlan(vlan_id)
        svi = SVI(self, vlan_id, name)
        self._svis[vlan_id] = svi
        self._interfaces.append(svi)

        if address is not None:
            svi.set_address(address)
        return svi

    # Alias used by callers that prefer an imperative API.
    add_svi = create_svi

    @input_validator
    def get_svi(self, vlan_id: int):
        """Return the SVI for ``vlan_id`` or ``None`` if it does not exist."""

        self._validate_vlan_id(vlan_id)
        return self._svis.get(vlan_id)

    @input_validator
    def delete_svi(self, vlan_id: int):
        """Delete the SVI for ``vlan_id`` and return it."""

        self._validate_vlan_id(vlan_id)
        svi = self._svis.pop(vlan_id, None)
        if svi is None:
            raise ValueError(f"No SVI exists for VLAN {vlan_id}")

        engine.exec_subprocess(
            f"ip netns exec {self.id} ip link delete {svi.id}"
        )
        self._interfaces.remove(svi)
        TopologyMap.delete_device(self.id, svi.id)
        return svi

    def _validate_port(self, interface):
        if not isinstance(interface, BaseInterface):
            raise TypeError("interface must be a BaseInterface")
        if interface.node_id != self.id:
            raise ValueError("interface must belong to this L3 switch")
        if isinstance(interface, SVI):
            raise ValueError("an SVI cannot be configured as a bridge port")

    def _bridge_vlan(self, interface, vlan_id, *flags):
        self._validate_vlan_id(vlan_id)
        self._validate_port(interface)
        suffix = " ".join(flags)
        engine.exec_subprocess(
            f"ip netns exec {self.id} bridge vlan add dev {interface.id} "
            f"vid {vlan_id} {suffix}".rstrip()
        )

    @input_validator
    def set_access_vlan(self, interface: BaseInterface, vlan_id: int):
        """Make a switch port an untagged access port for ``vlan_id``."""

        self._enable_vlan_filtering()
        self._validate_port(interface)
        engine.exec_subprocess(
            f"ip netns exec {self.id} bridge vlan del dev {interface.id} vid 1"
        )
        self._bridge_vlan(interface, vlan_id, "pvid", "untagged")
        return interface

    @input_validator
    def set_trunk_vlans(self, interface: BaseInterface, vlan_ids: list):
        """Allow tagged ``vlan_ids`` on a switch port."""

        self._enable_vlan_filtering()
        self._validate_port(interface)
        if not vlan_ids:
            raise ValueError("vlan_ids must contain at least one VLAN")
        for vlan_id in vlan_ids:
            self._bridge_vlan(interface, vlan_id)
        return interface

    @input_validator
    def remove_port_vlan(self, interface: BaseInterface, vlan_id: int):
        """Remove a VLAN from a switch port."""

        self._validate_vlan_id(vlan_id)
        self._validate_port(interface)
        engine.exec_subprocess(
            f"ip netns exec {self.id} bridge vlan del dev {interface.id} vid {vlan_id}"
        )
        return interface
