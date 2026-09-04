import json
import unittest

from ui_faultlab.agents.generic_vlm import StrictOutputError, parse_action_json


class VLMContractTest(unittest.TestCase):
    def test_strict_json_action_parser(self):
        action = parse_action_json(json.dumps({"type": "tap", "x": .4, "y": .2, "reason": "target"}))
        self.assertEqual(action.type, "tap")

    def test_parser_does_not_repair_python_literal(self):
        with self.assertRaises(StrictOutputError):
            parse_action_json("{'type': 'finish'}")


if __name__ == "__main__":
    unittest.main()

