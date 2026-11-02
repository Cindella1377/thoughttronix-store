import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    """Files under ``PRIVATE_MEDIA_ROOT``, which nothing serves directly.

    The location is read from settings each time, so tests can redirect
    it. There is no URL at all: a file leaves only through a view that
    checks who is asking.
    """

    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Private files have no public URL.")
