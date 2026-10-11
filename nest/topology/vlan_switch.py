# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2019-2021 NITK Surathkal

"""API related to L3 switch creation in topology"""

import logging

from nest import engine
from nest.topology.device.bridge import Bridge
from nest.topology.interface import BaseInterface
from nest.topology.node import Node

logger = logging.getLogger(__name__)


class VLAN_Switch(Node, BaseInterface):
    """
    Abstraction for a switch.

    Attributes
    ----------
    name: str
        User given name for the switch.
    """

    def __init__(self, name):
        """
        Create a switch with given `name` inside a 'Node'.

        A namespace is created by inheriting the "Node" class and unique id is given
        to the namespace. Then a bridge with the same name and unique id as namespace
        is created inside the created namespace.

        Parameters
        ----------
        name: str
            The name of the switch to be created
        """

        Node.__init__(self, name)
        _bridge = Bridge(name, self._id)
        BaseInterface.__init__(self, name, _bridge)
        _bridge.enable_vlan_filtering()

    def _add_interface(self, interface: BaseInterface):
        """
        Add `interface` to `Switch`

        Parameters
        ----------
        interface: Interface
            `Interface` to be added to `Switch`
        """
        super()._add_interface(interface)
        engine.add_int_to_switch(self.id, interface.id)

    def _add_interface_to_vlan(
        self, interface: BaseInterface, vlan: int, access_port: bool
    ):
        engine.exec_subprocess(
            f"ip netns exec {self.node_id} bridge vlan add dev {interface.id} vid {vlan}"
            + (" pvid untagged" if access_port else "")
        )

    def _del_interface_from_vlan(self, interface: BaseInterface, vlan: int):
        engine.exec_subprocess(
            f"ip netns exec {self.node_id} bridge vlan del dev {interface.id} vid {vlan}"
        )
