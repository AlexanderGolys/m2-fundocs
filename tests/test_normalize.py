import unittest
import json

from tools.m2_normalize import (
    classify_kind,
    normalize,
    parse_help_text,
    parse_methods,
    parse_options,
    parse_signature_id,
)


class NormalizeTests(unittest.TestCase):
    def test_parse_methods_extracts_signatures(self) -> None:
        raw = "new NumberedVerticalList from {(ideal,Matrix),(ideal,Module)}"
        parsed = parse_methods(raw)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["signature"], "ideal(Matrix)")
        self.assertEqual(parsed[1]["inputs"], ["Module"])

    def test_parse_options_extracts_option_keys_only(self) -> None:
        raw = "new OptionTable from {Degree => null, Strategy => Fast}"
        self.assertEqual(parse_options(raw), ["Degree", "Strategy"])

    def test_parse_signature_id_handles_operator_assignment(self) -> None:
        parsed = parse_signature_id("symbol +(symbol =)")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["name"], "symbol +")
        self.assertEqual(parsed["inputs"], ["symbol ="])

    def test_normalize_does_not_duplicate_type_objects(self) -> None:
        records = [
            {"symbol": "Matrix", "probe": "runtime_class", "stdout": "Type"},
            {"symbol": "Matrix", "probe": "parent", "stdout": "Thing"},
            {"symbol": "Matrix", "probe": "to_string", "stdout": "\"Matrix\""},
            {
                "symbol": "matrix",
                "probe": "runtime_class",
                "stdout": "MethodFunctionSingle",
            },
            {
                "symbol": "matrix",
                "probe": "methods",
                "stdout": "new NumberedVerticalList from {(matrix,Matrix)}",
            },
            {"symbol": "matrix", "probe": "options", "stdout": "null"},
        ]
        objects, _, _ = normalize(records)
        ids = [obj["id"] for obj in objects["objects"]]
        self.assertEqual(ids.count("core::type::Matrix"), 1)

    def test_parse_help_text_extracts_brief_examples_and_io_descriptions(self) -> None:
        payload = (
            "M2HELP2|SYMBOL=matrix\n"
            "M2HELP2|HEADER=matrix -- make a matrix\n"
            "M2HELP2|DESCRIPTION_BEGIN\n"
            "Creates a matrix from nested data.\n"
            "M2HELP2|DESCRIPTION_END\n"
            "M2HELP2|EXAMPLE_BEGIN\n"
            "+----------------------+\n"
            "|  i1 : matrix{{1,2}}  |\n"
            "|                      |\n"
            "|  o1 : Matrix ZZ      |\n"
            "+----------------------+\n"
            "M2HELP2|EXAMPLE_END\n"
            "M2HELP2|WAYS_ITEM=\"matrix(List)\" -- make matrix\n"
            "M2HELP2|WAYS_ITEM=\"matrix(Ring,List)\" -- make matrix\n"
            "M2HELP2|METHOD_BEGIN=matrix(List)\n"
            "M2HELP2|METHOD_HEADER=matrix(List) -- create matrix\n"
            "M2HELP2|METHOD_DESCRIPTION_BEGIN\n"
            "Method specific docs.\n"
            "M2HELP2|METHOD_DESCRIPTION_END\n"
            "M2HELP2|METHOD_EXAMPLE_BEGIN\n"
            "+----------------------+\n"
            "|  o1 : Matrix ZZ      |\n"
            "+----------------------+\n"
            "M2HELP2|METHOD_EXAMPLE_END\n"
            "M2HELP2|METHOD_END\n"
        )
        parsed = parse_help_text("matrix", json.dumps(payload))
        self.assertEqual(parsed["brief"], "make a matrix")
        self.assertEqual(parsed["description"], "Creates a matrix from nested data.")
        self.assertEqual(len(parsed["examples"]), 1)
        self.assertIn("o1 : Matrix ZZ", parsed["examples"][0])
        self.assertIn("matrix(List)", parsed["inputDescription"])
        self.assertEqual(parsed["outputDescription"], "Example outputs: Matrix ZZ")
        self.assertIn("matrix(List)", parsed["methods"])
        self.assertEqual(parsed["methods"]["matrix(List)"]["brief"], "create matrix")

    def test_parse_help_text_ignores_redirected_header(self) -> None:
        payload = "M2HELP2|HEADER=other -- another object\n"
        self.assertEqual(parse_help_text("matrix", payload), {})

    def test_parse_help_text_supports_m2help2_envelope(self) -> None:
        payload = (
            "M2HELP2|SYMBOL=matrix\n"
            "M2HELP2|HEADER=matrix -- make a matrix\n"
            "M2HELP2|DESCRIPTION_BEGIN\n"
            "Creates matrices.\n"
            "M2HELP2|DESCRIPTION_END\n"
        )
        parsed = parse_help_text("matrix", payload)
        self.assertEqual(parsed["brief"], "make a matrix")
        self.assertEqual(parsed["description"], "Creates matrices.")

    def test_normalize_creates_type_entities_from_dispatch(self) -> None:
        records = [
            {
                "symbol": "ideal",
                "probe": "runtime_class",
                "stdout": "MethodFunctionSingle",
            },
            {
                "symbol": "ideal",
                "probe": "methods",
                "stdout": "new NumberedVerticalList from {(ideal,Matrix),(ideal,Module)}",
            },
            {
                "symbol": "ideal",
                "probe": "options",
                "stdout": "null",
            },
            {
                "symbol": "ideal",
                "probe": "help_text",
                "stdout": json.dumps(
                    "M2HELP2|SYMBOL=ideal\n"
                    "M2HELP2|HEADER=ideal -- make an ideal\n"
                    "M2HELP2|DESCRIPTION_BEGIN\n"
                    "Construct an ideal from generators.\n"
                    "M2HELP2|DESCRIPTION_END\n"
                    "M2HELP2|EXAMPLE_BEGIN\n"
                    "+----------------------+\n"
                    "|  i1 : ideal(0_R)     |\n"
                    "|                      |\n"
                    "|  o1 : Ideal          |\n"
                    "+----------------------+\n"
                    "M2HELP2|EXAMPLE_END\n"
                    "M2HELP2|WAYS_ITEM=\"ideal(Matrix)\" -- from matrix\n"
                    "M2HELP2|METHOD_BEGIN=ideal(Matrix)\n"
                    "M2HELP2|METHOD_HEADER=ideal(Matrix) -- from matrix\n"
                    "M2HELP2|METHOD_DESCRIPTION_BEGIN\n"
                    "Construct an ideal from generators.\n"
                    "M2HELP2|METHOD_DESCRIPTION_END\n"
                    "M2HELP2|METHOD_EXAMPLE_BEGIN\n"
                    "+----------------------+\n"
                    "|  o1 : Ideal          |\n"
                    "+----------------------+\n"
                    "M2HELP2|METHOD_EXAMPLE_END\n"
                    "M2HELP2|METHOD_END\n"
                ),
            },
        ]

        objects, relations, index = normalize(records)
        object_by_id = {item["id"]: item for item in objects["objects"]}
        object_ids = {item["id"] for item in objects["objects"]}

        self.assertIn("core::type::Matrix", object_ids)
        self.assertIn("core::type::Module", object_ids)
        self.assertIn("core::method::ideal(Matrix)", object_ids)

        function_obj = object_by_id["core::function::ideal"]
        method_obj = object_by_id["core::method::ideal(Matrix)"]
        self.assertNotIn("parent", function_obj)
        self.assertEqual(
            function_obj["function"]["inputs"],
            [
                {"type": "core::type::Matrix", "description": ""},
                {"type": "core::type::Module", "description": ""},
            ],
        )
        self.assertIn("ideal(Matrix)", function_obj["function"]["inputDescription"])
        self.assertEqual(function_obj["function"]["outputDescription"], "Example outputs: Ideal")
        self.assertEqual(function_obj["brief"], "make an ideal")
        self.assertEqual(method_obj["brief"], "from matrix")
        self.assertEqual(method_obj["description"], "Construct an ideal from generators.")
        self.assertEqual(method_obj["outputDescription"], "Example outputs: Ideal")

        relation_edges = relations["relations"]
        self.assertIn(
            {
                "from": "core::method::ideal(Matrix)",
                "to": "core::type::Matrix",
                "type": "input_type",
            },
            relation_edges,
        )

        reverse = index["reverse"]
        self.assertIn("core::method::ideal(Matrix)", reverse["core::type::Matrix"]["usableByMethods"])

    def test_classify_operator_kind(self) -> None:
        self.assertEqual(classify_kind("+", "MethodFunctionBinary", "Keyword"), "operator")
        self.assertEqual(classify_kind("and", "MethodFunctionBinary", "Keyword"), "operator")
        self.assertEqual(classify_kind("ideal", "MethodFunctionSingle", "Symbol"), "function")


if __name__ == "__main__":
    unittest.main()
