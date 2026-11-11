"""Compute: SSH keypair, the CPU VM, floating IP, volume attachment, and
cloud-init user_data rendering."""
import pathlib

import pulumi
import pulumi_openstack as openstack

_TEMPLATE_PATH = pathlib.Path(__file__).parent / "cloud-init" / "user_data.sh.tmpl"


def _render_user_data(values: dict) -> str:
    text = _TEMPLATE_PATH.read_text()
    for key, value in values.items():
        text = text.replace(f"__{key}__", str(value))
    return text


def create_keypair(config: pulumi.Config) -> openstack.compute.Keypair:
    return openstack.compute.Keypair(
        "dietnet-keypair",
        name="dietnet-keypair",
        public_key=config.require("keypairPublicKey"),
    )


def create_instance(
    config: pulumi.Config,
    network_id: pulumi.Input[str],
    subnet_id: pulumi.Input[str],
    external_network_id: pulumi.Input[str],
    web_sg: openstack.networking.SecGroup,
    internal_sg: openstack.networking.SecGroup,
    keypair: openstack.compute.Keypair,
    data_volume: openstack.blockstorage.Volume,
):
    port = openstack.networking.Port(
        "dietnet-instance-port",
        network_id=network_id,
        security_group_ids=[web_sg.id, internal_sg.id],
        fixed_ips=[openstack.networking.PortFixedIpArgs(subnet_id=subnet_id)],
    )

    domain = config.get("domain") or ""
    scheme_host = domain if domain else "localhost"  # falls back to self-signed cert on the floating IP

    user_data_values = {
        "DOMAIN": scheme_host,
        "ACME_EMAIL": config.get("acmeEmail") or "admin@example.org",
        "BASE_URL": f"https://{scheme_host}",
        "FRONTEND_URL": f"https://{scheme_host}",
        "PUBLIC_API_BASE_URL": f"https://{scheme_host}/api",
        "GIT_REPO_URL": config.get("gitRepoUrl") or "https://github.com/HussinLab/DIETNETWORK.git",
        "GIT_REF": config.get("gitRef") or "main",
        "RETENTION_DAYS": config.get("retentionDays") or "30",
        "DELETE_RAW_AFTER_SUCCESS": config.get("deleteRawAfterSuccess") or "true",
        "SMTP_PORT": config.get("smtpPort") or "587",
    }
    secret_values = pulumi.Output.all(
        db_password=config.require_secret("dbPassword"),
        jwt_secret=config.require_secret("jwtSecret"),
        smtp_host=config.require_secret("smtpHost"),
        smtp_username=config.get_secret("smtpUsername") or pulumi.Output.from_input(""),
        smtp_password=config.get_secret("smtpPassword") or pulumi.Output.from_input(""),
        turnstile_secret=config.require_secret("turnstileSecretKey"),
        turnstile_site_key=config.get_secret("turnstileSiteKey") or pulumi.Output.from_input(""),
    ).apply(
        lambda s: {
            "POSTGRES_PASSWORD": s["db_password"],
            "JWT_SECRET": s["jwt_secret"],
            "SMTP_HOST": s["smtp_host"],
            "SMTP_USERNAME": s["smtp_username"],
            "SMTP_PASSWORD": s["smtp_password"],
            "SMTP_FROM": config.get("smtpFromAddress") or f"no-reply@{scheme_host}",
            "TURNSTILE_SECRET": s["turnstile_secret"],
            "TURNSTILE_SITE_KEY": s["turnstile_site_key"],
        }
    )

    user_data = secret_values.apply(lambda secrets: _render_user_data({**user_data_values, **secrets}))

    instance = openstack.compute.Instance(
        "dietnet-instance",
        name="dietnet-instance",
        image_name=config.require("imageName"),
        flavor_name=config.require("flavorName"),
        key_pair=keypair.name,
        security_groups=[],  # SGs are attached to the port instead, above
        networks=[openstack.compute.InstanceNetworkArgs(port=port.id)],
        user_data=user_data,
    )

    openstack.compute.VolumeAttach(
        "dietnet-data-volume-attach",
        instance_id=instance.id,
        volume_id=data_volume.id,
    )

    # `pool` takes the external network's *name*; quota on Arbutus is
    # typically small (~2), so this stack allocates exactly one.
    floating_ip = openstack.networking.FloatingIp(
        "dietnet-floating-ip",
        pool=config.require("externalNetworkName"),
    )

    openstack.networking.FloatingIpAssociate(
        "dietnet-floating-ip-assoc",
        floating_ip=floating_ip.address,
        port_id=port.id,
    )

    return instance, floating_ip
