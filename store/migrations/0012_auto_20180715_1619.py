# Generated by Django 2.0 on 2018-07-15 16:19

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0011_auto_20180715_1619'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='product',
            options={'ordering': ['-stock']},
        ),
    ]
