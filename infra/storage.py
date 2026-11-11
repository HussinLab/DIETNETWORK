"""Encrypted Cinder volume for user data (uploads/results) + Postgres.
`volume_type` must name an encrypted type available in your Arbutus
project (`openstack volume type list`) -- Arbutus commonly offers a
LUKS-encrypted type; ask your project's Alliance support contact if
unsure which name to use.

There is deliberately no `pulumi up`-time check that the named type is
actually encrypted: pulumi_openstack's `blockstorage` module (checked
against v4.x) exposes no data source to look up an *existing* volume
type's properties (only a resource for admin-*creating* one), and Cinder's
volume-type encryption association is a separate API this provider
doesn't surface at all -- so there is no reliable value to assert against
even with a lookup. This is enforced by operator diligence, not code:
verify with `openstack volume type show <name>` before `pulumi up` (look
for its encryption association), and see DEPLOYMENT.md's "Open items"
list. Don't add a check here that only inspects `extra_specs` for
something that looks encryption-related -- that key isn't standardized
across OpenStack deployments and a false pass would be worse than no
check at all."""
import pulumi
import pulumi_openstack as openstack


def create_data_volume(config: pulumi.Config) -> openstack.blockstorage.Volume:
    return openstack.blockstorage.Volume(
        "dietnet-data-volume",
        name="dietnet-data",
        description="Encrypted volume: per-user uploads/results + Postgres data (30-day retention)",
        size=config.get_int("volumeSizeGb") or 150,
        volume_type=config.require("volumeType"),
    )
