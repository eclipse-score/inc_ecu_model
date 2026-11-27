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

import unittest
from pathlib import Path

from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.identifier import Identifier, QualifiedName
from score.ecu_model.data_types.struct import StructDataType
from score.parsers.franca_parser.model.fidl.fidl_file import (
    FIDLFileModel,
)
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)
from score.parsers.franca_parser.model.franca_file import (
    FrancaFileModel,
    ImportedNamespace,
)
from score.parsers.franca_parser.transformer.resolver.fidl_datatype_resolver import (
    FIDLDataTypeResolver,
    PendingDatatypeReference,
)
from score.parsers.franca_parser.transformer.resolver.utils_resolver import select_single_match


def qualified_name(value: str) -> QualifiedName:
    """Create a qualified Franca name from a readable dotted test value."""
    return QualifiedName(tuple(Identifier(part) for part in value.split(".")))


def type_collection(name: str | None, *datatypes: StructDataType) -> TypeCollection:
    """Create a FIDL type collection containing the supplied definitions."""
    return TypeCollection(
        name=Identifier(name) if name is not None else None,
        datatypes=list(datatypes),
    )


def struct(name: str) -> StructDataType:
    """Create a minimal datatype definition for resolver behavior tests."""
    return StructDataType(name=name, source_kind=DataTypeSource.FRANCA)


