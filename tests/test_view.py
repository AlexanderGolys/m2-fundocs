import unittest

from tools.m2_view import _format_method_report, build_show_payload, resolve_target, summarize


class ViewTests(unittest.TestCase):
    def test_summarize_counts_kinds_and_relations(self) -> None:
        objects = [
            {"id": "a", "kind": "function", "name": "ideal"},
            {"id": "b", "kind": "type", "name": "Matrix"},
            {"id": "c", "kind": "type", "name": "Module"},
        ]
        relations = [
            {"from": "a", "to": "b", "type": "uses"},
            {"from": "a", "to": "c", "type": "uses"},
            {"from": "b", "to": "c", "type": "parent_type"},
        ]
        result = summarize(objects, relations)
        self.assertEqual(result["objects"], 3)
        self.assertEqual(result["relations"], 3)
        self.assertEqual(result["kinds"]["type"], 2)
        self.assertEqual(result["relationTypes"]["uses"], 2)

    def test_resolve_target_prefers_id_then_name(self) -> None:
        by_id = {"core::function::ideal": {"id": "core::function::ideal", "name": "ideal"}}
        by_name = {"ideal": [{"id": "core::function::ideal", "name": "ideal"}]}

        from_id = resolve_target("core::function::ideal", by_id, by_name)
        from_name = resolve_target("ideal", by_id, by_name)

        self.assertEqual(from_id["id"], "core::function::ideal")
        self.assertEqual(from_name["id"], "core::function::ideal")

    def test_build_show_payload_includes_method_context(self) -> None:
        function_obj = {"id": "core::function::matrix", "kind": "function", "name": "matrix"}
        type_obj = {"id": "core::type::List", "kind": "type", "name": "List"}
        method_obj = {
            "id": "core::method::matrix(List)",
            "kind": "method",
            "name": "matrix(List)",
            "brief": "create matrix",
            "description": "method description",
            "examples": ["+--+\n|x|\n+--+"],
            "inputDescription": "takes list",
            "outputDescription": "returns matrix",
            "dispatch": {
                "function": "core::function::matrix",
                "inputs": ["core::type::List"],
                "outputs": [],
            },
        }
        by_id = {
            function_obj["id"]: function_obj,
            type_obj["id"]: type_obj,
            method_obj["id"]: method_obj,
        }
        relations = [{"from": function_obj["id"], "to": method_obj["id"], "type": "has_method"}]
        reverse = {method_obj["id"]: {"function": [function_obj["id"]]}}

        payload = build_show_payload(method_obj, by_id, relations, reverse)

        self.assertEqual(payload["object"]["id"], method_obj["id"])
        self.assertEqual(payload["methodContext"]["function"]["id"], function_obj["id"])
        self.assertEqual(payload["methodContext"]["inputTypes"][0]["id"], type_obj["id"])
        self.assertEqual(payload["methodContext"]["docs"]["brief"], "create matrix")
        self.assertEqual(payload["relations"]["reverseIndex"]["function"], [function_obj["id"]])

    def test_summarize_includes_mapping_statistics(self) -> None:
        objects = [
            {
                "id": "f",
                "kind": "function",
                "name": "matrix",
                "description": "function docs",
                "examples": ["ex"],
                "function": {"inputDescription": "in", "outputDescription": "out"},
            },
            {
                "id": "m",
                "kind": "method",
                "name": "matrix(List)",
                "description": "method docs",
                "examples": [],
                "inputDescription": "method in",
                "outputDescription": "method out",
            },
        ]
        relations = []
        result = summarize(objects, relations)
        self.assertEqual(result["mapped"]["description"], 2)
        self.assertEqual(result["mapped"]["examples"], 1)
        self.assertEqual(result["mapped"]["functionInputDescription"], 1)
        self.assertEqual(result["mapped"]["methodInputDescription"], 1)

    def test_format_method_report_contains_method_docs(self) -> None:
        payload = {
            "object": {"id": "core::method::matrix(List)", "name": "matrix(List)"},
            "methodContext": {
                "function": {"id": "core::function::matrix"},
                "inputTypes": [{"name": "List"}],
                "outputTypes": [],
                "docs": {
                    "brief": "create matrix",
                    "description": "Builds a matrix.",
                    "examples": ["+--+\n|x|\n+--+"],
                    "inputDescription": "takes list",
                    "outputDescription": "returns matrix",
                },
            },
        }
        report = _format_method_report(payload)
        self.assertIn("Method: core::method::matrix(List)", report)
        self.assertIn("Brief: create matrix", report)
        self.assertIn("Input types: List", report)
        self.assertIn("Examples (1):", report)


if __name__ == "__main__":
    unittest.main()
