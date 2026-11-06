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

import unittest

from pydantic import ValidationError

from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier


class TestIdentifier(unittest.TestCase):
    def test_accepts_a_valid_identifier(self) -> None:
        self.assertEqual(str(Identifier("_value2")), "_value2")

    def test_rejects_an_invalid_identifier(self) -> None:
        with self.assertRaisesRegex(ValidationError, "Invalid identifier 'with-dash'"):
            Identifier("with-dash")

    def test_rejects_a_qualified_name_as_an_identifier(self) -> None:
        with self.assertRaisesRegex(ValidationError, "Invalid identifier 'Customer.FullyQualifiedName'"):
            Identifier("Customer.FullyQualifiedName")

    def test_is_hashable_and_comparable_by_value(self) -> None:
        self.assertEqual(Identifier("Position"), Identifier("Position"))
        self.assertEqual(len({Identifier("Position"), Identifier("Position")}), 1)


class TestSelectableIdentifier(unittest.TestCase):
    def test_accepts_plain_and_colon_separated_identifiers(self) -> None:
        for value in ("query", "query:first", "_query2:_first3"):
            with self.subTest(value=value):
                identifier = SelectableIdentifier(value)
                self.assertEqual(identifier.as_str, value)
                self.assertEqual(str(identifier), value)

    def test_rejects_malformed_identifiers(self) -> None:
        for value in (
            "",
            ":first",
            "query:",
            "query::first",
            "query:a:b",
            "query:1",
            "1query",
            "with-dash",
            "a.b",
            "a:b\n",
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                SelectableIdentifier(value)

    def test_is_independent_of_identifier(self) -> None:
        self.assertFalse(issubclass(SelectableIdentifier, Identifier))
        self.assertNotEqual(SelectableIdentifier("query"), Identifier("query"))
        with self.assertRaises(ValidationError):
            Identifier("query:first")

    def test_is_frozen_hashable_and_comparable_by_value(self) -> None:
        identifier = SelectableIdentifier("query:first")
        self.assertEqual({identifier: "value"}[SelectableIdentifier("query:first")], "value")
        with self.assertRaises(ValidationError):
            identifier.root = "changed"


class TestQualifiedName(unittest.TestCase):
    def test_accepts_identifier_segments(self) -> None:
        qualified_name = QualifiedName((Identifier("com"), Identifier("example")))

        self.assertEqual(qualified_name.as_str, "com.example")

    def test_rejects_string_input(self) -> None:
        with self.assertRaises(ValidationError):
            QualifiedName("com.example")

    def test_renders_with_a_custom_separator(self) -> None:
        self.assertEqual(QualifiedName(("app", "geometry")).format("::"), "app::geometry")

    def test_is_empty_by_default(self) -> None:
        qualified_name = QualifiedName()

        self.assertEqual(str(qualified_name), "")

    def test_iterates_over_its_segments(self) -> None:
        self.assertEqual([str(segment) for segment in QualifiedName(("a", "b"))], ["a", "b"])

    def test_is_hashable_and_comparable_by_value(self) -> None:
        self.assertEqual(QualifiedName(("a", "b")), QualifiedName(("a", "b")))
        self.assertEqual(len({QualifiedName(("a", "b")), QualifiedName(("a", "b"))}), 1)


if __name__ == "__main__":
    unittest.main()
