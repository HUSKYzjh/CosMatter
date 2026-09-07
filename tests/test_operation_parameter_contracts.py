import unittest

from cosmatter.operation_parameter_contracts import (
    operation_parameter_contracts,
    parse_sciverse_limit,
    parse_sciverse_offset,
    validate_sciverse_content_parameters,
)


class OperationParameterContractTests(unittest.TestCase):
    def test_sciverse_content_contract_is_closed_bounded_and_nonexecuting(self) -> None:
        contract = operation_parameter_contracts()
        schema = contract["operations"]["sciverse_read_content"]
        self.assertEqual(contract["trust_status"], "static_parameter_contracts_not_execution_authorization")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(schema["required"], ["offset", "limit"])
        self.assertEqual(schema["properties"]["offset"], {"type": "integer", "minimum": 0, "default": 0})
        self.assertEqual(schema["properties"]["limit"], {"type": "integer", "minimum": 200, "maximum": 4000, "default": 2000})

    def test_shared_parser_and_runtime_validation_reject_the_same_boundaries(self) -> None:
        self.assertEqual(parse_sciverse_offset("0"), 0)
        self.assertEqual(parse_sciverse_limit("200"), 200)
        self.assertEqual(validate_sciverse_content_parameters(10, 4000), (10, 4000))
        for value in ("-1",):
            with self.assertRaises(ValueError):
                parse_sciverse_offset(value)
        for value in ("199", "4001", "8192"):
            with self.assertRaises(ValueError):
                parse_sciverse_limit(value)
        for offset, limit in ((True, 200), (0, False), (-1, 200), (0, 8192)):
            with self.assertRaises(ValueError):
                validate_sciverse_content_parameters(offset, limit)


if __name__ == "__main__":
    unittest.main()
