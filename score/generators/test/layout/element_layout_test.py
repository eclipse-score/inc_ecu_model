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

"""Verify layout identity, instance reuse, immutability, and validation."""

import unittest
from collections.abc import Callable
from dataclasses import FrozenInstanceError, fields
from enum import Enum

from score.generators.src.layout.element_layout import ByteOrder, ElementLayout, StringEncoding


class OtherEnum(str, Enum):
    """Provide matching string values with an incompatible enum type."""

    BIG_ENDIAN = "BigEndian"
    UTF8 = "Utf8"


class IntSubclass(int):
    """Distinguish exact integer validation from subclass acceptance."""


class ElementLayoutTest(unittest.TestCase):
    """Exercise the documented layout contract with an isolated registry."""

    def setUp(self) -> None:
        """Use a fresh registry and restore the original after each test."""
        original_registry = ElementLayout._instances
        ElementLayout._instances = {}
        self.addCleanup(setattr, ElementLayout, "_instances", original_registry)

    def _assert_rejected(self, field_name: str, value: object, error: type[Exception]) -> None:
        """Check both construction paths, including an already populated registry."""
        canonical = ElementLayout.intern()
        original_registry = ElementLayout._instances.copy()
        factories: tuple[Callable[..., ElementLayout], ...] = (ElementLayout.intern,)
        for factory in factories:
            with self.subTest(factory=factory, field=field_name, value=value):
                with self.assertRaisesRegex(error, field_name):
                    factory(**{field_name: value})
                self.assertEqual(ElementLayout._instances, original_registry)
                self.assertIs(ElementLayout.find(canonical.layout_id), canonical)

    def test_enum_values_are_stable_strings(self) -> None:
        """Enum values retain the documented identifier spellings."""
        self.assertEqual([value.value for value in ByteOrder], ["BigEndian", "LittleEndian"])
        self.assertEqual([value.value for value in StringEncoding], ["Utf8", "Utf16"])
        for value in (*ByteOrder, *StringEncoding):
            self.assertIsInstance(value, str)

    def test_default_configuration_identifier_and_interning(self) -> None:
        """Defaults produce the documented ID and equivalent calls share one object."""
        layout = ElementLayout.intern()
        self.assertIs(layout.byte_order, ByteOrder.BIG_ENDIAN)
        self.assertEqual(layout.alignment_bits, 8)
        self.assertEqual(layout.vector_length_field_bytes, 4)
        self.assertEqual(layout.string_length_field_bytes, 4)
        self.assertEqual(layout.struct_length_field_bytes, 0)
        self.assertIs(layout.string_encoding, StringEncoding.UTF8)
        self.assertEqual(layout.layout_id, "BigEndian_8_4_4_0_Utf8")
        self.assertEqual(ElementLayout._instances, {layout.layout_id: layout})
        self.assertFalse(next(item for item in fields(ElementLayout) if item.name == "layout_id").init)
        self.assertNotIn("_instances", {item.name for item in fields(ElementLayout)})
        self.assertIs(ElementLayout.intern(), layout)
        self.assertIs(ElementLayout.intern(ByteOrder.BIG_ENDIAN, 8, 4, 4, 0, StringEncoding.UTF8), layout)
        self.assertIs(
            ElementLayout.intern(
                string_encoding=StringEncoding.UTF8,
                struct_length_field_bytes=0,
                string_length_field_bytes=4,
                vector_length_field_bytes=4,
                alignment_bits=8,
                byte_order=ByteOrder.BIG_ENDIAN,
            ),
            layout,
        )
        self.assertEqual(len(ElementLayout._instances), 1)

    def test_nondefault_positional_configuration(self) -> None:
        """The factory retains positional field order, zero and three."""
        layout = ElementLayout.intern(ByteOrder.LITTLE_ENDIAN, 128, 3, 0, 255, StringEncoding.UTF16)
        self.assertEqual(layout.layout_id, "LittleEndian_128_3_0_255_Utf16")
        self.assertIs(ElementLayout.find(layout.layout_id), layout)

    def test_direct_construction_is_rejected(self) -> None:
        """Construction must go through the interning factory."""
        with self.assertRaisesRegex(RuntimeError, "Direct creation"):
            ElementLayout()
        with self.assertRaisesRegex(RuntimeError, "Direct creation"):
            ElementLayout(ByteOrder.LITTLE_ENDIAN, 128, 3, 0, 255, StringEncoding.UTF16)
        self.assertEqual(ElementLayout._instances, {})

    def test_each_configuration_field_contributes_to_identity(self) -> None:
        """Changing any field, including struct width and encoding, changes the key."""
        default = ElementLayout.intern()
        scenarios = (
            ("byte_order", ByteOrder.LITTLE_ENDIAN, "LittleEndian_8_4_4_0_Utf8"),
            ("alignment_bits", 16, "BigEndian_16_4_4_0_Utf8"),
            ("vector_length_field_bytes", 3, "BigEndian_8_3_4_0_Utf8"),
            ("string_length_field_bytes", 3, "BigEndian_8_4_3_0_Utf8"),
            ("struct_length_field_bytes", 3, "BigEndian_8_4_4_3_Utf8"),
            ("string_encoding", StringEncoding.UTF16, "BigEndian_8_4_4_0_Utf16"),
        )
        intern: Callable[..., ElementLayout] = ElementLayout.intern
        layouts = [default]
        for field_name, value, expected_id in scenarios:
            with self.subTest(field=field_name):
                layout = intern(**{field_name: value})
                self.assertEqual(layout.layout_id, expected_id)
                self.assertIsNot(layout, default)
                self.assertIs(intern(**{field_name: value}), layout)
                layouts.append(layout)
        self.assertEqual(len({layout.layout_id for layout in layouts}), 7)
        self.assertEqual(len(ElementLayout._instances), 7)

    def test_find_never_creates_or_registers_layouts(self) -> None:
        """Missing IDs remain absent before and after another layout is interned."""
        self.assertIsNone(ElementLayout.find("BigEndian_8_4_4_0_Utf8"))
        self.assertEqual(ElementLayout._instances, {})
        layout = ElementLayout.intern()
        self.assertIs(ElementLayout.find(layout.layout_id), layout)
        for missing_id in ("", "unknown_layout_id", "BigEndian_8_4_4_3_Utf8"):
            self.assertIsNone(ElementLayout.find(missing_id))
        self.assertEqual(ElementLayout._instances, {layout.layout_id: layout})

    def test_layout_is_frozen_and_slotted(self) -> None:
        """All instance fields, including the derived ID, are immutable."""
        for layout in (ElementLayout.intern(),):
            self.assertFalse(hasattr(layout, "__dict__"))
            for item in fields(ElementLayout):
                with self.subTest(field=item.name):
                    with self.assertRaises(FrozenInstanceError):
                        setattr(layout, item.name, None)
                    with self.assertRaises(FrozenInstanceError):
                        delattr(layout, item.name)
            self.assertEqual(layout.layout_id, "BigEndian_8_4_4_0_Utf8")

    def test_byte_order_requires_the_exact_enum(self) -> None:
        """Raw strings and foreign enums are rejected even when their values match."""
        for value in ("BigEndian", "LittleEndian", OtherEnum.BIG_ENDIAN, StringEncoding.UTF8, None, True, 0):
            self._assert_rejected("byte_order", value, TypeError)

    def test_string_encoding_requires_the_exact_enum(self) -> None:
        """Encoding validation preserves enum type information."""
        for value in ("Utf8", "Utf16", OtherEnum.UTF8, ByteOrder.BIG_ENDIAN, None, False, 0):
            self._assert_rejected("string_encoding", value, TypeError)

    def test_alignment_accepts_all_documented_values(self) -> None:
        """Packed and supported aligned layouts are accepted by both APIs."""
        for alignment in (8, 16, 32, 64, 128):
            with self.subTest(alignment=alignment):
                layout = ElementLayout.intern(alignment_bits=alignment)
                self.assertEqual(layout.alignment_bits, alignment)

    def test_alignment_rejects_other_values_and_nonexact_integers(self) -> None:
        """Unsupported alignments and bool or integer subclasses are rejected."""
        for value in (-8, 0, 1, 7, 9, 24, 256):
            self._assert_rejected("alignment_bits", value, ValueError)
        for value in (True, False, 8.0, "8", None, IntSubclass(8)):
            self._assert_rejected("alignment_bits", value, TypeError)

    def test_widths_accept_zero_three_and_unsigned_byte_boundaries(self) -> None:
        """Width validation retains the complete unsigned-byte domain."""
        intern: Callable[..., ElementLayout] = ElementLayout.intern
        for field_name in ("vector_length_field_bytes", "string_length_field_bytes", "struct_length_field_bytes"):
            for width in range(256):
                with self.subTest(field=field_name, width=width):
                    layout = intern(**{field_name: width})
                    self.assertEqual(getattr(layout, field_name), width)
                    self.assertIs(intern(**{field_name: width}), layout)

    def test_widths_reject_out_of_range_values_and_nonexact_integers(self) -> None:
        """Each width rejects invalid ranges and types through both APIs."""
        for field_name in ("vector_length_field_bytes", "string_length_field_bytes", "struct_length_field_bytes"):
            for value in (-1, 256, 1000):
                self._assert_rejected(field_name, value, ValueError)
            for value in (True, False, 3.0, "4", None, IntSubclass(4), ByteOrder.BIG_ENDIAN):
                self._assert_rejected(field_name, value, TypeError)


if __name__ == "__main__":
    unittest.main()
