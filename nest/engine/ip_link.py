# SPDX-License-Identifier: GPL-2.0-only
# Copyright (c) 2019-2020 NITK Surathkal

"""IP link commands"""

import logging
from .exec import exec_subprocess

logger = logging.getLogger(__name__)


def _run_link_command(command, operation, check=False):
    """Run a link command and optionally raise on failure."""
    exit_code = exec_subprocess(command)
    if check and exit_code != 0:
        raise RuntimeError(
            f"Engine operation failed with exit code {exit_code}: {operation}"
        )
    return exit_code


def create_switch(ns_name, s_name):
    """
    Create switch if it doesn't already exist.
    Switch is contained inside a namespace.

    Parameters
    ----------
    s_name : str
        switch name
    ns_name : str
        namespace name
    """
    exec_subprocess(f"ip netns exec {ns_name} ip link add {s_name} type bridge")


def delete_switch(ns_name, s_name):
    """
    Delete switch inside a namespace, if it exists.

    Parameters
    ----------
    s_name : str
        switch name
    ns_name : str
        namespace name
    """
    exec_subprocess(f"ip netns exec {ns_name} ip link del {s_name}")


def set_switch_mode(ns_name, mode, bridge_name=None):
    """
    Set switch mode

    Parameters
    ----------
    ns_name : str
        namespace name
    mode : str
        'up' or 'down'
    bridge_name : str, optional
        Linux bridge name. Defaults to ``ns_name`` for compatibility.
    """
    bridge_name = bridge_name or ns_name
    exec_subprocess(
        f"ip netns exec {ns_name} ip link set dev {bridge_name} {mode}"
    )


def add_int_to_switch(s_name, dev_name, ns_name=None):
    """
    Add interface to a switch

    Parameters
    ----------
    s_name : str
        switch name
    dev_name : str
        interface name
    ns_name : str, optional
        Namespace containing the bridge. Defaults to ``s_name`` for
        compatibility.
    """
    ns_name = ns_name or s_name
    exec_subprocess(
        f"ip netns exec {ns_name} ip link set {dev_name} master {s_name}"
    )


def create_veth(dev_name1, dev_name2):
    """
    Create a veth pair with endpoint interfaces `dev_name1`
    and `dev_name2`

    Parameters
    ----------
    dev_name1 : str
    dev_name2 : str
    """
    exec_subprocess(f"ip link add {dev_name1} type veth peer name {dev_name2}")


def create_ifb(dev_name):
    """
    Create a IFB

    Parameters
    ----------
    dev_name : str
        interface names
    """

    exec_subprocess(f"ip link add {dev_name} type ifb")


def add_int_to_ns(ns_name, dev_name):
    """
    Add interface to a namespace

    Parameters
    ----------
    ns_name : str
        namespace name
    dev_name : str
        interface name
    """
    exec_subprocess(f"ip link set {dev_name} netns {ns_name}")


def set_int_up(ns_name, dev_name):
    """
    Set interface mode to up

    Parameters
    ----------
    ns_name : str
        namespace name
    dev_name : str
        interface name
    """
    exec_subprocess(f"ip netns exec {ns_name} ip link set dev {dev_name} up")


def setup_veth(ns_name1, ns_name2, dev_name1, dev_name2):
    """
    Sets up veth connection between interfaces. The interfaces are
    set up as well.

    The connections are made between `dev_name1` in `ns_name1` and
    `dev_name2` in `ns_name2`

    Parameters
    ----------
    ns_name1 : str
    dev_name1 : str
    dev_name2 : str
    ns_name2 : str
    """
    create_veth(dev_name1, dev_name2)
    add_int_to_ns(ns_name1, dev_name1)
    add_int_to_ns(ns_name2, dev_name2)
    set_int_up(ns_name1, dev_name1)
    set_int_up(ns_name2, dev_name2)


def setup_ifb(ns_name, dev_name):
    """
    Sets up an IFB device. The device is setup as well.

    Parameters
    ----------
    ns_name : str
        namespace name
    dev_name : str
        name of IFB
    """

    create_ifb(dev_name)
    add_int_to_ns(ns_name, dev_name)
    set_int_up(ns_name, dev_name)


def set_interface_mode(ns_name, dev_name, mode, check=False):
    """
    Set interface mode up or down

    Parameters
    ----------
    ns_name : str
    dev_name : str
    mode : str
        'up' or 'down'
    """
    return _run_link_command(
        f"ip netns exec {ns_name} ip link set dev {dev_name} {mode}",
        f"set interface {dev_name} {mode}",
        check,
    )


def create_vlan_interface(ns_name, parent_name, dev_name, vlan_id, check=False):
    """Create a VLAN interface inside a network namespace.

    Returns the command exit code so callers can keep Python state in sync
    with the kernel state.
    """
    return _run_link_command(
        f"ip netns exec {ns_name} ip link add link {parent_name} "
        f"name {dev_name} type vlan id {vlan_id}",
        f"create VLAN interface {dev_name} (VLAN {vlan_id})",
        check,
    )


def delete_interface(ns_name, dev_name, check=False):
    """Delete a network interface from a network namespace."""
    return _run_link_command(
        f"ip netns exec {ns_name} ip link delete {dev_name}",
        f"delete interface {dev_name}",
        check,
    )


def set_bridge_vlan_filtering(ns_name, bridge_name, enabled=True, check=False):
    """Enable or disable VLAN filtering on a Linux bridge."""
    value = 1 if enabled else 0
    return _run_link_command(
        f"ip netns exec {ns_name} ip link set dev {bridge_name} "
        f"type bridge vlan_filtering {value}",
        f"set VLAN filtering on bridge {bridge_name} to {value}",
        check,
    )


def add_bridge_vlan(
    ns_name,
    dev_name,
    vlan_id,
    *,
    self_port=False,
    pvid=False,
    untagged=False,
    check=False,
):
    """Add VLAN membership to a Linux bridge device or bridge port."""
    flags = []
    if self_port:
        flags.append("self")
    if pvid:
        flags.append("pvid")
    if untagged:
        flags.append("untagged")
    suffix = " ".join(flags)
    command = (
        f"ip netns exec {ns_name} bridge vlan add dev {dev_name} "
        f"vid {vlan_id}"
    )
    if suffix:
        command += f" {suffix}"
    return _run_link_command(
        command,
        f"add VLAN {vlan_id} to {dev_name}",
        check,
    )


def delete_bridge_vlan(ns_name, dev_name, vlan_id, *, self_port=False, check=False):
    """Delete VLAN membership from a Linux bridge device or bridge port."""
    suffix = " self" if self_port else ""
    return _run_link_command(
        f"ip netns exec {ns_name} bridge vlan del dev {dev_name} "
        f"vid {vlan_id}{suffix}",
        f"delete VLAN {vlan_id} from {dev_name}",
        check,
    )


def set_mtu_interface(ns_name, dev_name, mtu_value):
    """
    Set the MTU for the interface

    Parameters
    ----------
    ns_name : str
    dev_name : str
    mtu_value : int
    """
    exec_subprocess(
        f"ip netns exec {ns_name} ip link set dev {dev_name} mtu {mtu_value}"
    )
    # Verify if the mtu is set
    mtu = int(
        exec_subprocess(
            f" ip netns exec {ns_name} cat /sys/class/net/{dev_name}/mtu", output=True
        )
    )
    if mtu != mtu_value:
        logger.error(
            "MTU of interface %s wasn't set to %s!", str(dev_name), str(mtu_value)
        )
