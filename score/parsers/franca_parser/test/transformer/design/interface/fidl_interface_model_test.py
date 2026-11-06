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

"""FIDL interface conversion directly into shared ECU models."""

import unittest
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lark import Tree
from lark.exceptions import VisitError

from score.ecu_model.common.version import Version
from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.model import ModelRegistry
from score.parsers.franca_parser.model.fidl.fidl_file import FIDLFileModel
from score.parsers.franca_parser.model.fidl.type_collection import TypeCollection
from score.parsers.franca_parser.model.franca_file import FrancaTransformationContext
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.fidl_transformer import FIDLTransformer
from score.parsers.franca_parser.transformer.file_graph_transformer import FrancaFileGraphTransformer

TEST_DATA_DIRECTORY = Path(__file__).parent / "test_data"


class FIDLInterfaceModelTest(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def transform(self, path: Path) -> object:
        graph = FrancaFileGraphTransformer(FrancaParser([path], []).parse_files())
        graph.transform_files()
        return graph.transformed_files[path.resolve()]

    def test_interface_members_and_datatypes_are_shared_models(self) -> None:
        model = self.transform(TEST_DATA_DIRECTORY / "shared_models.fidl")
        interface = model.interfaces[1]
        self.assertIsInstance(interface, InterfaceDefinition)
        self.assertNotIn(SelectableIdentifier("ping"), interface.methods)
        self.assertEqual(interface.namespace.as_str, "example.interfaces")
        self.assertEqual(str(interface.version), "1.2.0")
        self.assertIsInstance(interface.datatypes[0], StructDataType)
        payload, errors = interface.datatypes
        self.assertEqual(payload.namespace.as_str, "example.interfaces.API")
        method = interface.methods[SelectableIdentifier("query:first")]
        self.assertIs(method.inputs[0].data_type, payload)
        self.assertIs(method.error_return_codes, errors)
        self.assertEqual(method.outputs[0].data_type.dimension_max, 25)
        self.assertIs(interface.attributes[next(iter(interface.attributes))].data_type, payload)
        self.assertFalse(next(iter(interface.attributes.values())).has_setter)
        self.assertTrue(interface.methods[SelectableIdentifier("notify")].fire_and_forget)
        self.assertIs(interface.broadcasts[SelectableIdentifier("changed")].outputs[0].data_type, payload)
        self.assertIs(payload.fields[0].data_type, PrimitiveDataType.UINT32)
        self.assertTrue(
            all(
                not type(element).__module__.startswith("score.parsers.franca_parser.model")
                for element in ModelRegistry.elements.values()
            )
        )

    def test_attribute_references_are_registered_under_attribute_owner(self) -> None:
        for inline_array in (False, True):
            with self.subTest(inline_array=inline_array):
                transformer = FIDLTransformer(
                    {}, FrancaTransformationContext(file_path=Path("attribute.fidl"), imported_files=[])
                )
                reference = QualifiedName((Identifier("Payload"),))
                data_type = (
                    ArrayDataType(source_kind=DataTypeSource.FRANCA, data_type=reference, is_inline=True)
                    if inline_array
                    else reference
                )
                declaration = DataTypeField(name=Identifier("value"), data_type=data_type)

                attribute = transformer.fi_attribute(declaration, set())

                references = transformer._pending_datatype_references_by_declaration
                self.assertEqual(set(references), {id(attribute)})
                self.assertEqual(len(references[id(attribute)]), 1)
                pending = references[id(attribute)][0]
                self.assertIs(pending.owning_declaration, attribute)
                self.assertEqual(pending.reference, reference)
                self.assertEqual(transformer.pending_datatype_references, [])

                payload = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
                pending.bind(payload)

                if inline_array:
                    self.assertIs(attribute.data_type, data_type)
                    self.assertIs(attribute.data_type.data_type, payload)
                else:
                    self.assertIs(attribute.data_type, payload)

    def test_model_constraints_are_not_relaxed_for_franca(self) -> None:
        cases = [
            ("interface API {}", "requires an explicit version"),
            ("interface API { version { major 0 minor 0 } }", "greater than zero"),
            ("interface API { version { major 1 minor 0 } method query { error { FAILED } } }", "Anonymous"),
            ("interface API { version { major 1 minor 0 } method query { in { Integer(0,100) value } } }", "intervals"),
        ]
        for source, message in cases:
            with self.subTest(source=source), TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.fidl"
                path.write_text("package example " + source, encoding="utf-8")
                with self.assertRaisesRegex((ValueError, VisitError), message):
                    self.transform(path)

    def test_primitive_types_literals_and_escaped_keyword_names_transform(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "primitives.fidl"
            path.write_text(
                """package example
                interface ^interface {
                    version { major 1 minor 0 }
                    struct PrimitiveValues {
                        Boolean boolean_value
                        Float float_value
                        Double double_value
                        UInt64 uint64_value
                        Int8 int8_value
                        Int16 int16_value
                        Int64 int64_value
                    }
                    enumeration States { FIRST, SECOND, THIRD = 5, FOURTH }
                    const Float float_constant = 1.25f
                    const Double double_constant = 2.5d
                }
                """,
                encoding="utf-8",
            )

            interface = self.transform(path).interfaces[0]

        self.assertEqual(interface.name.as_str, "interface")
        self.assertEqual(
            [field.data_type for field in interface.datatypes[0].fields],
            [
                PrimitiveDataType.BOOL,
                PrimitiveDataType.FLOAT,
                PrimitiveDataType.DOUBLE,
                PrimitiveDataType.UINT64,
                PrimitiveDataType.INT8,
                PrimitiveDataType.INT16,
                PrimitiveDataType.INT64,
            ],
        )
        self.assertEqual([value.value for value in interface.datatypes[1].values], [0, 1, 5, 6])

    def test_duplicate_interface_and_type_collection_names_are_rejected(self) -> None:
        cases = [
            ("interface API { version { major 1 minor 0 } } interface API { version { major 1 minor 0 } }",),
            ("typeCollection Types {} typeCollection Types {}",),
        ]
        for (declarations,) in cases:
            with self.subTest(declarations=declarations), TemporaryDirectory() as directory:
                path = Path(directory) / "duplicate.fidl"
                path.write_text("package example " + declarations, encoding="utf-8")
                with self.assertRaisesRegex((ValueError, VisitError), "Duplicate ID"):
                    self.transform(path)

    def test_file_model_rejects_non_datatypes_and_duplicate_datatype_identities(self) -> None:
        namespace = QualifiedName((Identifier("example"),))
        with self.assertRaisesRegex(TypeError, "may only contain datatype definitions"):
            FIDLFileModel(
                file_path=Path("invalid.fidl"),
                namespace=namespace,
                type_collections=[TypeCollection(name=None, datatypes=[object()])],
            )

        datatype = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        with self.assertRaisesRegex(ValueError, "Duplicate datatype identity 'example.Payload'"):
            FIDLFileModel(
                file_path=Path("duplicate.fidl"),
                namespace=namespace,
                type_collections=[
                    TypeCollection(name=None, datatypes=[datatype]),
                    TypeCollection(name=None, datatypes=[datatype]),
                ],
            )

    def test_interface_sections_are_collected_across_ignored_declarations(self) -> None:
        for annotation in ("", "<** @description: API **>"):
            for header in ("", "extends Base", "manages Managed", "extends Base manages Managed"):
                with self.subTest(annotation=annotation, header=header), TemporaryDirectory() as directory:
                    ModelRegistry.elements.clear()
                    path = Path(directory) / "sections.fidl"
                    path.write_text(
                        "package example "
                        "interface Base { version { major 1 minor 0 } } "
                        f"{annotation} interface API {header} {{ "
                        "version { major 1 minor 2 } "
                        "const UInt32 Limit = 42 "
                        "method query { out { Payload result } } "
                        "contract { PSM { initial Idle state Idle {} } } "
                        "const UInt32 OtherLimit = 7 "
                        "struct Payload { UInt32 value } }",
                        encoding="utf-8",
                    )
                    base, interface = self.transform(path).interfaces
                    self.assertEqual(interface.name.as_str, "API")
                    self.assertEqual(interface.description, "@description: API " if annotation else "")
                    self.assertEqual(base.description, "")
                    self.assertEqual(str(interface.version), "1.2.0")
                    self.assertFalse(hasattr(interface, "base"))
                    self.assertEqual([datatype.name.as_str for datatype in interface.datatypes], ["Payload"])
                    self.assertIs(
                        interface.methods[SelectableIdentifier("query")].outputs[0].data_type,
                        interface.datatypes[0],
                    )

    def test_callbacks_collect_supported_elements_independently_of_order(self) -> None:
        transformer = FIDLTransformer(
            {}, FrancaTransformationContext(file_path=Path("callbacks.fidl"), imported_files=[])
        )
        ignored = Tree("unsupported", [])
        input_field = DataTypeField(name="input", data_type=PrimitiveDataType.UINT32)
        output_field = DataTypeField(name="output", data_type=PrimitiveDataType.STRING)
        error = QualifiedName((Identifier("Errors"),))
        method = transformer.fi_method(
            ignored,
            ("outputs", [output_field]),
            error,
            Tree("fi_error_comment", [Tree("f_annotation_block", ["Error details"])]),
            SelectableIdentifier("query"),
            ("inputs", [input_field]),
            Tree("f_annotation_block", ["Method details"]),
        )
        self.assertEqual(method.description, "Method details")
        self.assertEqual(method.error_description, "Error details")
        self.assertIs(method.error_return_codes, error)
        self.assertEqual(method.inputs, [input_field])
        self.assertEqual(method.outputs, [output_field])

        broadcast = transformer.fi_broadcast(
            True,
            ("outputs", [output_field]),
            ignored,
            SelectableIdentifier("changed"),
            Tree("f_annotation_block", ["Broadcast details"]),
        )
        self.assertTrue(broadcast.selective)
        self.assertEqual(broadcast.outputs, [output_field])
        self.assertEqual(broadcast.description, "Broadcast details")

        attribute = transformer.fi_attribute(
            {"readonly", "noSubscriptions"},
            ignored,
            Tree("f_annotation_block", ["Attribute details"]),
            DataTypeField(name="value", data_type=PrimitiveDataType.UINT32),
        )
        self.assertFalse(attribute.has_setter)
        self.assertFalse(attribute.subscribable)
        self.assertEqual(attribute.description, "Attribute details")

        version = Version(major=1, minor=2, patch=0)
        interface = transformer.fi_interface(
            ignored,
            broadcast,
            version,
            attribute,
            method,
            Identifier("API"),
            Tree("f_annotation_block", ["Interface details"]),
        )
        self.assertEqual(interface.name.as_str, "API")
        self.assertIs(interface.version, version)
        self.assertEqual(interface.description, "Interface details")
        self.assertIs(interface.methods[method.name], method)
        self.assertIs(interface.broadcasts[broadcast.name], broadcast)
        self.assertIs(interface.attributes[attribute.name], attribute)

    def test_method_sections_are_collected_from_optional_elements(self) -> None:
        description = "@description: First  line\n    Second\tline\n\n    @author: Example Author\n"
        error_description = "@description: Error  details\n    @custom-tag: More\ttext\n"
        for annotated, has_input, has_output, error_kind, fire_and_forget in product(
            (False, True), (False, True), (False, True), ("none", "plain", "annotated"), (False, True)
        ):
            if fire_and_forget and (has_output or error_kind != "none"):
                continue
            with (
                self.subTest(
                    annotated=annotated,
                    has_input=has_input,
                    has_output=has_output,
                    error_kind=error_kind,
                    fire_and_forget=fire_and_forget,
                ),
                TemporaryDirectory() as directory,
            ):
                ModelRegistry.elements.clear()
                path = Path(directory) / "method_sections.fidl"
                annotation = f"<**{description}**>" if annotated else ""
                inputs = "in { UInt32 value }" if has_input else ""
                outputs = "out { UInt32 result }" if has_output else ""
                error_annotation = f"<**{error_description}**>" if error_kind == "annotated" else ""
                error = f"{error_annotation} error Errors" if error_kind != "none" else ""
                flag = "fireAndForget" if fire_and_forget else ""
                path.write_text(
                    "package example interface API { version { major 1 minor 0 } "
                    "enumeration Errors { FAILED } "
                    f"{annotation} method query:first {flag} {{ {inputs} {outputs} {error} }} }}",
                    encoding="utf-8",
                )
                interface = self.transform(path).interfaces[0]
                method = interface.methods[SelectableIdentifier("query:first")]
                self.assertEqual(method.description, description if annotated else "")
                self.assertEqual(method.error_description, error_description if error_kind == "annotated" else "")
                self.assertEqual([argument.name.as_str for argument in method.inputs], ["value"] if has_input else [])
                self.assertEqual(
                    [argument.name.as_str for argument in method.outputs], ["result"] if has_output else []
                )
                self.assertIs(method.error_return_codes, interface.datatypes[0] if error_kind != "none" else None)
                self.assertEqual(method.fire_and_forget, fire_and_forget)

    def test_broadcast_sections_are_consumed_in_grammar_order(self) -> None:
        description = "@description: First  line\n    Second\tline\n\n    @author: Example Author\n"
        for annotated, selective, output_kind in product((False, True), (False, True), ("none", "empty", "field")):
            with (
                self.subTest(annotated=annotated, selective=selective, output_kind=output_kind),
                TemporaryDirectory() as directory,
            ):
                ModelRegistry.elements.clear()
                path = Path(directory) / "broadcast_sections.fidl"
                annotation = f"<**{description}**>" if annotated else ""
                flag = "selective" if selective else ""
                outputs = {"none": "", "empty": "out {}", "field": "out { Payload value }"}[output_kind]
                path.write_text(
                    "package example interface API { version { major 1 minor 0 } "
                    f"{annotation} broadcast changed:first {flag} {{ {outputs} }} "
                    "struct Payload { UInt32 value } }",
                    encoding="utf-8",
                )
                interface = self.transform(path).interfaces[0]
                broadcast = interface.broadcasts[SelectableIdentifier("changed:first")]
                self.assertEqual(broadcast.description, description if annotated else "")
                self.assertEqual(broadcast.selective, selective)
                self.assertEqual(broadcast.model_dump()["selective"], selective)
                self.assertEqual(
                    [argument.name.as_str for argument in broadcast.outputs],
                    ["value"] if output_kind == "field" else [],
                )
                if output_kind == "field":
                    self.assertIs(broadcast.outputs[0].data_type, interface.datatypes[0])

    def test_attribute_sections_are_consumed_in_grammar_order(self) -> None:
        description = "@description: First  line\n    Second\tline\n\n    @author: Example Author\n"
        for annotated, inline_array, readonly, no_read, no_subscriptions in product(
            (False, True), (False, True), (False, True), (False, True), (False, True)
        ):
            with (
                self.subTest(
                    annotated=annotated,
                    inline_array=inline_array,
                    readonly=readonly,
                    no_read=no_read,
                    no_subscriptions=no_subscriptions,
                ),
                TemporaryDirectory() as directory,
            ):
                ModelRegistry.elements.clear()
                path = Path(directory) / "attribute_sections.fidl"
                annotation = f"<**{description}**>" if annotated else ""
                datatype = "Payload[5]" if inline_array else "Payload"
                qualifiers = " ".join(
                    qualifier
                    for qualifier, enabled in (
                        ("readonly", readonly),
                        ("noRead", no_read),
                        ("noSubscriptions", no_subscriptions),
                    )
                    if enabled
                )
                path.write_text(
                    "package example interface API { version { major 1 minor 0 } "
                    f"{annotation} attribute {datatype} value {qualifiers} "
                    "struct Payload { UInt32 value } }",
                    encoding="utf-8",
                )
                interface = self.transform(path).interfaces[0]
                attribute = next(iter(interface.attributes.values()))
                self.assertEqual(attribute.name.as_str, "value")
                self.assertEqual(attribute.description, description if annotated else "")
                self.assertEqual(attribute.has_getter, not no_read)
                self.assertEqual(attribute.has_setter, not readonly)
                self.assertEqual(attribute.subscribable, not no_subscriptions)
                if inline_array:
                    self.assertTrue(attribute.data_type.is_inline)
                    self.assertEqual(attribute.data_type.dimension_max, 5)
                else:
                    self.assertIs(attribute.data_type, interface.datatypes[0])

    def test_unsupported_declarations_are_ignored_after_child_transformation(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "ignored.fidl"
            path.write_text(
                "package example "
                "typeCollection Types { const UInt32 Limit = 42 typedef Value is UInt32 } "
                "interface API extends Missing manages Managed { version { major 1 minor 0 } "
                "const UInt32 Limit = 42 method query {} "
                "contract { vars { UInt32 State = 0 } PSM { initial Idle state Idle {} } } "
                "const UInt32 OtherLimit = 7 struct Payload {} }",
                encoding="utf-8",
            )
            parsed_files = FrancaParser([path], []).parse_files()
            original_tree = parsed_files[path.resolve()].parse_tree
            with patch.object(
                FIDLTransformer,
                "transform",
                autospec=True,
                side_effect=FIDLTransformer.transform,
            ) as transform:
                graph = FrancaFileGraphTransformer(parsed_files)
                graph.transform_files()
                model = graph.transformed_files[path.resolve()]
            transform.assert_called_once()
            tree = transform.call_args.args[1]
            self.assertIs(tree, original_tree)
            rules = {str(node.data) for node in tree.iter_subtrees()}
            self.assertTrue(
                {"fi_contract", "fi_constant_def", "fi_interface_extends", "fi_interface_manages"}.issubset(rules)
            )
            self.assertTrue(
                any(
                    isinstance(element, DataTypeField) and element.name.as_str == "State"
                    for element in ModelRegistry.elements.values()
                )
            )
        self.assertEqual([datatype.name.as_str for datatype in model.type_collections[0].datatypes], ["Value"])
        self.assertEqual([datatype.name.as_str for datatype in model.interfaces[0].datatypes], ["Payload"])
        self.assertIn(SelectableIdentifier("query"), model.interfaces[0].methods)

    def test_unsupported_declarations_still_validate_child_types(self) -> None:
        for source in (
            "typeCollection Types { const Integer(0,100) Limit = 42 }",
            "interface API { version { major 1 minor 0 } const Integer(0,100) Limit = 42 }",
            "interface API { version { major 1 minor 0 } contract { "
            "vars { Integer(0,100) State = 0 } PSM { initial Idle state Idle {} } } }",
        ):
            with self.subTest(source=source), TemporaryDirectory() as directory:
                path = Path(directory) / "invalid.fidl"
                path.write_text("package example " + source, encoding="utf-8")
                with self.assertRaisesRegex(VisitError, "Integer intervals are not supported"):
                    self.transform(path)

    def test_interface_annotation_preserves_all_tags_and_formatting(self) -> None:
        description = (
            "@description: First  line\n"
            "    Second\tline\n\n"
            "    @author: Example Author\n"
            r"    @custom-tag: literal \@marker and \*symbol"
            "\n"
        )
        with TemporaryDirectory() as directory:
            path = Path(directory) / "annotated.fidl"
            path.write_text(
                f"package example <**{description}**> "
                "interface API { version { major 1 minor 0 } "
                "<** @description: Member text **> method query {} }",
                encoding="utf-8",
            )
            interface = self.transform(path).interfaces[0]
        self.assertEqual(interface.description, description)

    def test_duplicate_members_across_contract_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.fidl"
            path.write_text(
                "package example interface API { version { major 1 minor 0 } "
                "method Payload {} "
                "contract { PSM { initial Idle state Idle {} } } "
                "struct Payload {} }",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(VisitError, "Duplicate interface member 'Payload'"):
                self.transform(path)

    def test_duplicate_top_level_names_are_rejected(self) -> None:
        collection = "typeCollection API {}"
        interface = "interface API { version { major 1 minor 0 } }"
        cases = [
            (collection, collection),
            (interface, interface),
            (collection, interface),
            (interface, collection),
        ]
        for declarations in cases:
            with self.subTest(declarations=declarations), TemporaryDirectory() as directory:
                ModelRegistry.elements.clear()
                path = Path(directory) / "duplicate.fidl"
                path.write_text("package example " + " ".join(declarations), encoding="utf-8")
                with self.assertRaisesRegex(VisitError, "Duplicate ID API found in"):
                    self.transform(path)

    def test_anonymous_type_collections_are_preserved(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "anonymous.fidl"
            path.write_text(
                "package example typeCollection {} typeCollection {} "
                "typeCollection Types {} interface API { version { major 1 minor 0 } }",
                encoding="utf-8",
            )
            model = self.transform(path)
        self.assertEqual(len(model.type_collections), 3)
        self.assertIsNone(model.type_collections[0].name)
        self.assertIsNone(model.type_collections[1].name)
        self.assertEqual(model.type_collections[2].name.as_str, "Types")
        self.assertEqual([interface.name.as_str for interface in model.interfaces], ["API"])

    def test_escaped_member_identifiers_remain_valid_identifiers(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "escaped.fidl"
            path.write_text(
                "package example interface ^interface { version { major 1 minor 0 } method ^method:^in {} }",
                encoding="utf-8",
            )
            interface = self.transform(path).interfaces[0]
        self.assertEqual(interface.name.as_str, "interface")
        self.assertEqual(interface.methods[SelectableIdentifier("method:in")].name.as_str, "method:in")


if __name__ == "__main__":
    unittest.main()
