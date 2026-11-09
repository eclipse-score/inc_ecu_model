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

"""Immutable, interned SOME/IP element layout configurations."""

from dataclasses import InitVar, dataclass, field
from enum import Enum
from typing import ClassVar


class ByteOrder(str, Enum):
    """Byte order used for serialized values."""

    BIG_ENDIAN = "BigEndian"
    LITTLE_ENDIAN = "LittleEndian"


class StringEncoding(str, Enum):
    """Encoding used for serialized strings."""

    UTF8 = "Utf8"
    UTF16 = "Utf16"


@dataclass(slots=True, frozen=True, eq=False)
class ElementLayout:
    """Store six wire-layout settings with a lossless, stable identifier."""

    byte_order: ByteOrder = ByteOrder.BIG_ENDIAN
    alignment_bits: int = 8
    vector_length_field_bytes: int = 4
    string_length_field_bytes: int = 4
    struct_length_field_bytes: int = 0
    string_encoding: StringEncoding = StringEncoding.UTF8
    force_direct_creation_without_the_use_of_the_builder: InitVar[bool] = field(default=True, kw_only=True, repr=False)
    layout_id: str = field(init=False)
    _instances: ClassVar[dict[str, "ElementLayout"]] = {}

    def __post_init__(self, force_direct_creation_without_the_use_of_the_builder: bool) -> None:
        """Reject direct construction and derive the identifier for factory calls."""
        if force_direct_creation_without_the_use_of_the_builder:
            raise RuntimeError("Direct creation without the builder is not allowed!")
        self._validate_key(self._layout_key())
        object.__setattr__(self, "layout_id", self._compute_hash_id())

    @staticmethod
    def _validate_key(key: tuple[object, ...]) -> None:
        """Require exact enum and integer types within the layout value domains."""
        byte_order, alignment_bits, vector_bytes, string_bytes, struct_bytes, encoding = key
        if type(byte_order) is not ByteOrder:
            raise TypeError("byte_order must be a ByteOrder")
        if type(encoding) is not StringEncoding:
            raise TypeError("string_encoding must be a StringEncoding")
        if type(alignment_bits) is not int:
            raise TypeError("alignment_bits must be an int")
        if alignment_bits not in {8, 16, 32, 64, 128}:
            raise ValueError("alignment_bits must be one of 8/16/32/64/128")
        for field_name, value in (
            ("vector_length_field_bytes", vector_bytes),
            ("string_length_field_bytes", string_bytes),
            ("struct_length_field_bytes", struct_bytes),
        ):
            if type(value) is not int:
                raise TypeError(f"{field_name} must be an int")
            if not 0 <= value <= 255:
                raise ValueError(f"{field_name} must be between 0 and 255")

    @classmethod
    def intern(
        cls,
        byte_order: ByteOrder = ByteOrder.BIG_ENDIAN,
        alignment_bits: int = 8,
        vector_length_field_bytes: int = 4,
        string_length_field_bytes: int = 4,
        struct_length_field_bytes: int = 0,
        string_encoding: StringEncoding = StringEncoding.UTF8,
    ) -> "ElementLayout":
        """Return the process-local shared instance for a validated configuration."""
        key = (
            byte_order,
            alignment_bits,
            vector_length_field_bytes,
            string_length_field_bytes,
            struct_length_field_bytes,
            string_encoding,
        )
        cls._validate_key(key)
        layout_id = cls._encode_key(key)
        if layout_id not in cls._instances:
            cls._instances[layout_id] = cls(*key, force_direct_creation_without_the_use_of_the_builder=False)
        return cls._instances[layout_id]

    @classmethod
    def find(cls, layout_id: str) -> "ElementLayout | None":
        """Look up a registered identifier without creating an instance."""
        return cls._instances.get(layout_id)

    def _compute_hash_id(self) -> str:
        """Encode the complete configuration as its layout identifier."""
        return self._encode_key(self._layout_key())

    @staticmethod
    def _encode_key(key: tuple[object, ...]) -> str:
        """Join stable enum values and integer spellings in field order."""
        return "_".join(value.value if isinstance(value, Enum) else str(value) for value in key)

    def _layout_key(self) -> tuple[ByteOrder, int, int, int, int, StringEncoding]:
        """Return all six configuration fields in identifier order."""
        return (
            self.byte_order,
            self.alignment_bits,
            self.vector_length_field_bytes,
            self.string_length_field_bytes,
            self.struct_length_field_bytes,
            self.string_encoding,
        )
