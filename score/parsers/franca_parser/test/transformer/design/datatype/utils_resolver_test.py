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

from score.ecu_model.common.common_name_types import Identifier, QualifiedName
from score.parsers.franca_parser.transformer.resolver.utils_resolver import (
    matches_named_element_reference,
    matches_use_definition_reference,
)


def qualified_name(value: str) -> QualifiedName:
    """Create a qualified Franca name from a readable dotted test value."""
    return QualifiedName(names=[Identifier(part) for part in value.split(".")])


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


if __name__ == "__main__":
    unittest.main()
