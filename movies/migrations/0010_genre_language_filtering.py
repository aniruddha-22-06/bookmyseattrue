from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('movies', '0009_analytics_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='Genre',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(max_length=120, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Language',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('code', models.CharField(max_length=10, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='movie',
            name='genres',
            field=models.ManyToManyField(blank=True, related_name='movies', to='movies.genre'),
        ),
        migrations.AddField(
            model_name='movie',
            name='languages',
            field=models.ManyToManyField(blank=True, related_name='movies', to='movies.language'),
        ),
        migrations.AddIndex(
            model_name='movie',
            index=models.Index(fields=['name'], name='movie_name_idx'),
        ),
        migrations.AddIndex(
            model_name='movie',
            index=models.Index(fields=['rating'], name='movie_rating_idx'),
        ),
        migrations.AddIndex(
            model_name='genre',
            index=models.Index(fields=['name'], name='genre_name_idx'),
        ),
        migrations.AddIndex(
            model_name='genre',
            index=models.Index(fields=['slug'], name='genre_slug_idx'),
        ),
        migrations.AddIndex(
            model_name='language',
            index=models.Index(fields=['name'], name='language_name_idx'),
        ),
        migrations.AddIndex(
            model_name='language',
            index=models.Index(fields=['code'], name='language_code_idx'),
        ),
    ]
