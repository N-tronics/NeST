# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2026 NITK Surathkal

"""Layer 3 switch and switched virtual interface (SVI) support."""

from typing import TYPE_CHECKING

from nest import config, engine
from nest.input_validator import input_validator
from nest.topology.device import Device
from nest.topology.interface import BaseInterface
from nest.topology_map import TopologyMap

from .switch import Switch

if TYPE_CHECKING:  # pragma: no cover
    from nest.routing.routing_helper import RoutingHelper


class _SVIDevice(Device):
    """Linux VLAN device used by :class:`SVI`."""

    def __init__(self, name, node_id, parent_id, vlan_id):
        super().__init__(name, node_id)
        exit_code = engine.exec_subprocess(
            f"ip netns exec {node_id} ip link add link {parent_id} "
            f"name {self.id} type vlan id {vlan_id}"
        )
        if exit_code != 0:
            # Device.__init__ already registered this device; undo that so no
            # ghost entry is left in the TopologyMap.
            TopologyMap.delete_device(node_id, self.id)
            raise RuntimeError(
                f"Could not create VLAN interface {name} (VLAN {vlan_id}) "
                f"on {parent_id}; exit code {exit_code}"
            )
        engine.set_interface_mode(node_id, self.id, "up")


class _L3RoutingNode:
    """Routing view of an :class:`L3Switch`.

    ``RoutingHelper`` hands ``node.interfaces`` straight to zebra and the
    routing daemons, and those assume that *every* interface has an address
    (they index ``get_address(...)[0]``). A switch's own ``interfaces`` also
    contain the unaddressed bridge ports, so the real switch cannot be given
    to the helper. This view exposes only the Layer 3 interfaces: the bridge
    itself (the native VLAN 1 SVI) and every VLAN SVI that has an address of
    the family being routed.

    The list is computed when the daemons are started, so SVIs created or
    addressed after ``enable_routing()`` are still picked up.
    """

    def __init__(self, switch, routing_helper):
        self._switch = switch
        self._helper = routing_helper

    @property
    def switch(self):
        """The :class:`L3Switch` this view belongs to."""

        return self._switch

    @property
    def id(self):
        """Namespace id of the switch (where the daemons run)."""

        return self._switch.id

    @property
    def name(self):
        """User given name of the switch."""

        return self._switch.name

    @property
    def interfaces(self):
        """Addressed Layer 3 interfaces of the switch."""

        ipv6 = self._helper.ipv6_routing
        candidates = [self._switch, *self._switch.svis.values()]
        routed = [i for i in candidates if i.get_address(not ipv6, ipv6, True)]
        if not routed:
            raise ValueError(
                f"{self._switch.name} has no {'IPv6' if ipv6 else 'IPv4'}-addressed "
                "SVI (or bridge address) to run routing on"
            )
        return routed

    def __repr__(self):
        return f"{self.__class__.__name__}({self._switch.name!r})"


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

    def _run(self, cmd: str):
        """Run ``cmd`` and raise if it fails.

        ``engine.exec_subprocess`` only returns the exit code, so without this
        check a failed kernel command would go unnoticed and the Python-side
        port state would drift away from the kernel state.
        """

        exit_code = engine.exec_subprocess(cmd)
        if exit_code != 0:
            raise RuntimeError(f"Command failed with exit code {exit_code}: {cmd}")

    def _enable_vlan_filtering(self):
        self._run(
            f"ip netns exec {self.id} ip link set dev {self.id} "
            "type bridge vlan_filtering 1"
        )

    def _add_bridge_vlan(self, vlan_id):
        """Allow a VLAN on the bridge device itself (the SVI side)."""

        self._validate_vlan_id(vlan_id)
        self._run(
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
        try:
            svi = SVI(self, vlan_id, name)
        except Exception:
            # Do not leave a phantom bridge VLAN entry behind.
            engine.exec_subprocess(
                f"ip netns exec {self.id} bridge vlan del dev {self.id} "
                f"vid {vlan_id} self"
            )
            raise
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
        svi = self._svis.get(vlan_id)
        if svi is None:
            raise ValueError(f"No SVI exists for VLAN {vlan_id}")

        # Remove the Layer 2 bridge filter entry first so no phantom VLAN
        # replication rule is left behind, then delete the Layer 3 interface.
        self._run(
            f"ip netns exec {self.id} bridge vlan del dev {self.id} "
            f"vid {vlan_id} self"
        )
        self._run(f"ip netns exec {self.id} ip link delete {svi.id}")
        # Update Python state only after the kernel commands succeeded.
        del self._svis[vlan_id]
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
        self._run(
            f"ip netns exec {self.id} bridge vlan add dev {interface.id} "
            f"vid {vlan_id} {suffix}".rstrip()
        )

    @staticmethod
    def _init_port_state(interface):
        """Lazily attach VLAN tracking state to a switch port."""

        if not hasattr(interface, "_configured_vlans"):
            interface._configured_vlans = set()  # pylint: disable=protected-access
            interface._port_mode = None  # pylint: disable=protected-access

    def _rollback_port(self, interface, vlan_ids):
        """Best-effort undo of a partially applied port configuration.

        Exit codes are intentionally ignored: the VLANs may not all have been
        added yet. The port is returned to the default VLAN 1 state.
        """

        for vlan_id in vlan_ids:
            engine.exec_subprocess(
                f"ip netns exec {self.id} bridge vlan del dev {interface.id} "
                f"vid {vlan_id}"
            )
        engine.exec_subprocess(
            f"ip netns exec {self.id} bridge vlan add dev {interface.id} "
            "vid 1 pvid untagged"
        )

    @input_validator
    def set_access_vlan(self, interface: BaseInterface, vlan_id: int):
        """Make a switch port an untagged access port for ``vlan_id``."""

        self._init_port_state(interface)
        self._validate_vlan_id(vlan_id)
        self._validate_port(interface)
        if interface._port_mode == "trunk":  # pylint: disable=protected-access
            raise ValueError(
                f"Port {interface.name} is already configured as a trunk port; "
                "call remove_port_vlan() to unlock it before making it an "
                "access port"
            )
        if interface._configured_vlans:  # pylint: disable=protected-access
            raise ValueError("Port already has VLANs configured. Remove them first.")

        self._enable_vlan_filtering()
        # Drop the default VLAN 1 membership. The strict check above guarantees
        # the port has no other configured VLANs, so nothing can stack.
        engine.exec_subprocess(
            f"ip netns exec {self.id} bridge vlan del dev {interface.id} vid 1"
        )
        try:
            self._bridge_vlan(interface, vlan_id, "pvid", "untagged")
        except Exception:
            # VLAN 1 was already removed above; do not leave the port dead.
            self._rollback_port(interface, [vlan_id])
            raise
        interface._configured_vlans.add(vlan_id)  # pylint: disable=protected-access
        interface._port_mode = "access"  # pylint: disable=protected-access
        return interface

    @input_validator
    def set_trunk_vlans(
        self, interface: BaseInterface, vlan_ids: list, native_vlan: int = 1
    ):
        """Allow tagged ``vlan_ids`` on a switch port.

        Untagged ingress traffic is placed in ``native_vlan`` (PVID) and is
        sent out untagged. ``native_vlan`` is not tagged even if it also
        appears in ``vlan_ids``.
        """

        self._init_port_state(interface)
        self._validate_port(interface)
        if interface._port_mode == "access":  # pylint: disable=protected-access
            raise ValueError(
                f"Port {interface.name} is already configured as an access "
                "port; call remove_port_vlan() to unlock it before making it "
                "a trunk port"
            )
        if getattr(interface, "_configured_vlans", None):
            raise ValueError(
                "Port already has VLANs configured. Call remove_port_vlan first."
            )
        if not vlan_ids:
            raise ValueError("vlan_ids must contain at least one VLAN")
        self._validate_vlan_id(native_vlan)
        for vlan_id in vlan_ids:
            self._validate_vlan_id(vlan_id)

        self._enable_vlan_filtering()
        wanted = {native_vlan, *vlan_ids}
        if 1 not in wanted:
            # Same as access ports: the default VLAN 1 membership must not
            # leak onto a trunk that does not carry VLAN 1. The port may no
            # longer be a member, so the exit code is deliberately ignored.
            engine.exec_subprocess(
                f"ip netns exec {self.id} bridge vlan del dev {interface.id} vid 1"
            )
        try:
            self._bridge_vlan(interface, native_vlan, "pvid", "untagged")
            for vlan_id in vlan_ids:
                if vlan_id == native_vlan:
                    continue
                self._bridge_vlan(interface, vlan_id)
        except Exception:
            # Undo whatever was applied so the kernel matches the (unchanged)
            # Python state.
            self._rollback_port(interface, wanted - {1})
            raise
        interface._configured_vlans.update(vlan_ids)  # pylint: disable=protected-access
        interface._configured_vlans.add(native_vlan)  # pylint: disable=protected-access
        interface._port_mode = "trunk"  # pylint: disable=protected-access
        return interface

    @input_validator
    def remove_port_vlan(self, interface: BaseInterface, vlan_id: int):
        """Remove a VLAN from a switch port."""

        self._init_port_state(interface)
        self._validate_vlan_id(vlan_id)
        self._validate_port(interface)
        configured = interface._configured_vlans  # pylint: disable=protected-access
        if vlan_id not in configured:
            raise ValueError(
                f"VLAN {vlan_id} is not configured on port {interface.name}"
            )
        self._run(
            f"ip netns exec {self.id} bridge vlan del dev {interface.id} vid {vlan_id}"
        )

        # Only when the last VLAN is gone: restore the default state so the
        # port is not left dead, and unlock the access/trunk mode. The
        # restore runs before the Python state is committed so a failure
        # leaves the tracking set consistent with the kernel.
        remaining = configured - {vlan_id}
        if not remaining:
            self._run(
                f"ip netns exec {self.id} bridge vlan add dev {interface.id} "
                "vid 1 pvid untagged"
            )
            interface._port_mode = None  # pylint: disable=protected-access
        interface._configured_vlans = remaining  # pylint: disable=protected-access
        return interface

    def enable_routing(self, routing_protocol: "RoutingHelper"):
        """Let a NeST routing object run its daemons on this switch.

        ``routing_protocol`` is a :class:`nest.routing.routing_helper.RoutingHelper`
        (OSPF, RIP, IS-IS, ...). When ``populate_routing_tables()`` runs, zebra
        and the routing daemon are started inside this switch's namespace on
        its Layer 3 interfaces: every addressed SVI and, if it has an address,
        the bridge itself (the native VLAN 1 SVI). Unaddressed bridge ports are
        never handed to the daemons.

        Call this after creating the helper and before
        ``routing_protocol.populate_routing_tables()``. Calling it again with
        the same helper is a no-op.
        """

        # Imported lazily: nest.routing imports nest.topology (circular).
        from nest.routing.routing_helper import RoutingHelper

        if not isinstance(routing_protocol, RoutingHelper):
            raise TypeError("routing_protocol must be a RoutingHelper instance")
        if config.get_value("routing_suite") == "bird":
            # bird support in RoutingHelper pairs every router interface with
            # its veth peer, which SVIs do not have.
            raise NotImplementedError(
                "Dynamic routing on an L3Switch needs the 'frr' or 'quagga' "
                "routing suite, not 'bird'"
            )
        # Register as a router so that the helper does not treat the switch as
        # a host. The node must live in exactly one of the two lists, so remove
        # it from the hosts list explicitly (TopologyMap.add_router() skips
        # that when the node is already a router). The lock is re-entrant.
        with TopologyMap.lock:
            routers = TopologyMap.get_routers()
            hosts = TopologyMap.get_hosts()
            if self not in routers:
                routers.append(self)
            while self in hosts:
                hosts.remove(self)
        if routing_protocol.hosts:
            while self in routing_protocol.hosts:
                routing_protocol.hosts.remove(self)

        if routing_protocol.routers is None:
            routing_protocol.routers = []

        # Reuse this helper's Layer 3 view if enable_routing() already ran.
        view = next(
            (
                router
                for router in routing_protocol.routers
                if isinstance(router, _L3RoutingNode) and router.switch is self
            ),
            None,
        )
        if view is None:
            view = _L3RoutingNode(self, routing_protocol)

        # The helper may have auto-discovered the real switch (it has more than
        # one interface), which would hand the unaddressed ports to the
        # daemons. Swap it for the Layer 3 view.
        routing_protocol.routers[:] = [
            view if router is self else router for router in routing_protocol.routers
        ]
        if view not in routing_protocol.routers:
            routing_protocol.routers.append(view)
        return routing_protocol