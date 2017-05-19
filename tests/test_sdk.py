import unittest

from eu.softfire.main import start_manager
from eu.softfire.manager import AbstractManager


class DummyManager(AbstractManager):
    def create_user(self, username, password):
        pass

    def refresh_resources(self, user_info):
        pass

    def list_resources(self, user_info=None, payload=None):
        pass

    def provide_resources(self, user_info, payload=None):
        pass

    def release_resources(self, user_info, payload=None):
        pass


class MyTestCase(unittest.TestCase):
    def test_something(self):
        manager = DummyManager()
        self.assertIsNone(manager.list_resources())
        self.assertIsNone(manager.provide_resources(None))
        self.assertIsNone(manager.refresh_resources(None))
        self.assertIsNone(manager.release_resources(None))


if __name__ == '__main__':
    start_manager(DummyManager(), '/etc/softfire/nfv-manager.ini')
