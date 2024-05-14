import unittest
from ..create_bedrock_components import main

class TestMain(unittest.TestCase):

  def test_main_function(self):
    main()
    # add assertions here to validate main() behavior

if __name__ == '__main__':
  unittest.main()
