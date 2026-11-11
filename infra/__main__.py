"""
Pulumi program that provisions the Diet Network platform on Arbutus
(OpenStack), per deployPlan.md's "Pulumi IaC specification" section.

Auth: the `openstack` provider is configured via an Application Credential
in clouds.yaml, referenced through the `openstack:cloud` config value (see
infra/clouds.yaml.example) -- never a personal password, never committed.

Run:
    cd infra
    python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
    pulumi stack init arbutus
    cp Pulumi.arbutus.yaml.example Pulumi.arbutus.yaml   # then edit + set secrets
    pulumi up
"""
import pulumi

from compute import create_instance, create_keypair
from network import get_or_create_network
from security_groups import create_security_groups
from storage import create_data_volume

config = pulumi.Config()

network_id, subnet_id, external_network_id, _router_iface = get_or_create_network(config)
web_sg, internal_sg = create_security_groups(config)
data_volume = create_data_volume(config)
keypair = create_keypair(config)

instance, floating_ip = create_instance(
    config=config,
    network_id=network_id,
    subnet_id=subnet_id,
    external_network_id=external_network_id,
    web_sg=web_sg,
    internal_sg=internal_sg,
    keypair=keypair,
    data_volume=data_volume,
)

pulumi.export("floating_ip", floating_ip.address)
pulumi.export("instance_id", instance.id)
pulumi.export("data_volume_id", data_volume.id)
pulumi.export(
    "ssh_command",
    floating_ip.address.apply(lambda ip: f"ssh -i <path-to-private-key> ubuntu@{ip}"),
)
pulumi.export(
    "app_url",
    pulumi.Output.from_input((config.get("domain") or "")).apply(
        lambda d: f"https://{d}" if d else floating_ip.address.apply(lambda ip: f"https://{ip}")
    ),
)
