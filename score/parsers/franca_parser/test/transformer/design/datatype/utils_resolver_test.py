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

"""Tests for shared Franca qualified-name resolution utilities."""

import unittest

from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.parsers.franca_parser.transformer.resolver.utils_resolver import (
    matches_named_element_reference,
    matches_use_definition_reference,
    resolve_from_local,
    select_single_match,
)


def qualified_name(value: str) -> QualifiedName:
    """Create a qualified Franca name from a readable dotted test value."""
    return QualifiedName(tuple(Identifier(part) for part in value.split(".")))


class UtilsResolverTest(unittest.TestCase):
    """Verify reusable legacy-compatible Franca name matching rules."""

    def test_matches_use_definition_reference_given_legacy_reference_forms_expect_match(self) -> None:
        definition_name = qualified_name("d.tc")
        definition_namespace = qualified_name("a.b.c")

        self.assertTrue(
            matches_use_definition_reference(
                qualified_name("d.tc"),
                definition_name,
                definition_namespace,
                qualified_name("a.b.c"),
            )
        )
        self.assertTrue(
            matches_use_definition_reference(
                qualified_name("c.d.tc"),
                definition_name,
                definition_namespace,
                qualified_name("a.b"),
            )
        )
        self.assertTrue(
            matches_use_definition_reference(
                qualified_name("a.b.c.d.tc"),
                definition_name,
                definition_namespace,
                qualified_name("a.b.c"),
            )
        )
        self.assertTrue(
            matches_use_definition_reference(
                qualified_name("b.c.d.tc"),
                definition_name,
                definition_namespace,
                qualified_name("a.b"),
            )
        )

    def test_matches_named_element_reference_given_identifier_name_expect_match(self) -> None:
        matches = matches_named_element_reference(
            qualified_name("b.c.Element"),
            Identifier("Element"),
            qualified_name("a.b.c"),
            qualified_name("a.b"),
        )

        self.assertTrue(matches)

    def test_matches_named_element_reference_requires_namespace_coverage(self) -> None:
        for reference, expected in (
            ("Element", False),
            ("c.Element", True),
            ("b.c.Element", True),
            ("a.b.c.Element", True),
            ("other.Element", False),
        ):
            with self.subTest(reference=reference):
                self.assertEqual(
                    matches_named_element_reference(
                        qualified_name(reference),
                        Identifier("Element"),
                        qualified_name("a.b.c"),
                        qualified_name("a.b"),
                    ),
                    expected,
                )

    def test_resolve_from_local_matches_only_the_supplied_scope(self) -> None:
        element = Identifier("Element")
        matches = resolve_from_local(
            qualified_name("c.Element"),
            [element, Identifier("Other")],
            qualified_name("a.b.c"),
            lambda name: name,
            imported_namespace=qualified_name("a.b"),
        )

        self.assertEqual(len(matches), 1)
        self.assertIs(matches[0], element)
        self.assertEqual(
            resolve_from_local(qualified_name("c.Element"), [element], qualified_name("a.b.other"), lambda name: name),
            [],
        )

    def test_select_single_match_deduplicates_by_identity_not_equality(self) -> None:
        element = Identifier("Element")
        other_element = Identifier("Element")
        self.assertEqual(element, other_element)
        self.assertIs(
            select_single_match(
                [element, element], not_found_message="Missing element", ambiguous_message="Ambiguous element"
            ),
            element,
        )
        with self.assertRaisesRegex(ValueError, "Ambiguous element"):
            select_single_match(
                [element, other_element],
                not_found_message="Missing element",
                ambiguous_message="Ambiguous element",
            )

    def test_select_single_match_allows_absent_optional_reference(self) -> None:
        self.assertIsNone(
            select_single_match([], not_found_message="Missing element", ambiguous_message="Ambiguous element")
        )


if __name__ == "__main__":
    unittest.main()
