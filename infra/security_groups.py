"""
Least-privilege security groups (deployPlan.md 'Security groups'):
  - 443 and 80 open to the world (80 only for ACME HTTP-01 / redirect).
  - 22 restricted to the admin CIDR only.
  - Postgres/Redis: no ingress from outside; only reachable within the
    `internal` security group.

Note: in the current single-VM topology, docker-compose already keeps
Postgres/Redis unbound from the host (no -p flag), so no packet for 5432
or 6432 ever reaches the OpenStack network layer regardless of this group.
The `internal` security group is what will matter once the worker moves
to its own instance (deployPlan.md's "no code changes" scaling path) --
at that point Postgres/Redis get real host-bound ports and this group is
the only thing standing between them and the internet.
"""
import pulumi
import pulumi_openstack as openstack


def create_security_groups(config: pulumi.Config):
    admin_cidr = config.require("adminCidr")

    web_sg = openstack.networking.SecGroup(
        "dietnet-web-sg",
        name="dietnet-web-sg",
        description="Public HTTP/HTTPS; SSH restricted to admin CIDR",
    )
    openstack.networking.SecGroupRule(
        "web-sg-http",
        security_group_id=web_sg.id,
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=80,
        port_range_max=80,
        remote_ip_prefix="0.0.0.0/0",
        description="ACME HTTP-01 challenge + HTTP->HTTPS redirect",
    )
    openstack.networking.SecGroupRule(
        "web-sg-https",
        security_group_id=web_sg.id,
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=443,
        port_range_max=443,
        remote_ip_prefix="0.0.0.0/0",
    )
    openstack.networking.SecGroupRule(
        "web-sg-ssh",
        security_group_id=web_sg.id,
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=22,
        port_range_max=22,
        remote_ip_prefix=admin_cidr,
    )

    internal_sg = openstack.networking.SecGroup(
        "dietnet-internal-sg",
        name="dietnet-internal-sg",
        description="Postgres/Redis: ingress only from members of this same group",
    )
    openstack.networking.SecGroupRule(
        "internal-sg-postgres",
        security_group_id=internal_sg.id,
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=5432,
        port_range_max=5432,
        remote_group_id=internal_sg.id,
    )
    openstack.networking.SecGroupRule(
        "internal-sg-redis",
        security_group_id=internal_sg.id,
        direction="ingress",
        ethertype="IPv4",
        protocol="tcp",
        port_range_min=6379,
        port_range_max=6379,
        remote_group_id=internal_sg.id,
    )

    return web_sg, internal_sg
