from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_category_task_category'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='category',
            unique_together={('user', 'name')},
        ),
    ]
