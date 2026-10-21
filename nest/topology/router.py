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

    def create_vlan_subif(self, interface, vlan_id, name=None):
        """
        Creates a new subinterface on the router associated with a VLAN

        Parameters
        ----------
        interface: BaseInterface
            parent interface on the router
        vlan_id: int
        name: (None | str)
            name of the subinterface, if None, set to parent_interface.vlan_id
        """
        if name is None:
            name = f"{interface.id}.{vlan_id}"

        dev = VlanEnd(name, self.id)
        engine.create_vlan_subinterface(self.id, interface, dev.id, vlan_id)

        vlan_if = BaseInterface(name, dev)
        vlan_if.set_mode("UP")

        return vlan_if
