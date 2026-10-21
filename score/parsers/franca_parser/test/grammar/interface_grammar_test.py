# *******************************************************************************
# Copyright (c) 2026 Contributors to the Eclipse Foundation
#
# See the NOTICE file(s) distributed with this work for additional
# information regarding copyright ownership.
#
# This program and the accompanying materials are made available under the
# terms of the Apache License Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0
#
# SPDX-License-Identifier: Apache-2.0
# *******************************************************************************

"""Parse-only coverage of the reference Franca interface grammar."""

import unittest
from pathlib import Path

from lark import Lark
from lark.exceptions import UnexpectedInput

TEST_DATA_DIRECTORY = Path(__file__).parent / "test_data"
GRAMMAR_DIRECTORY = Path(__file__).parents[2] / "grammar"


class InterfaceGrammarTest(unittest.TestCase):
    """Exercise the grammar without parser orchestration or model transformation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.parser = Lark(
            (GRAMMAR_DIRECTORY / "franca_fidl.lark").read_text(encoding="utf-8"),
            parser="lalr",
            import_paths=[GRAMMAR_DIRECTORY],
        )

    def test_complete_interface_grammar_accepts_reference_syntax(self) -> None:
        tree = self.parser.parse((TEST_DATA_DIRECTORY / "complete_interface.fidl").read_text(encoding="utf-8"))
        rules = {str(node.data) for node in tree.iter_subtrees()}
        self.assertTrue(
            {
                "fi_interface",
                "fi_interface_extends",
                "fi_interface_manages",
                "f_version",
                "fi_attribute",
                "access_q_no_read",
                "access_q_readonly",
                "access_q_no_subscriptions",
                "fi_method",
                "fi_fire_and_forget",
                "fi_method_input",
                "fi_method_output",
                "fi_method_error",
                "fi_enumeration_type_body",
                "fi_broadcast",
                "fi_broadcast_output",
                "fi_contract",
                "fi_state_graph",
                "fi_states",
                "fi_transition",
                "call",
                "respond",
                "error",
                "signal",
                "set",
                "update",
                "fi_assignment",
                "fi_if_statement",
                "fi_constant_def",
            }.issubset(rules)
        )
        selectors = list(tree.find_data("fi_id_with_selector"))
        self.assertTrue(any(len(node.children) == 2 for node in selectors))

    def test_complex_types_and_initializers_are_accepted(self) -> None:
        self.parser.parse((TEST_DATA_DIRECTORY / "complex_interface.fidl").read_text(encoding="utf-8"))

    def test_empty_interface_and_optional_members(self) -> None:
        self.parser.parse("package example interface Empty {}")
        self.parser.parse(
            "package example interface Minimal { method ping {} broadcast pulse {} attribute Boolean enabled }"
        )

    def test_selective_broadcast_flag_is_preserved_in_grammar_order(self) -> None:
        for selective in (False, True):
            with self.subTest(selective=selective):
                flag = "selective" if selective else ""
                tree = self.parser.parse(
                    f"package example interface API {{ broadcast changed {flag} {{ out {{ UInt32 value }} }} }}"
                )
                broadcast = next(tree.find_data("fi_broadcast"))
                expected = ["fi_id_with_selector"]
                if selective:
                    expected.append("fi_selective")
                expected.append("fi_broadcast_output")
                self.assertEqual([str(child.data) for child in broadcast.children], expected)

    def test_reference_grammar_literal_filtering_is_unchanged(self) -> None:
        cases = [
            ("typedef Alias is UInt32", "public typedef Alias is UInt32", "fi_type_def"),
            ("struct Payload {}", "struct Payload polymorphic {}", "fi_struct_type"),
            ("attribute Integer(minInt,10) value", "attribute Integer(10,maxInt) value", "fi_integer_interval"),
        ]
        for plain, qualified, rule in cases:
            with self.subTest(rule=rule):
                first = self.parser.parse("package example interface API { " + plain + " }")
                second = self.parser.parse("package example interface API { " + qualified + " }")
                self.assertEqual(next(first.find_data(rule)), next(second.find_data(rule)))

    def test_invalid_interface_is_rejected(self) -> None:
        with self.assertRaises(UnexpectedInput):
            self.parser.parse("package example interface Invalid { broadcast event { in { UInt32 x } } }")


if __name__ == "__main__":
    unittest.main()
