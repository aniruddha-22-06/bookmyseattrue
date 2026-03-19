from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand


DEFAULT_USERNAME = 'analytics_admin'
DEFAULT_PASSWORD = 'ani2006'
DEFAULT_EMAIL = 'aniruddhaa719@gmail.com'


class Command(BaseCommand):
    help = 'Create or update an admin analytics user for dashboard access.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default=DEFAULT_USERNAME, help='Username for the admin user.')
        parser.add_argument('--password', default=DEFAULT_PASSWORD, help='Password to set for the admin user.')
        parser.add_argument('--email', default=DEFAULT_EMAIL, help='Email address for the admin user.')
        parser.add_argument('--reset-password', action='store_true', help='Reset password if user exists.')
        parser.add_argument('--superuser', action='store_true', help='Grant superuser privileges.')

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']
        reset_password = options['reset_password']
        make_superuser = options['superuser']

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )

        if email and user.email != email:
            user.email = email

        if created or reset_password:
            user.set_password(password)

        user.is_staff = True
        if make_superuser:
            user.is_superuser = True

        user.save()

        group, _ = Group.objects.get_or_create(name='analytics_admin')
        user.groups.add(group)

        status = 'created' if created else 'updated'
        if reset_password:
            status += ' (password reset)'

        self.stdout.write(self.style.SUCCESS(
            f'Analytics admin user {status}: {username}'
        ))