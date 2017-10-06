import unittest
from twnm import twnm as t

class TWNetworkManagerTest(unittest.TestCase):

    def test_netmask_bits(self):
        assert t.netmask_bits("255.255.0.0") == 16
        assert t.netmask_bits("255.255.255.0") == 24
        assert t.netmask_bits("255.255.255.192") == 26
        