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

"""Shared-model references across interfaces and type collections."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from lark.exceptions import VisitError

from score.ecu_model.data_types.identifier import SelectableIdentifier
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.file_graph_transformer import FrancaFileGraphTransformer


class FIDLReferenceResolutionTest(unittest.TestCase):
    def transform(self, sources: dict[str, str]) -> dict[str, object]:
        with TemporaryDirectory() as directory:
            paths = []
            for name, source in sources.items():
                path = Path(directory) / name
                path.write_text(source, encoding="utf-8")
                paths.append(path)
            graph = FrancaFileGraphTransformer(FrancaParser(paths[:1], paths[1:]).parse_files())
            graph.transform_files()
            return {model.file_path.name: model for model in graph.transformed_files.values()}

    def test_circular_imports_bind_interface_and_collection_types_without_adaptation(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package example import model "base.fidl"
                typeCollection Types { struct Container { DerivedTypes.Item item BaseTypes.BaseItem referenced } }
                typeCollection DerivedTypes { struct Item { BaseTypes.BaseItem base Types.Container container } }
                interface Derived extends Base {
                    version { major 1 minor 0 }
                    struct LocalItem { BaseTypes.BaseItem base Types.Container container }
                    method query:other { in { String value } out { LocalItem payload } }
                    attribute BaseTypes.BaseItem referenced
                }
            """,
                "base.fidl": """package example import model "root.fidl"
                typeCollection BaseTypes { struct BaseItem { DerivedTypes.Item next } }
                interface Base {
                    version { major 1 minor 0 }
                    method query:first { in { UInt32 value } }
                }
            """,
            }
        )
        derived = models["root.fidl"].interfaces[0]
        container = models["root.fidl"].type_collections[0].datatypes[0]
        derived_item = models["root.fidl"].type_collections[1].datatypes[0]
        base_item = models["base.fidl"].type_collections[0].datatypes[0]
        self.assertEqual({name.as_str for name in derived.methods}, {"query:other"})
        self.assertIs(container.fields[0].data_type, derived_item)
        self.assertIs(container.fields[1].data_type, base_item)
        self.assertIs(base_item.fields[0].data_type, derived_item)
        self.assertIs(derived.datatypes[0].fields[0].data_type, base_item)
        self.assertIs(derived.datatypes[0].fields[1].data_type, container)
        self.assertIs(next(iter(derived.attributes.values())).data_type, base_item)

    def test_namespace_import_binds_named_method_error_and_inline_array(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package app import common.Types.* from "types.fidl"
                interface API { version { major 1 minor 0 }
                    method query { in { Types.Payload[0,10] data } error Types.Errors }
                    attribute Types.Payload[] status readonly noRead noSubscriptions
                }
            """,
                "types.fidl": "package common typeCollection Types { struct Payload {} enumeration Errors { FAILED } }",
            }
        )
        interface = models["root.fidl"].interfaces[0]
        payload, errors = models["types.fidl"].type_collections[0].datatypes
        method = interface.methods[SelectableIdentifier("query")]
        self.assertIs(method.inputs[0].data_type.data_type, payload)
        self.assertIs(method.error_return_codes, errors)
        self.assertIs(next(iter(interface.attributes.values())).data_type.data_type, payload)

    def test_interface_local_datatypes_take_precedence(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package example
                    typeCollection { struct Payload {} }
                    interface API {
                        version { major 1 minor 0 }
                        struct Payload {}
                        attribute Payload value
                        method get { in { example.API.Payload data } }
                    }
                """
            }
        )
        file_model = models["root.fidl"]
        interface = file_model.interfaces[0]
        self.assertIs(next(iter(interface.attributes.values())).data_type, interface.datatypes[0])
        self.assertIs(interface.methods[SelectableIdentifier("get")].inputs[0].data_type, interface.datatypes[0])
        self.assertIs(file_model.lookup_datatype_in_tc("example.Payload"), file_model.type_collections[0].datatypes[0])
        self.assertIsNone(file_model.lookup_datatype_in_tc("example.API.Payload"))

    def test_interface_and_file_datatypes_precede_imported_types(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package app import common.Types.* from "types.fidl"
                    typeCollection LocalTypes { struct Payload {} }
                    interface Local {
                        version { major 1 minor 0 }
                        struct Payload {}
                        method get { in { Payload value } }
                    }
                    interface FileFallback {
                        version { major 1 minor 0 }
                        method get { in { LocalTypes.Payload value } }
                    }
                """,
                "types.fidl": "package common typeCollection Types { struct Payload {} }",
            }
        )

        file_model = models["root.fidl"]
        interface_local = file_model.interfaces[0]
        file_fallback = file_model.interfaces[1]
        local_payload = interface_local.datatypes[0]
        file_payload = file_model.type_collections[0].datatypes[0]
        method_local_payload = interface_local.methods[SelectableIdentifier("get")].inputs[0].data_type
        method_file_payload = file_fallback.methods[SelectableIdentifier("get")].inputs[0].data_type

        self.assertIs(method_local_payload, local_payload)
        self.assertIs(method_file_payload, file_payload)

    def test_other_interface_datatypes_are_not_visible_by_qualified_name(self) -> None:
        with self.assertRaisesRegex((ValueError, VisitError), "was not found"):
            self.transform(
                {
                    "root.fidl": """package example
                        interface Private {
                            version { major 1 minor 0 }
                            struct Secret {}
                        }
                        interface Public {
                            version { major 1 minor 0 }
                            method leak { in { Private.Secret value } }
                        }
                    """
                }
            )

    def test_imported_interface_datatypes_are_not_visible_by_qualified_name(self) -> None:
        with self.assertRaisesRegex((ValueError, VisitError), "was not found"):
            self.transform(
                {
                    "root.fidl": """package app import \"types.fidl\"
                        interface Public {
                            version { major 1 minor 0 }
                            method leak { in { common.Hidden.Secret value } }
                        }
                    """,
                    "types.fidl": """package common
                        interface Hidden {
                            version { major 1 minor 0 }
                            struct Secret {}
                        }
                    """,
                }
            )

    def test_indirect_imported_type_collection_is_not_searched(self) -> None:
        with self.assertRaisesRegex((ValueError, VisitError), "was not found"):
            self.transform(
                {
                    "root.fidl": """package root import \"middle.fidl\"
                        interface Public {
                            version { major 1 minor 0 }
                            method leak { in { leaf.LeafTypes.Payload value } }
                        }
                    """,
                    "middle.fidl": """package middle import \"leaf.fidl\"
                        typeCollection MiddleTypes {}
                    """,
                    "leaf.fidl": """package leaf
                        typeCollection LeafTypes { struct Payload {} }
                    """,
                }
            )

    def test_reference_complete_interface_combination_transforms_supported_semantics(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package example
                    interface Base {
                        version { major 1 minor 0 }
                        method ping {}
                    }
                    interface Sample extends Base manages Ignored {
                        version { major 1 minor 2 }
                        public typedef Alias is UInt32
                        public array Items of Alias[0,25]
                        public enumeration Errors { OK FAILED = 0x10 }
                        public struct Payload polymorphic { Alias value }
                        public union Value { UInt32 number String text }
                        public map Lookup { String to Payload }
                        const UInt32 ignored = 1 + 2 * 3
                        attribute Payload[0,25] value noRead readonly noSubscriptions
                        method request:first { in { Alias input } out { Items result } error Errors }
                        method request:second fireAndForget { in { String text } }
                        broadcast changed:first selective { out { Payload data } }
                        broadcast changed:second {}
                        contract { PSM { initial Idle state Idle { on call ping -> Idle } } }
                        struct AfterContract { ByteBuffer bytes }
                    }
                """
            }
        )

        interface = models["root.fidl"].interfaces[1]
        self.assertEqual(len(interface.datatypes), 7)
        self.assertEqual(set(name.as_str for name in interface.methods), {"request:first", "request:second"})
        self.assertEqual(set(name.as_str for name in interface.broadcasts), {"changed:first", "changed:second"})
        self.assertNotIn(SelectableIdentifier("ping"), interface.methods)
        method = interface.methods[SelectableIdentifier("request:first")]
        self.assertEqual(method.error_return_codes.name.as_str, "Errors")
        self.assertTrue(interface.methods[SelectableIdentifier("request:second")].fire_and_forget)
        self.assertFalse(next(iter(interface.attributes.values())).has_getter)
        self.assertFalse(next(iter(interface.attributes.values())).has_setter)
        self.assertFalse(next(iter(interface.attributes.values())).subscribable)

    def test_imported_named_array_keeps_reference_ownership_across_circular_imports(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package example.root
                    import "middle.fidl"
                    typeCollection RootTypes { struct Payload { UInt32 value } }
                """,
                "middle.fidl": """package example.middle
                    import "leaf.fidl"
                    typeCollection MiddleTypes {
                        struct Container { LeafTypes.LeafArray values }
                    }
                """,
                "leaf.fidl": """package example.leaf
                    import "root.fidl"
                    typeCollection LeafTypes {
                        array LeafArray of RootTypes.Payload
                    }
                """,
            }
        )

        root_payload = models["root.fidl"].type_collections[0].datatypes[0]
        middle_container = models["middle.fidl"].type_collections[0].datatypes[0]
        leaf_array = models["leaf.fidl"].type_collections[0].datatypes[0]
        self.assertIs(middle_container.fields[0].data_type, leaf_array)
        self.assertIs(leaf_array.data_type, root_payload)

    def test_local_errors_are_rejected(self) -> None:
        version = "version { major 1 minor 0 }"
        cases = (
            ("method get { in { UInt32 x UInt32 x } }", "Duplicate parameter"),
            ("method get { out { UInt32 x UInt32 x } }", "Duplicate parameter"),
            ("broadcast changed { out { UInt32 x UInt32 x } }", "Duplicate parameter"),
            ("struct Payload {} typedef Payload is UInt8", "Duplicate interface member"),
            ("method ping {} broadcast ping {}", "Duplicate interface member"),
            ("method get fireAndForget { out { UInt32 x } }", "fireAndForget"),
            ("method get fireAndForget { error Missing }", "fireAndForget"),
        )
        for members, message in cases:
            with self.subTest(members=members), self.assertRaisesRegex(VisitError, message):
                self.transform({"root.fidl": f"package example interface API {{ {version} {members} }}"})

    def test_input_and_output_names_are_checked_in_separate_scopes(self) -> None:
        models = self.transform(
            {
                "root.fidl": "package example interface API { version { major 1 minor 0 } "
                "method get { in { UInt32 value } out { String value } } }"
            }
        )
        method = models["root.fidl"].interfaces[0].methods[SelectableIdentifier("get")]
        self.assertEqual(method.inputs[0].name.as_str, "value")
        self.assertEqual(method.outputs[0].name.as_str, "value")

    def test_unused_type_collection_valid_chains_are_accepted(self) -> None:
        for name in ("Types", ""):
            with self.subTest(name=name):
                models = self.transform(
                    {
                        "root.fidl": f"package example typeCollection {name} {{ "
                        "typedef First is Second array Second of Third typedef Third is UInt32 }"
                    }
                )
                model = models["root.fidl"]
                self.assertEqual(model.interfaces, [])
                first, second, third = model.type_collections[0].datatypes
                self.assertIs(first.data_type, second)
                self.assertIs(second.data_type, third)

    def test_invalid_declarations_are_rejected(self) -> None:
        version = "version { major 1 minor 0 }"
        cases = [
            (f"interface A {{ {version} attribute Missing value }}", "was not found"),
            (f"interface A {{ {version} method get:x {{}} method get:x {{}} }}", "Duplicate interface member"),
            (f"interface A {{ {version} method ping {{}} broadcast ping {{}} }}", "Duplicate interface member"),
            (f"interface A {{ {version} method status {{}} attribute UInt32 status }}", "Duplicate interface member"),
            (
                f"interface A {{ {version} method Payload {{}} typedef Payload is UInt8 }}",
                "Duplicate interface member",
            ),
            (f'interface A {{ {version} enumeration Status {{ UNKNOWN = "bad" }} }}', "integer literals"),
            (f"interface A {{ {version} enumeration Status {{ UNKNOWN = 1.5f }} }}", "integer literals"),
            (f"interface A {{ {version} enumeration Status {{ UNKNOWN = true }} }}", "integer literals"),
            (f"interface A {{ {version} method get {{ in {{ UInt32 x UInt32 x }} }} }}", "Duplicate parameter"),
            (f"interface A {{ {version} method get fireAndForget {{ out {{ UInt32 x }} }} }}", "fireAndForget"),
        ]
        for body, message in cases:
            with self.subTest(body=body), self.assertRaisesRegex((ValueError, VisitError), message):
                self.transform({"root.fidl": "package example " + body})
        with self.assertRaises((ValueError, VisitError)):
            self.transform(
                {
                    "root.fidl": f"package example interface API {{ {version} "
                    "struct NotAnEnum {} method call { error NotAnEnum } }"
                }
            )

    def test_distinct_selectors_accept_identical_signatures(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package example
                interface Base {
                    version { major 1 minor 0 }
                    method get:x { in { UInt32 value } out { String result } }
                    broadcast changed:x { out { UInt32 value } }
                }
                interface Derived extends Base {
                    version { major 1 minor 0 }
                    method get:x { in { UInt32 value } out { String result } }
                    method get:y { in { UInt32 value } out { String result } }
                    broadcast changed:x { out { UInt32 value } }
                    broadcast changed:y { out { UInt32 value } }
                    method empty:x {}
                    method empty:y {}
                }
                """
            }
        )
        interface = models["root.fidl"].interfaces[1]
        self.assertEqual({name.as_str for name in interface.methods}, {"get:x", "get:y", "empty:x", "empty:y"})
        self.assertEqual({name.as_str for name in interface.broadcasts}, {"changed:x", "changed:y"})

    def test_interface_extends_is_ignored_without_resolving_references(self) -> None:
        version = "version { major 1 minor 0 }"
        for header in ("extends Missing", "extends Missing manages Managed", "extends API"):
            with self.subTest(header=header):
                models = self.transform(
                    {"root.fidl": f"package example interface API {header} {{ {version} method ping {{}} }}"}
                )
                interface = models["root.fidl"].interfaces[0]
                self.assertEqual({name.as_str for name in interface.methods}, {"ping"})
                self.assertFalse(hasattr(interface, "base"))
        models = self.transform(
            {
                "root.fidl": f"package example interface A extends B {{ {version} }} "
                f"interface B extends A {{ {version} }}"
            }
        )
        self.assertEqual(len(models["root.fidl"].interfaces), 2)

    def test_interface_members_and_datatypes_are_not_inherited(self) -> None:
        models = self.transform(
            {
                "root.fidl": """package example
                interface Base {
                    version { major 1 minor 0 }
                    struct Payload {}
                    method ping {}
                    broadcast changed {}
                    attribute UInt32 status
                }
                interface Derived extends Base {
                    version { major 1 minor 0 }
                    method query {}
                }
            """
            }
        )
        file_model = models["root.fidl"]
        interface = file_model.interfaces[1]
        self.assertEqual({name.as_str for name in interface.methods}, {"query"})
        self.assertEqual(interface.broadcasts, {})
        self.assertEqual(interface.attributes, {})
        self.assertEqual(interface.datatypes, [])
        self.assertIsNone(file_model.lookup_datatype_in_tc("example.Derived.Payload"))

    def test_interface_extends_does_not_extend_datatype_scope(self) -> None:
        for reference in ("Payload", "Derived.Payload"):
            with self.subTest(reference=reference), self.assertRaisesRegex((ValueError, VisitError), "was not found"):
                self.transform(
                    {
                        "root.fidl": f"""package example
                        interface Base {{ version {{ major 1 minor 0 }} struct Payload {{}} }}
                        interface Derived extends Base {{
                            version {{ major 1 minor 0 }}
                            attribute {reference} value
                        }}
                    """
                    }
                )

    def test_type_collection_cannot_reference_interface_local_datatypes(self) -> None:
        with self.assertRaisesRegex((ValueError, VisitError), "was not found"):
            self.transform(
                {
                    "root.fidl": """package example
                        interface Private {
                            version { major 1 minor 0 }
                            struct Secret {}
                        }
                        typeCollection PublicTypes {
                            struct Container { Private.Secret value }
                        }
                    """
                }
            )

    def test_duplicate_interface_names_are_rejected_regardless_of_version(self) -> None:
        for major, minor in ((1, 0), (1, 1), (2, 0)):
            with self.subTest(major=major, minor=minor):
                source = (
                    "package example "
                    "interface A { version { major 1 minor 0 } } "
                    f"interface A {{ version {{ major {major} minor {minor} }} }}"
                )
                with self.assertRaisesRegex(VisitError, "Duplicate ID A found in"):
                    self.transform({"root.fidl": source})


if __name__ == "__main__":
    unittest.main()
