"""Switched virtual interface support."""

from nest.input_validator import input_validator
from nest.topology.device.vlan import SVIDevice

from .base_interface import BaseInterface


class SVI(BaseInterface):
    """Layer 3 interface for a VLAN on an :class:`L3Switch`."""

    @input_validator
    def __init__(self, switch, vlan_id: int, name: str):
        self._switch = switch
        self._vlan_id = vlan_id
        self._is_svi = True
        super().__init__(
            name,
            SVIDevice(name, switch._id, switch._device.id, vlan_id),
        )

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