class FIDLDataTypeResolverTest(unittest.TestCase):
    """Verify FIDL named and anonymous type collection resolution semantics."""

    def test_file_model_allows_multiple_anonymous_type_collections(self) -> None:
        first = struct("First")
        second = struct("Second")
        file_model = FIDLFileModel(
            file_path=Path("anonymous.fidl"),
            namespace=qualified_name("example"),
            type_collections=[type_collection(None), type_collection(None, first), type_collection(None, second)],
        )

        self.assertEqual(len(file_model.type_collections), 3)
        self.assertIs(file_model.lookup_datatype_in_tc("example.First"), first)
        self.assertIs(file_model.lookup_datatype_in_tc("example.Second"), second)

    def test_resolve_local_given_local_named_collection_reference_expect_declared_datatype(self) -> None:
        local_payload = struct("LocalPayload")
        local_types = type_collection("LocalTypes", local_payload)
        local_file = FIDLFileModel(
            file_path=Path("local.fidl"),
            namespace=qualified_name("example.local"),
            type_collections=[local_types],
        )

        resolved_datatype = FIDLDataTypeResolver({local_file.file_path: local_file}).resolve_local(
            qualified_name("LocalPayload"), local_file, local_types
        )

        self.assertIs(resolved_datatype, local_payload)

    def test_resolve_local_given_other_named_collection_requires_collection_name(self) -> None:
        referenced_payload = struct("SharedPayload")
        primary_types = type_collection("PrimaryTypes")
        secondary_types = type_collection("SecondaryTypes", referenced_payload)
        local_file = FIDLFileModel(
            file_path=Path("local.fidl"),
            namespace=qualified_name("example.local"),
            type_collections=[primary_types, secondary_types],
        )
        resolver = FIDLDataTypeResolver({local_file.file_path: local_file})

        resolved_datatype = resolver.resolve_local(
            qualified_name("SecondaryTypes.SharedPayload"), local_file, primary_types
        )

        self.assertIs(resolved_datatype, referenced_payload)
        resolved_fully_qualified = resolver.resolve_local(
            qualified_name("example.local.SecondaryTypes.SharedPayload"), local_file, primary_types
        )
        self.assertIs(resolved_fully_qualified, referenced_payload)
        self.assertIsNone(resolver.resolve_local(qualified_name("SharedPayload"), local_file, primary_types))

    def test_resolve_local_given_other_anonymous_collection_allows_short_name(self) -> None:
        anonymous_payload = struct("AnonymousPayload")
        named_types = type_collection("NamedTypes")
        anonymous_types = type_collection(None, anonymous_payload)
        local_file = FIDLFileModel(
            file_path=Path("local.fidl"),
            namespace=qualified_name("example.local"),
            type_collections=[named_types, anonymous_types],
        )

        resolved_datatype = FIDLDataTypeResolver({local_file.file_path: local_file}).resolve_local(
            qualified_name("AnonymousPayload"), local_file, named_types
        )

        self.assertIs(resolved_datatype, anonymous_payload)

    def test_resolve_imports_given_wildcard_import_expect_named_anonymous_and_overlap_references(self) -> None:
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

        resolved_named = resolver.resolve_imports(qualified_name("SharedTypes.SharedPayload"), wildcard_file)
        resolved_full = resolver.resolve_imports(
            qualified_name("example.shared.SharedTypes.SharedPayload"), wildcard_file
        )
        resolved_overlap = resolver.resolve_imports(qualified_name("shared.SharedTypes.SharedPayload"), wildcard_file)
        resolved_anonymous = resolver.resolve_imports(qualified_name("AnonymousPayload"), wildcard_file)

        self.assertIs(resolved_named, shared_payload)
        self.assertIs(resolved_full, shared_payload)
        self.assertIs(resolved_overlap, shared_payload)
        self.assertIs(resolved_anonymous, anonymous_payload)

    def test_resolve_imports_given_file_only_import_expect_target_package_forms(self) -> None:
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

        resolved_short = resolver.resolve_imports(qualified_name("SharedTypes.SharedPayload"), file_only_file)
        resolved_full = resolver.resolve_imports(
            qualified_name("example.shared.SharedTypes.SharedPayload"), file_only_file
        )

        self.assertIs(resolved_short, shared_payload)
        self.assertIs(resolved_full, shared_payload)

    def test_resolve_imports_given_import_targeting_named_collection_requires_collection_name(self) -> None:
        shared_payload = struct("SharedPayload")
        shared_file = FIDLFileModel(
            file_path=Path("shared.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection("SharedTypes", shared_payload)],
        )

        for is_wildcard in (True, False):
            with self.subTest(is_wildcard=is_wildcard):
                root_types = type_collection("RootTypes")
                root_file = FIDLFileModel(
                    file_path=Path("root.fidl"),
                    namespace=qualified_name("example.root"),
                    imported_files=[
                        ImportedNamespace(
                            shared_file.file_path,
                            qualified_name("example.shared.SharedTypes"),
                            is_wildcard,
                        )
                    ],
                    type_collections=[root_types],
                )
                resolver = FIDLDataTypeResolver({shared_file.file_path: shared_file, root_file.file_path: root_file})

                self.assertIsNone(resolver.resolve_imports(qualified_name("SharedPayload"), root_file))
                self.assertIs(
                    resolver.resolve_imports(qualified_name("SharedTypes.SharedPayload"), root_file),
                    shared_payload,
                )

    def test_resolve_imports_given_equivalent_reference_forms_expect_one_declaration_not_ambiguity(self) -> None:
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

        resolved_datatype = resolver.resolve_imports(
            qualified_name("example.shared.SharedTypes.SharedPayload"), root_file
        )

        self.assertIs(resolved_datatype, shared_payload)

    def test_resolve_imports_given_matching_definitions_from_two_imports_expect_ambiguity_error(self) -> None:
        left_payload = struct("SharedPayload")
        right_payload = struct("SharedPayload")
        left_file = FIDLFileModel(
            file_path=Path("left.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection("SharedTypes", left_payload)],
        )
        right_file = FIDLFileModel(
            file_path=Path("right.fidl"),
            namespace=qualified_name("other.shared"),
            type_collections=[type_collection("SharedTypes", right_payload)],
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
            resolver.resolve_imports(qualified_name("shared.SharedTypes.SharedPayload"), root_file)

    def test_resolve_pending_imports_given_no_matching_definition_expect_contextual_error(self) -> None:
        root_types = type_collection("RootTypes")
        root_file = FIDLFileModel(
            file_path=Path("root.fidl"),
            namespace=qualified_name("example.root"),
            type_collections=[root_types],
        )
        resolver = FIDLDataTypeResolver({root_file.file_path: root_file})
        pending = PendingDatatypeReference(
            reference=qualified_name("MissingPayload"),
            bind=lambda datatype: self.fail("An unresolved reference must not be bound"),
            owning_declaration=root_types,
            owning_collection=root_types,
        )
        unresolved = resolver.resolve_local_references([pending], root_file)

        self.assertEqual(unresolved, [pending])

        with self.assertRaisesRegex(ValueError, "Referenced datatype 'MissingPayload' in 'root.fidl' was not found"):
            resolver.resolve_pending_imports(unresolved)

    def test_resolve_local_prefers_owning_collection_over_other_local_and_imported_scopes(self) -> None:
        local_payload = struct("Payload")
        local_types = type_collection("LocalTypes", local_payload)
        shared_file = FIDLFileModel(
            file_path=Path("shared.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection(None, struct("Payload"))],
        )
        local_file = FIDLFileModel(
            file_path=Path("local.fidl"),
            namespace=qualified_name("example.local"),
            type_collections=[local_types, type_collection(None, struct("Payload"))],
            imported_files=[ImportedNamespace(shared_file.file_path, None)],
        )
        resolver = FIDLDataTypeResolver({shared_file.file_path: shared_file, local_file.file_path: local_file})

        self.assertIs(resolver.resolve_local(qualified_name("Payload"), local_file, local_types), local_payload)

    def test_resolve_imports_deduplicates_declarations_reached_through_different_imports(self) -> None:
        payload = struct("Payload")
        shared_file = FIDLFileModel(
            file_path=Path("shared.fidl"),
            namespace=qualified_name("example.shared"),
            type_collections=[type_collection("Types", payload)],
        )
        local_file = FIDLFileModel(
            file_path=Path("local.fidl"),
            namespace=qualified_name("example.local"),
            imported_files=[
                ImportedNamespace(shared_file.file_path, qualified_name("example.shared"), True),
                ImportedNamespace(shared_file.file_path, None),
            ],
        )

        self.assertIs(
            FIDLDataTypeResolver({shared_file.file_path: shared_file}).resolve_imports(
                qualified_name("Types.Payload"), local_file
            ),
            payload,
        )

    def test_select_single_match_required_without_definition_raises_contextual_error(self) -> None:
        root_file = FIDLFileModel(
            file_path=Path("root.fidl"),
            namespace=qualified_name("example.root"),
        )

        with self.assertRaisesRegex(ValueError, "Referenced datatype 'MissingPayload' in 'root.fidl' was not found"):
            select_single_match(
                [],
                not_found_message=f"Referenced datatype 'MissingPayload' in '{root_file.file_path}' was not found",
                ambiguous_message="Ambiguous datatype reference 'MissingPayload'",
                required=True,
            )

    def test_resolve_imports_skips_non_fidl_files(self) -> None:
        imported_path = Path("deployment.fdepl")
        imported_file = FrancaFileModel(file_path=imported_path, namespace=qualified_name("example.deployment"))
        root_types = type_collection("RootTypes")
        root_file = FIDLFileModel(
            file_path=Path("root.fidl"),
            namespace=qualified_name("example.root"),
            imported_files=[ImportedNamespace(imported_path, qualified_name("example.deployment"))],
            type_collections=[root_types],
        )
        resolver = FIDLDataTypeResolver({imported_path: imported_file, root_file.file_path: root_file})

        self.assertIsNone(resolver.resolve_imports(qualified_name("MissingPayload"), root_file))


if __name__ == "__main__":
    unittest.main()
