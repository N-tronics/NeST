"""Linux VLAN device support for topology interfaces."""

from nest import engine
from nest.topology_map import TopologyMap

from .device import Device


def validate_vlan_id(vlan_id):
    """Validate an 802.1Q VLAN identifier."""
    if isinstance(vlan_id, bool) or not isinstance(vlan_id, int):
        raise TypeError("vlan_id must be an integer")
    if not 1 <= vlan_id <= 4094:
        raise ValueError("vlan_id must be between 1 and 4094")


class SVIDevice(Device):
    """Linux VLAN device used by an SVI."""

    def __init__(self, name, node_id, parent_id, vlan_id):
        super().__init__(name, node_id)
        try:
            engine.create_vlan_interface(
                node_id, parent_id, self.id, vlan_id, check=True
            )
            engine.set_interface_mode(node_id, self.id, "up", check=True)
        except RuntimeError as error:
            engine.delete_interface(node_id, self.id)
            TopologyMap.delete_device(node_id, self.id)
            raise RuntimeError(
                f"Could not create VLAN interface {name} (VLAN {vlan_id}) "
                f"on {parent_id}"
            ) from error
