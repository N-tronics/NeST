"""Wrapper for the bridge tool"""

import logging

from .exec import exec_subprocess

logger = logging.getLogger(__name__)


def add_vlan_tag_to_if(ns_name, interface, vlan_id, access):
    """
    Adds the inteface to the specified VLAN

    Parameters
    ----------
    interface: Interface
        `Interface` to be assigned
    vlan_id: int
        vlan id
    access: bool
        If True, the interface will be an access port, other wise a trunk port
    """
    exec_subprocess(
        f"ip netns exec {ns_name} bridge vlan add dev {interface.id} vid {vlan_id}"
        + (" pvid untagged" if access else "")
    )


def rem_vlan_tag_from_if(ns_name, interface, vlan_id):
    """
    Removes the interface from the specified VLAN

    Parameters
    ----------
    interface: Interface
        `Interface` to be removed
    vlan_id: int
        vlan id
    """
    exec_subprocess(
        f"ip netns exec {ns_name} bridge vlan del dev {interface.id} vid {vlan_id}"
    )
