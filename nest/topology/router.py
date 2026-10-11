# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2019-2021 NITK Surathkal

"""API related to router creation in topology"""

from nest import engine
from nest.topology.device import VlanEnd
from nest.topology.interface.base_interface import BaseInterface
from nest.topology.node import Node


class Router(Node):
    """
    Abstraction for a Router.

    Attributes
    ----------
    name: str
        User given name for the Router.
    """

    def __init__(self, name):
        """
        Create a router with given `name`.

        Parameters
        ----------
        name: str
            The name of the router to be created
        """
        super().__init__(name)
        self.enable_ip_forwarding()

    def _create_vlan_subif(
        self, interface: BaseInterface, vlan_id: int, name: (None | str) = None
    ):
        if name is None:
            name = f"{interface.name}.{vlan_id}"
        engine.exec_subprocess(
            f"ip netns exec {self._id} ip link add link {interface.id} name {interface.id}.{vlan_id} type vlan id {vlan_id}"
        )

        dev = VlanEnd(name, self.id)
        vlan_if = BaseInterface(name, dev)
        vlan_if.set_mode("UP")

        return vlan_if
