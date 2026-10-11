import logging

from .device import Device

logger = logging.getLogger(__name__)


class VlanEnd(Device):
    def __init__(self, name, node_id):
        super().__init__(name, node_id)
