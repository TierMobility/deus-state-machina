from contextlib import contextmanager
from django.db import transaction
from django.db.transaction import get_connection
from threading import RLock


@contextmanager
def lock_table(model):
    # adapted from https://stackoverflow.com/a/41831049/1191373
    with transaction.atomic():
        cursor = get_connection().cursor()
        cursor.execute(f'LOCK TABLE {model._meta.db_table}')
        yield
        cursor.close()


@contextmanager
def lock_object(obj):
    with transaction.atomic():
        obj.__class__.objects.select_for_update().get(pk=obj.pk)
        yield


_attach_lock = RLock()


def get_or_attach_lock_to_object(obj):
    # we need to have a global lock that allows us to set a lock on the individual instance in a thread-safe way
    with _attach_lock:
        try:
            return obj.__thread_lock
        except AttributeError:
            obj.__thread_lock = RLock()
            return obj.__thread_lock


@contextmanager
def thread_lock_object(obj):
    with get_or_attach_lock_to_object(obj):
        yield
