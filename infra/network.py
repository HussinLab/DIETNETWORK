"""Networking: reuse the project's existing network/subnet/router if
configured, otherwise create a small dedicated one plus a router out to
the external/provider network (needed so the floating IP can route in)."""
import pulumi
import pulumi_openstack as openstack


def get_or_create_network(config: pulumi.Config):
    external_network_name = config.require("externalNetworkName")
    external_network = openstack.networking.get_network(name=external_network_name, external=True)

    if config.get_bool("reuseExistingNetwork"):
        network_name = config.require("networkName")
        subnet_name = config.require("subnetName")
        existing_network = openstack.networking.get_network(name=network_name)
        existing_subnet = openstack.networking.get_subnet(name=subnet_name)
        return existing_network.id, existing_subnet.id, external_network.id, None

    network = openstack.networking.Network(
        "dietnet-network",
        name="dietnet-network",
        admin_state_up=True,
    )

    subnet = openstack.networking.Subnet(
        "dietnet-subnet",
        name="dietnet-subnet",
        network_id=network.id,
        cidr=config.get("subnetCidr") or "192.168.100.0/24",
        ip_version=4,
        dns_nameservers=["1.1.1.1", "8.8.8.8"],
    )

    router = openstack.networking.Router(
        "dietnet-router",
        name="dietnet-router",
        external_network_id=external_network.id,
    )

    router_interface = openstack.networking.RouterInterface(
        "dietnet-router-iface",
        router_id=router.id,
        subnet_id=subnet.id,
    )

    return network.id, subnet.id, external_network.id, router_interface
