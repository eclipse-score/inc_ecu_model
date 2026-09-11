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

"""Behavior tests for collection-aware FIDL datatype resolution."""

from pathlib import Path
import unittest

from score.ecu_model.common.common_name_types import Identifier, QualifiedName
from score.ecu_model.data_types.data_type_definition import (
    StructDataType,
)
from score.parsers.franca_parser.model.fidl.fidl_file import (
    FIDLFileModel,
)
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)
from score.parsers.franca_parser.model.franca_file import (
    ImportedNamespace,
)
from score.parsers.franca_parser.transformer.resolver.fidl_datatype_resolver import (
    FIDLDataTypeResolver,
)


def qualified_name(value: str) -> QualifiedName:
    """Create a qualified Franca name from a readable dotted test value."""
    return QualifiedName(names=[Identifier(part) for part in value.split(".")])


def type_collection(name: str | None, *datatypes: StructDataType) -> TypeCollection:
    """Create a FIDL type collection containing the supplied definitions."""
    return TypeCollection(
        name=Identifier(name) if name is not None else None,
        datatypes=list(datatypes),
    )


def struct(name: str) -> StructDataType:
    """Create a minimal datatype definition for resolver behavior tests."""
    return StructDataType(name=Identifier(name))


class FIDLDataTypeResolverTest(unittest.TestCase):
    """Verify FIDL named and anonymous type collection resolution semantics."""

    def test_resolve_given_local_named_collection_reference_expect_declared_datatype(self) -> None:
        local_payload = struct("LocalPayload")
        local_types = type_collection("LocalTypes", local_payload)
        local_file = FIDLFileModel(
            file_path=Path("local.fidl"),
            namespace=qualified_name("example.local"),
            type_collections=[local_types],
        )

        resolved_datatype = FIDLDataTypeResolver({local_file.file_path: local_file}).resolve(
            qualified_name("LocalPayload"), local_file, local_types
        )

        self.assertIs(resolved_datatype, local_payload)

    def test_resolve_given_wildcard_import_expect_named_anonymous_and_overlap_references(self) -> None:
        shared_payload = struct("SharedPayload")
        shared_file = FIDLFileModel(
            file_path=Path("shared.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection("SharedTypes", shared_payload)],
        )
        anonymous_payload = struct("AnonymousPayload")
        anonymous_file = FIDLFileModel(
            file_path=Path("anonymous.fidl"),
            namespace=qualified_name("example.anonymous"),
            type_collections=[type_collection(None, anonymous_payload)],
        )
        wildcard_types = type_collection("WildcardTypes")
        wildcard_file = FIDLFileModel(
            file_path=Path("wildcard.fidl"),
            namespace=qualified_name("example.wildcard"),
            imported_files=[
                ImportedNamespace(shared_file.file_path, qualified_name("example.shared"), True),
                ImportedNamespace(anonymous_file.file_path, qualified_name("example.anonymous"), True),
            ],
            type_collections=[wildcard_types],
        )
        resolver = FIDLDataTypeResolver(
            {
                shared_file.file_path: shared_file,
                anonymous_file.file_path: anonymous_file,
                wildcard_file.file_path: wildcard_file,
            }
        )

        resolved_named = resolver.resolve(qualified_name("SharedTypes.SharedPayload"), wildcard_file, wildcard_types)
        resolved_full = resolver.resolve(
            qualified_name("example.shared.SharedTypes.SharedPayload"), wildcard_file, wildcard_types
        )
        resolved_overlap = resolver.resolve(
            qualified_name("shared.SharedTypes.SharedPayload"), wildcard_file, wildcard_types
        )
        resolved_anonymous = resolver.resolve(qualified_name("AnonymousPayload"), wildcard_file, wildcard_types)

        self.assertIs(resolved_named, shared_payload)
        self.assertIs(resolved_full, shared_payload)
        self.assertIs(resolved_overlap, shared_payload)
        self.assertIs(resolved_anonymous, anonymous_payload)

    def test_resolve_given_file_only_import_expect_target_package_forms(self) -> None:
        shared_payload = struct("SharedPayload")
        shared_file = FIDLFileModel(
            file_path=Path("shared.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection("SharedTypes", shared_payload)],
        )
        file_only_types = type_collection("FileOnlyTypes")
        file_only_file = FIDLFileModel(
            file_path=Path("file_only.fidl"),
            namespace=qualified_name("example.fileonly"),
            imported_files=[ImportedNamespace(shared_file.file_path, None)],
            type_collections=[file_only_types],
        )
        resolver = FIDLDataTypeResolver({shared_file.file_path: shared_file, file_only_file.file_path: file_only_file})

        resolved_short = resolver.resolve(qualified_name("SharedTypes.SharedPayload"), file_only_file, file_only_types)
        resolved_full = resolver.resolve(
            qualified_name("example.shared.SharedTypes.SharedPayload"), file_only_file, file_only_types
        )

        self.assertIs(resolved_short, shared_payload)
        self.assertIs(resolved_full, shared_payload)

    def test_resolve_given_equivalent_reference_forms_expect_one_declaration_not_ambiguity(self) -> None:
        shared_payload = struct("SharedPayload")
        shared_file = FIDLFileModel(
            file_path=Path("shared.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection("SharedTypes", shared_payload)],
        )
        root_types = type_collection("RootTypes")
        root_file = FIDLFileModel(
            file_path=Path("root.fidl"),
            namespace=qualified_name("example.root"),
            imported_files=[ImportedNamespace(shared_file.file_path, qualified_name("example.shared"), True)],
            type_collections=[root_types],
        )
        resolver = FIDLDataTypeResolver({shared_file.file_path: shared_file, root_file.file_path: root_file})

        resolved_datatype = resolver.resolve(
            qualified_name("example.shared.SharedTypes.SharedPayload"), root_file, root_types
        )

        self.assertIs(resolved_datatype, shared_payload)

    def test_resolve_given_matching_definitions_from_two_imports_expect_ambiguity_error(self) -> None:
        left_file = FIDLFileModel(
            file_path=Path("left.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection("SharedTypes", struct("SharedPayload"))],
        )
        right_file = FIDLFileModel(
            file_path=Path("right.fidl"),
            namespace=qualified_name("other.shared"),
            type_collections=[type_collection("SharedTypes", struct("SharedPayload"))],
        )
        root_types = type_collection("RootTypes")
        root_file = FIDLFileModel(
            file_path=Path("root.fidl"),
            namespace=qualified_name("example.root"),
            imported_files=[
                ImportedNamespace(left_file.file_path, qualified_name("example"), True),
                ImportedNamespace(right_file.file_path, qualified_name("other"), True),
            ],
            type_collections=[root_types],
        )
        resolver = FIDLDataTypeResolver(
            {left_file.file_path: left_file, right_file.file_path: right_file, root_file.file_path: root_file}
        )

        with self.assertRaisesRegex(ValueError, "Ambiguous datatype reference 'shared.SharedTypes.SharedPayload'"):
            resolver.resolve(qualified_name("shared.SharedTypes.SharedPayload"), root_file, root_types)

    def test_resolve_given_no_matching_definition_expect_contextual_error(self) -> None:
        root_types = type_collection("RootTypes")
        root_file = FIDLFileModel(
            file_path=Path("root.fidl"),
            namespace=qualified_name("example.root"),
            type_collections=[root_types],
        )
        resolver = FIDLDataTypeResolver({root_file.file_path: root_file})

        with self.assertRaisesRegex(ValueError, "Referenced datatype 'MissingPayload' in 'root.fidl' was not found"):
            resolver.resolve(qualified_name("MissingPayload"), root_file, root_types)


if __name__ == "__main__":
    unittest.main()
