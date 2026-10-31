# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2019-2022 NITK Surathkal

"""API related to creation of bridge in topology"""

import logging

from nest import engine
from .device import Device
from .vlan import validate_vlan_id

logger = logging.getLogger(__name__)


class Bridge(Device):
    """
    Abstraction for a bridge.

    Attributes
    ----------
    id : str
        This value is used by `engine` to create emulated interface
        entity
    node_id : str
        id of the Node to which this Device belongs
    """

    def __init__(self, name, node_id):
        """
        Constructor of Bridge

        Parameters
        ----------
        name : str
            Name of the bridge
        node_id : str
            Id of the node that the bridge belongs to
        """
        super().__init__(name, node_id)
        # The namespace ID and bridge device ID are different when random
        # names are enabled. Create and configure the bridge using the actual
        # device ID after Device has generated it.
        engine.create_switch(node_id, self.id)
        engine.set_switch_mode(node_id, "up", self.id)

    def enable_vlan_filtering(self):
        """Enable VLAN filtering on this bridge."""
        return engine.set_bridge_vlan_filtering(self.node_id, self.id, check=True)

    def add_vlan(self, vlan_id):
        """Allow a VLAN on the bridge's local interface."""
        validate_vlan_id(vlan_id)
        return engine.add_bridge_vlan(
            self.node_id, self.id, vlan_id, self_port=True, check=True
        )

    def delete_vlan(self, vlan_id):
        """Remove a VLAN from the bridge's local interface."""
        validate_vlan_id(vlan_id)
        return engine.delete_bridge_vlan(
            self.node_id, self.id, vlan_id, self_port=True, check=True
        )

    def _validate_port(self, interface):
        if not hasattr(interface, "id") or not hasattr(interface, "node_id"):
            raise TypeError("interface must be a NeST interface")
        if interface.node_id != self.node_id:
            raise ValueError("interface must belong to this bridge")
        if interface.id == self.id:
            raise ValueError("the bridge cannot be configured as its own port")
        if getattr(interface, "_is_svi", False):
            raise ValueError("an SVI cannot be configured as a bridge port")

    @staticmethod
    def _init_port_state(interface):
        if not hasattr(interface, "_configured_vlans"):
            interface._configured_vlans = set()  # pylint: disable=protected-access
            interface._port_mode = None  # pylint: disable=protected-access
            interface._native_vlan = None  # pylint: disable=protected-access

    def _add_port_vlan(self, interface, vlan_id, pvid=False, untagged=False):
        validate_vlan_id(vlan_id)
        self._validate_port(interface)
        return engine.add_bridge_vlan(
            self.node_id,
            interface.id,
            vlan_id,
            pvid=pvid,
            untagged=untagged,
            check=True,
        )

    def _rollback_port(self, interface, vlan_ids):
        for vlan_id in vlan_ids:
            engine.delete_bridge_vlan(self.node_id, interface.id, vlan_id)
        engine.add_bridge_vlan(
            self.node_id, interface.id, 1, pvid=True, untagged=True
        )

    def set_access_vlan(self, interface, vlan_id):
        """Configure an untagged access port."""
        self._init_port_state(interface)
        validate_vlan_id(vlan_id)
        self._validate_port(interface)
        if interface._port_mode == "trunk":  # pylint: disable=protected-access
            raise ValueError("Remove trunk VLANs before changing to access mode")
        if interface._configured_vlans:  # pylint: disable=protected-access
            raise ValueError("Port already has VLANs configured")

        self.enable_vlan_filtering()
        # A newly attached port may not have an explicit VLAN 1 entry yet.
        # Deleting the default entry is therefore intentionally idempotent;
        # adding the requested VLAN below remains checked.
        engine.delete_bridge_vlan(self.node_id, interface.id, 1)
        try:
            self._add_port_vlan(interface, vlan_id, pvid=True, untagged=True)
        except Exception:
            self._rollback_port(interface, [vlan_id])
            raise
        interface._configured_vlans.add(vlan_id)  # pylint: disable=protected-access
        interface._port_mode = "access"  # pylint: disable=protected-access
        interface._native_vlan = vlan_id  # pylint: disable=protected-access
        return interface

    def set_trunk_vlans(self, interface, vlan_ids, native_vlan=1):
        """Configure a trunk port with a native VLAN."""
        self._init_port_state(interface)
        self._validate_port(interface)
        if interface._port_mode == "access":  # pylint: disable=protected-access
            raise ValueError("Remove access VLAN before changing to trunk mode")
        if interface._configured_vlans:  # pylint: disable=protected-access
            raise ValueError("Port already has VLANs configured")
        if not vlan_ids:
            raise ValueError("vlan_ids must contain at least one VLAN")
        validate_vlan_id(native_vlan)
        for vlan_id in vlan_ids:
            validate_vlan_id(vlan_id)

        self.enable_vlan_filtering()
        wanted = {native_vlan, *vlan_ids}
        if 1 not in wanted:
            # VLAN 1 may not be present on a newly attached port.
            engine.delete_bridge_vlan(self.node_id, interface.id, 1)
        try:
            self._add_port_vlan(interface, native_vlan, pvid=True, untagged=True)
            for vlan_id in vlan_ids:
                if vlan_id != native_vlan:
                    self._add_port_vlan(interface, vlan_id)
        except Exception:
            self._rollback_port(interface, wanted - {1})
            raise
        interface._configured_vlans.update(vlan_ids)  # pylint: disable=protected-access
        interface._configured_vlans.add(native_vlan)  # pylint: disable=protected-access
        interface._port_mode = "trunk"  # pylint: disable=protected-access
        interface._native_vlan = native_vlan  # pylint: disable=protected-access
        return interface

    def remove_port_vlan(self, interface, vlan_id):
        """Remove a VLAN from a configured bridge port."""
        self._init_port_state(interface)
        validate_vlan_id(vlan_id)
        self._validate_port(interface)
        configured = interface._configured_vlans  # pylint: disable=protected-access
        if vlan_id not in configured:
            raise ValueError(f"VLAN {vlan_id} is not configured on port {interface.name}")
        native_vlan = getattr(interface, "_native_vlan", None)
        if vlan_id == native_vlan and len(configured) > 1:
            raise ValueError("Cannot remove the native VLAN while other VLANs remain")

        engine.delete_bridge_vlan(
            self.node_id, interface.id, vlan_id, check=True
        )
        remaining = configured - {vlan_id}
        if not remaining:
            engine.add_bridge_vlan(
                self.node_id, interface.id, 1, pvid=True, untagged=True, check=True
            )
            interface._port_mode = None  # pylint: disable=protected-access
            interface._native_vlan = None  # pylint: disable=protected-access
        interface._configured_vlans = remaining  # pylint: disable=protected-access
        return interface
