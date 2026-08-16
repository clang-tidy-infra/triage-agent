import unittest

from triage_agent import main


class TestMain(unittest.TestCase):
    def test_returns_zero(self):
        self.assertEqual(main([]), 0)


if __name__ == "__main__":
    unittest.main()
