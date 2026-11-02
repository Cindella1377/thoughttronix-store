from django.db import migrations

# The app cannot take an application without these, so they ship as a
# migration rather than in ``seed``.
DEFAULT_STAGES = [
    ("Applied", "entry"),
    ("Screening", "in_progress"),
    ("Interview", "in_progress"),
    ("Offer", "in_progress"),
    ("Hired", "hired"),
    ("Rejected", "rejected"),
    ("Withdrawn", "withdrawn"),
]


def create_default_stages(apps, schema_editor):
    Stage = apps.get_model("careers", "Stage")
    Stage.objects.bulk_create(
        Stage(name=name, kind=kind, position=position)
        for position, (name, kind) in enumerate(DEFAULT_STAGES)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("careers", "0002_stage_application_stagechange_and_more"),
    ]

    operations = [
        migrations.RunPython(create_default_stages, migrations.RunPython.noop),
    ]
