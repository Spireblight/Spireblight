import os
import unittest
import utils

class TestUtils(unittest.TestCase):
    def setUp(self):
        os.makedirs("data")

    def tearDown(self):
        os.removedirs("data")

    def test_getfile(self):
        filename = os.path.join("data", "data.json")
        with open(filename, "w+") as file:
            file.write("hi")
        with utils.getfile("data.json", "r") as file:
            self.assertEqual("hi", file.readline(), "incorrect file contents")
        os.remove(filename)

unittest.main()