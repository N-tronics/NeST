"""Routing adapter for Layer 3 switches."""


class L3RoutingNode:
    """Expose only addressed L3 interfaces of an L3 switch to routing daemons."""

    def __init__(self, switch, routing_helper):
        self._switch = switch
        self._helper = routing_helper

    @property
    def switch(self):
        return self._switch

    @property
    def id(self):
        return self._switch.id

    @property
    def name(self):
        return self._switch.name

    @property
    def interfaces(self):
        ipv6 = self._helper.ipv6_routing
        candidates = [self._switch, *self._switch.svis.values()]
        routed = [i for i in candidates if i.get_address(not ipv6, ipv6, True)]
        if not routed:
            family = "IPv6" if ipv6 else "IPv4"
            raise ValueError(
                f"{self.name} has no {family}-addressed SVI "
                "(or bridge address) to run routing on"
            )
        return routed

    def __repr__(self):
        return f"{self.__class__.__name__}({self.name!r})"
