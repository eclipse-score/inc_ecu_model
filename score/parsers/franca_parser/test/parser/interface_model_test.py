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

"""End-to-end shared interface registry generation."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lark.exceptions import VisitError

from score.ecu_model.common.version import Version
from score.ecu_model.communication.binding import NetworkKind
from score.ecu_model.communication.service_interface import InterfaceDefinition, ServiceInterface
from score.ecu_model.data_types.common import DataTypeBase, DataTypeSource
from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.model import ModelRegistry
from score.parsers.franca_parser.deployment_property_applier import DeploymentPropertyApplier
from score.parsers.franca_parser.franca_model_parser_runner import main
from score.parsers.franca_parser.model.fdepl.fdepl_file import FDEPLFileModel
from score.parsers.franca_parser.model.fdepl.interface_deployment import (
    BroadcastDeployment,
    InterfaceDeployment,
    MethodDeployment,
)
from score.parsers.franca_parser.model.fdepl.type_collection_deployment import StructDeployment
from score.parsers.franca_parser.model.fidl.fidl_file import FIDLFileModel
from score.parsers.franca_parser.model.fidl.type_collection import TypeCollection
from score.parsers.franca_parser.model.franca_file import ImportedNamespace
from score.parsers.franca_parser.parser import FrancaParser
from score.parsers.franca_parser.transformer.fdepl_transformer import FDEPLTransformer
from score.parsers.franca_parser.transformer.file_graph_transformer import FrancaFileGraphTransformer
from score.parsers.franca_parser.transformer.resolver.fdepl_resolver import FDEPLResolver


def qualified_name(value: str) -> QualifiedName:
    """Create a qualified Franca name from a readable dotted test value."""
    return QualifiedName(tuple(Identifier(part) for part in value.split(".")))


class FDEPLInterfaceResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()
        self.interface = InterfaceDefinition(name="Demo", namespace="a.b.c", version=Version(major=1, minor=0, patch=0))
        self.design = FIDLFileModel(
            file_path=Path("service.fidl"), namespace=qualified_name("a.b.c"), interfaces=[self.interface]
        )
        self.deployment = FDEPLFileModel(file_path=Path("service.fdepl"), namespace=None)
        self.resolver = FDEPLResolver({self.design.file_path: self.design})

    def test_interface_deployment_requires_target(self) -> None:
        self.assertRaisesRegex(TypeError, "required keyword-only argument: 'target'", InterfaceDeployment)

    def test_interface_datatype_respects_import_scope_and_priority(self) -> None:
        imported = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        local = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        self.interface.datatypes = [local]
        for collection_name, prefix, use_imported in (
            (None, None, True),
            (None, "a.b.c", True),
            (None, "a.b", False),
            (None, "other.scope.name", False),
            (None, "a.b.cx", False),
            (None, "a.b.c.extra", False),
            ("Types", None, False),
            ("Types", "a.b.c.Types", False),
        ):
            with self.subTest(collection_name=collection_name, prefix=prefix):
                self.design.type_collections = [
                    TypeCollection(
                        name=Identifier(collection_name) if collection_name is not None else None,
                        datatypes=[imported],
                    )
                ]
                self.deployment.imported_files = [
                    ImportedNamespace(self.design.file_path, qualified_name(prefix) if prefix is not None else None)
                ]
                element = StructDeployment(deployed_type=Identifier("Payload"))
                deployment = InterfaceDeployment(target=self.interface, deployment_elements=[element])

                self.resolver.resolve_interface_deployment_elements(deployment, self.deployment)

                self.assertIs(element.deployed_type, imported if use_imported else local)

    def test_interface_datatype_rejects_named_collection_without_local_target(self) -> None:
        imported = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        self.design.type_collections = [TypeCollection(name=Identifier("Types"), datatypes=[imported])]
        self.deployment.imported_files = [ImportedNamespace(self.design.file_path, None)]
        element = StructDeployment(deployed_type=Identifier("Payload"))
        deployment = InterfaceDeployment(target=self.interface, deployment_elements=[element])

        with self.assertRaisesRegex(ValueError, "Could not resolve FIDL datatype Payload in service.fdepl"):
            self.resolver.resolve_interface_deployment_elements(deployment, self.deployment)

    def test_interface_datatype_uses_last_import_scope_for_each_file(self) -> None:
        imported = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        local = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        self.design.type_collections = [TypeCollection(name=None, datatypes=[imported])]
        self.interface.datatypes = [local]
        for prefixes, expected in (
            ((None, None), imported),
            ((None, "a.b"), local),
            (("a.b", None), imported),
        ):
            with self.subTest(prefixes=prefixes):
                self.deployment.imported_files = [
                    ImportedNamespace(self.design.file_path, qualified_name(prefix) if prefix is not None else None)
                    for prefix in prefixes
                ]
                element = StructDeployment(deployed_type=Identifier("Payload"))
                deployment = InterfaceDeployment(target=self.interface, deployment_elements=[element])

                self.resolver.resolve_interface_deployment_elements(deployment, self.deployment)

                self.assertIs(element.deployed_type, expected)

    def test_interface_datatype_uses_first_matching_collection_in_each_file(self) -> None:
        first = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        second = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        self.design.type_collections = [
            TypeCollection(name=None, datatypes=[first]),
            TypeCollection(name=None, datatypes=[second]),
        ]
        self.deployment.imported_files = [ImportedNamespace(self.design.file_path, None)]
        element = StructDeployment(deployed_type=Identifier("Payload"))
        deployment = InterfaceDeployment(target=self.interface, deployment_elements=[element])

        self.resolver.resolve_interface_deployment_elements(deployment, self.deployment)

        self.assertIs(element.deployed_type, first)

    def test_interface_datatype_rejects_ambiguous_imports_before_local_fallback(self) -> None:
        imported = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        other = StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)
        self.design.type_collections = [TypeCollection(name=None, datatypes=[imported])]
        self.interface.datatypes = [StructDataType(name="Payload", source_kind=DataTypeSource.FRANCA)]
        other_design = FIDLFileModel(
            file_path=Path("other.fidl"),
            namespace=self.design.namespace,
            type_collections=[TypeCollection(name=None, datatypes=[other])],
        )
        self.deployment.imported_files = [
            ImportedNamespace(self.design.file_path, None),
            ImportedNamespace(other_design.file_path, None),
        ]
        resolver = FDEPLResolver({self.design.file_path: self.design, other_design.file_path: other_design})
        element = StructDeployment(deployed_type=Identifier("Payload"))
        deployment = InterfaceDeployment(target=self.interface, deployment_elements=[element])

        with self.assertRaisesRegex(ValueError, "Ambiguous FIDL datatype Payload in service.fdepl"):
            resolver.resolve_interface_deployment_elements(deployment, self.deployment)

    def test_interface_datatype_rejects_missing_imported_and_local_targets(self) -> None:
        self.deployment.imported_files = [ImportedNamespace(self.design.file_path, None)]
        element = StructDeployment(deployed_type=Identifier("Missing"))
        deployment = InterfaceDeployment(target=self.interface, deployment_elements=[element])

        with self.assertRaisesRegex(ValueError, "Could not resolve FIDL datatype Missing in service.fdepl"):
            self.resolver.resolve_interface_deployment_elements(deployment, self.deployment)

    def test_fd_interface_resolves_target_before_constructing_deployment(self) -> None:
        with TemporaryDirectory() as directory:
            design_path = Path(directory) / "service.fidl"
            deployment_path = Path(directory) / "service.fdepl"
            design_path.write_text("package a.b.c\ninterface Demo { version { major 1 minor 0 } }\n", encoding="utf-8")
            deployment_path.write_text(
                'package deployment\nimport "service.fidl"\nspecification someip {}\n', encoding="utf-8"
            )
            parsed_file = FrancaParser([deployment_path], [design_path]).parse_files()[deployment_path.resolve()]
            transformer = FDEPLTransformer(
                {design_path.resolve(): self.design}, parsed_file, DeploymentPropertyApplier()
            )

            deployment = transformer.fd_interface(qualified_name("a.b.c.Demo"))

            self.assertIs(deployment.target, self.interface)
            with self.assertRaisesRegex(
                ValueError, "Could not resolve FIDL interface a.b.c.Missing in .*service.fdepl"
            ):
                transformer.fd_interface(qualified_name("a.b.c.Missing"))

    def test_resolve_interface_respects_import_scope_and_legacy_reference_forms(self) -> None:
        for namespace, reference, expected in (
            ("a.b.c", "Demo", True),
            ("a.b", "c.Demo", True),
            ("a.b", "b.c.Demo", True),
            ("a.b", "a.b.c.Demo", True),
            ("a.b", "Demo", False),
            ("other", "a.b.c.Demo", False),
            ("a.b.cx", "a.b.c.Demo", False),
            ("a.b", "other.Demo", False),
            (None, "Demo", True),
            (None, "c.Demo", True),
            (None, "a.b.c.Demo", True),
        ):
            with self.subTest(namespace=namespace, reference=reference):
                self.deployment.imported_files = [
                    ImportedNamespace(
                        self.design.file_path, qualified_name(namespace) if namespace is not None else None
                    )
                ]
                if expected:
                    self.assertIs(
                        self.resolver.resolve_interface(
                            qualified_name(reference), self.deployment.imported_files, self.deployment.file_path
                        ),
                        self.interface,
                    )
                else:
                    with self.assertRaisesRegex(ValueError, "Could not resolve FIDL interface"):
                        self.resolver.resolve_interface(
                            qualified_name(reference), self.deployment.imported_files, self.deployment.file_path
                        )

    def test_resolve_interface_deduplicates_declarations_not_import_scopes(self) -> None:
        self.deployment.imported_files = [
            ImportedNamespace(self.design.file_path, qualified_name("other")),
            ImportedNamespace(self.design.file_path, qualified_name("a.b.c")),
            ImportedNamespace(self.design.file_path, None),
        ]

        self.assertIs(
            self.resolver.resolve_interface(
                qualified_name("a.b.c.Demo"), self.deployment.imported_files, self.deployment.file_path
            ),
            self.interface,
        )

    def test_resolve_interface_rejects_distinct_matching_declarations(self) -> None:
        other_interface = InterfaceDefinition(
            name="Demo", namespace="a.b.c", version=Version(major=1, minor=0, patch=0)
        )
        other_design = FIDLFileModel(
            file_path=Path("other.fidl"), namespace=self.design.namespace, interfaces=[other_interface]
        )
        self.deployment.imported_files = [
            ImportedNamespace(self.design.file_path, None),
            ImportedNamespace(other_design.file_path, None),
        ]
        resolver = FDEPLResolver({self.design.file_path: self.design, other_design.file_path: other_design})

        with self.assertRaisesRegex(ValueError, "Ambiguous FIDL interface a.b.c.Demo in service.fdepl"):
            resolver.resolve_interface(
                qualified_name("a.b.c.Demo"), self.deployment.imported_files, self.deployment.file_path
            )

    def test_resolve_interface_only_searches_direct_fidl_imports(self) -> None:
        intermediate = FDEPLFileModel(
            file_path=Path("intermediate.fdepl"),
            namespace=None,
            imported_files=[ImportedNamespace(self.design.file_path, None)],
        )
        self.deployment.imported_files = [
            ImportedNamespace(intermediate.file_path, None),
            ImportedNamespace(Path("missing.fidl"), None),
        ]
        resolver = FDEPLResolver({self.design.file_path: self.design, intermediate.file_path: intermediate})

        with self.assertRaisesRegex(ValueError, "Could not resolve FIDL interface a.b.c.Demo in service.fdepl"):
            resolver.resolve_interface(
                qualified_name("a.b.c.Demo"), self.deployment.imported_files, self.deployment.file_path
            )


class InterfaceModelRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

    def test_event_group_member_snapshots_use_the_current_declaration(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory)
            design = path / "service.fidl"
            deployment = path / "service.cdepl"
            output = path / "model.pkl"
            json_output = path / "model.json"
            design.write_text(
                "package demo\ninterface API { version { major 1 minor 0 }\n"
                "attribute UInt32 temperature\n"
                "broadcast changed {}\nbroadcast previous {}\n}\n",
                encoding="utf-8",
            )
            deployment.write_text(
                'package deployment\nimport "service.fidl"\n'
                "specification ipc { for interfaces { IpcServiceId: Integer; } for event_groups { "
                "Marker: Integer (optional); DefaultId: Integer (default: 10); Extra: Integer (optional); } }\n"
                "define ipc for interface demo.API {\n"
                "IpcServiceId = 80\n"
                "eventgroup Events { Marker = 1 DefaultId = 20 }\n"
                "attribute temperature { eventgroups { Events } }\n"
                "broadcast changed { eventgroups { Events } }\n"
                "broadcast previous { eventgroups { Events } }\n}\n"
                "define ipc for interface demo.API {\n"
                "IpcServiceId = 80\n"
                "eventgroup Events { Extra = 30 }\n"
                "attribute temperature { eventgroups { Events } }\n"
                "broadcast changed { eventgroups { Events } }\n}\n",
                encoding="utf-8",
            )
            main(
                [
                    "--src",
                    str(deployment),
                    "--dep",
                    str(design),
                    "--output",
                    str(output),
                    "--json-output",
                    str(json_output),
                ]
            )
            registry = json.loads(json_output.read_text(encoding="utf-8"))

        interface = next(element for element in registry.values() if element.get("deployment_binding"))
        self.assertEqual(interface["event_groups"]["Events"], {"Marker": 1, "DefaultId": 20, "Extra": 30})
        self.assertEqual(
            interface["attribute_deployment_properties"]["temperature"]["event_groups#ipc"]["Events"],
            {"DefaultId": 10, "Extra": 30},
        )
        self.assertEqual(
            interface["broadcast_deployment_properties"]["changed"]["event_groups#ipc"]["Events"],
            {"DefaultId": 10, "Extra": 30},
        )
        self.assertEqual(
            interface["broadcast_deployment_properties"]["previous"]["event_groups#ipc"]["Events"],
            {"Marker": 1, "DefaultId": 20},
        )

    def test_repeated_event_group_declarations_validate_required_properties_independently(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory)
            design = path / "service.fidl"
            deployment = path / "service.cdepl"
            design.write_text("package demo\ninterface API { version { major 1 minor 0 } }\n", encoding="utf-8")
            source = (
                'package deployment\nimport "service.fidl"\n'
                "specification ipc { for interfaces { IpcServiceId: Integer; } "
                "for event_groups { RequiredId: Integer; DefaultId: Integer (default: 10); } }\n"
                "define ipc for interface demo.API { IpcServiceId = 80 eventgroup Events "
                "{ RequiredId = 1 DefaultId = 20 } }\n"
                "define ipc for interface demo.API { IpcServiceId = 80 eventgroup Events { %s } }\n"
            )
            for parameters, expected in (
                ("", None),
                ("RequiredId = 2", {"RequiredId": 2, "DefaultId": 20}),
            ):
                with self.subTest(parameters=parameters):
                    ModelRegistry.elements.clear()
                    deployment.write_text(source % parameters, encoding="utf-8")
                    parser = FrancaParser(root_files=[deployment], dependency_files=[design])
                    transformer = FrancaFileGraphTransformer(parser.parse_files())
                    if expected is None:
                        with self.assertRaises((ValueError, VisitError)) as error:
                            transformer.transform_files()
                        self.assertIn("Required deployment property RequiredId is not set", str(error.exception))
                    else:
                        transformer.transform_files()
                        interface = next(
                            element
                            for element in ModelRegistry.elements.values()
                            if isinstance(element, ServiceInterface)
                        )
                        self.assertEqual(interface.event_groups[Identifier("Events")], expected)

    def test_interface_deployments_resolve_relative_overlapping_and_full_import_references(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory)
            design = path / "service.fidl"
            deployment = path / "service.fdepl"
            design.write_text("package a.b.c\ninterface Demo { version { major 1 minor 0 } }\n", encoding="utf-8")
            deployment.write_text(
                'package deployment\nimport a.b.* from "service.fidl"\n'
                "specification someip { for interfaces { SomeIpServiceID: Integer; } }\n"
                "define someip for interface c.Demo as Relative { SomeIpServiceID = 40 }\n"
                "define someip for interface b.c.Demo as Overlapping { SomeIpServiceID = 40 }\n"
                "define someip for interface a.b.c.Demo as Full { SomeIpServiceID = 40 }\n",
                encoding="utf-8",
            )
            parser = FrancaParser(root_files=[deployment], dependency_files=[design])
            transformer = FrancaFileGraphTransformer(parser.parse_files())
            transformer.transform_files()
            interface = transformer.transformed_files[design.resolve()].interfaces[0]
            deployments = transformer.transformed_files[deployment.resolve()].interface_deployments

        self.assertEqual(len(deployments), 3)
        self.assertTrue(all(item.target is interface for item in deployments))

    def test_runner_applies_interface_members_as_deployment_elements(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory)
            design = path / "service.fidl"
            deployment = path / "service.cdepl"
            output = path / "model.pkl"
            json_output = path / "model.json"
            design.write_text(
                "package demo\ninterface API { version { major 1 minor 0 }\n"
                "method call { in { UInt32 request } out { UInt32 response } }\n"
                "broadcast changed { out { UInt32 value } }\n}\n",
                encoding="utf-8",
            )
            deployment.write_text(
                'package demo.deployment\nimport "service.fidl"\n'
                "specification someip {\n"
                "for interfaces { SomeIpServiceID: Integer; }\n"
                "for methods { Marker: Integer (optional); }\n"
                "for broadcasts { Marker: Integer (optional); }\n"
                "for event_groups { EventGroupIdentifier: Integer (optional); }\n"
                "for integers { ArgumentMarker: Integer (optional); }\n}\n"
                "specification ipc {\n"
                "for interfaces { IpcServiceId: Integer; }\n"
                "for methods { Marker: Integer (optional); }\n"
                "for broadcasts { Marker: Integer (optional); }\n"
                "for event_groups { EventGroupIdentifier: Integer (optional); }\n"
                "for integers { ArgumentMarker: Integer (optional); ArgumentExtra: Integer (optional); }\n}\n"
                "<** @description: ignored **>\n"
                "define someip for interface demo.API {\n"
                "SomeIpServiceID = 40\n"
                "method call { Marker = 3 in { request { ArgumentMarker = 4 } } "
                "out { response { ArgumentMarker = 6 } } }\n"
                "broadcast changed { eventgroups { Events } Marker = 5 "
                "out { value { ArgumentMarker = 7 } } }\n"
                "eventgroup Events { EventGroupIdentifier = 17 }\n}\n"
                "define ipc for interface demo.API {\n"
                "IpcServiceId = 80\n"
                "method call { Marker = 30 in { request { ArgumentMarker = 40 } } "
                "out { response { ArgumentMarker = 60 } } }\n"
                "broadcast changed { eventgroups { Events } Marker = 50 "
                "out { value { ArgumentMarker = 70 } } }\n"
                "eventgroup Events { EventGroupIdentifier = 27 }\n}\n"
                "define ipc for interface demo.API {\n"
                "IpcServiceId = 80\n"
                "method call { in { request { ArgumentExtra = 41 } } "
                "out { response { ArgumentExtra = 61 } } }\n"
                "broadcast changed { out { value { ArgumentExtra = 71 } } }\n}\n",
                encoding="utf-8",
            )

            with patch.object(
                DeploymentPropertyApplier,
                "_apply_deployment_element",
                autospec=True,
                side_effect=DeploymentPropertyApplier._apply_deployment_element,
            ) as apply_element:
                main(
                    [
                        "--src",
                        str(deployment),
                        "--dep",
                        str(design),
                        "--output",
                        str(output),
                        "--json-output",
                        str(json_output),
                    ]
                )
            member_calls = [
                call.args
                for call in apply_element.call_args_list
                if isinstance(call.args[1], (BroadcastDeployment, MethodDeployment))
            ]
            interface_calls = [
                call.args for call in apply_element.call_args_list if isinstance(call.args[1], InterfaceDeployment)
            ]
            self.assertEqual(len(member_calls), 6)
            self.assertTrue(all(isinstance(call[3], ServiceInterface) for call in member_calls))
            self.assertEqual(len(interface_calls), 3)
            self.assertTrue(all(isinstance(call[3], ServiceInterface) for call in interface_calls))
            ModelRegistry.deserialize(output.read_bytes())
            json_registry = json.loads(json_output.read_text(encoding="utf-8"))

        interfaces = {
            element.deployment_binding.network: element
            for element in ModelRegistry.elements.values()
            if isinstance(element, ServiceInterface)
        }
        self.assertEqual(set(interfaces), {NetworkKind.SOMEIP, NetworkKind.IPC})
        for network, service_id, marker, broadcast_marker, event_id, arguments in (
            (
                NetworkKind.SOMEIP,
                40,
                3,
                5,
                17,
                ({"ArgumentMarker": 4}, {"ArgumentMarker": 6}, {"ArgumentMarker": 7}),
            ),
            (
                NetworkKind.IPC,
                80,
                30,
                50,
                27,
                (
                    {"ArgumentMarker": 40, "ArgumentExtra": 41},
                    {"ArgumentMarker": 60, "ArgumentExtra": 61},
                    {"ArgumentMarker": 70, "ArgumentExtra": 71},
                ),
            ),
        ):
            interface = interfaces[network]
            self.assertEqual(interface.service_id, service_id)
            self.assertEqual(
                interface.method_deployment_properties[SelectableIdentifier("call")],
                {
                    "Marker": marker,
                    "inputs#arguments": {"request": arguments[0]},
                    "outputs#arguments": {"response": arguments[1]},
                },
            )
            self.assertEqual(
                interface.broadcast_deployment_properties[SelectableIdentifier("changed")],
                {
                    "Marker": broadcast_marker,
                    f"event_groups#{network.value.lower()}": {"Events": {"EventGroupIdentifier": event_id}},
                    "outputs#arguments": {"value": arguments[2]},
                },
            )
            json_interface = json_registry[str(interface.id)]
            self.assertEqual(json_interface["service_id"], service_id)
            self.assertEqual(
                json_interface["method_deployment_properties"]["call"]["inputs#arguments"]["request"], arguments[0]
            )
            self.assertEqual(
                json_interface["method_deployment_properties"]["call"]["outputs#arguments"]["response"], arguments[1]
            )
            self.assertEqual(
                json_interface["broadcast_deployment_properties"]["changed"]["outputs#arguments"]["value"], arguments[2]
            )
        interface = interfaces[NetworkKind.SOMEIP].design_element
        method = interface.methods[SelectableIdentifier("call")]
        broadcast = interface.broadcasts[SelectableIdentifier("changed")]
        self.assertEqual(method.inputs[0].deployment_properties, {})
        self.assertEqual(method.outputs[0].deployment_properties, {})
        self.assertEqual(broadcast.outputs[0].deployment_properties, {})

    def test_interface_deployments_share_applier_across_circular_imports(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory)
            design = path / "service.fidl"
            first = path / "first.fdepl"
            second = path / "second.cdepl"
            design.write_text(
                "package demo\ninterface API { version { major 1 minor 0 } }\n",
                encoding="utf-8",
            )
            first.write_text(
                'package demo.deployment\nimport "service.fidl"\nimport "second.cdepl"\n'
                "specification someip { for interfaces { SomeIpServiceID: Integer; "
                "FirstMarker: Integer (optional); } }\n"
                "define someip for interface demo.API as First { use Second "
                "SomeIpServiceID = 40 FirstMarker = 1 }\n",
                encoding="utf-8",
            )
            second.write_text(
                'package demo.deployment\nimport "service.fidl"\nimport "first.fdepl"\n'
                "specification someip { for interfaces { SomeIpServiceID: Integer; "
                "SecondMarker: Integer (optional); } }\n"
                "specification ipc { for interfaces { IpcServiceId: Integer; } }\n"
                "define someip for interface demo.API as Second { use First "
                "SomeIpServiceID = 40 SecondMarker = 2 }\n"
                "define ipc for interface demo.API { IpcServiceId = 80 }\n",
                encoding="utf-8",
            )

            parser = FrancaParser(root_files=[first], dependency_files=[second, design])
            parsed_files = parser.parse_files()
            transformer = FrancaFileGraphTransformer(parsed_files)
            transformer.transform_files()
            first_deployment = transformer.transformed_files[first.resolve()].interface_deployments[0]
            second_deployment = transformer.transformed_files[second.resolve()].interface_deployments[0]
            self.assertIs(first_deployment.use_definitions[0], second_deployment)
            self.assertIs(second_deployment.use_definitions[0], first_deployment)

        interfaces = [element for element in ModelRegistry.elements.values() if isinstance(element, ServiceInterface)]
        self.assertEqual(len(interfaces), 2)
        self.assertEqual(
            {
                interface.deployment_binding.network: interface.interface_deployment_properties
                for interface in interfaces
            },
            {
                NetworkKind.SOMEIP: {"SomeIpServiceID": 40, "FirstMarker": 1, "SecondMarker": 2},
                NetworkKind.IPC: {"IpcServiceId": 80},
            },
        )

        applier = DeploymentPropertyApplier()
        parsed_first = parsed_files[first.resolve()]
        file_transformer = FDEPLTransformer(transformer.transformed_files, parsed_first, applier)
        file_transformer.transform_file()
        self.assertEqual(
            applier.service_Interface_map[("demo.API", NetworkKind.SOMEIP)].interface_deployment_properties,
            {"SomeIpServiceID": 40, "FirstMarker": 1},
        )

    def test_runner_ignores_interface_deployments_without_supported_binding(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory)
            design = path / "service.fidl"
            deployment = path / "service.cdepl"
            output = path / "model.pkl"
            design.write_text(
                "package demo\n"
                "interface API { version { major 1 minor 0 } }\n"
                "interface DiagnosticsOnly { version { major 1 minor 0 } }\n",
                encoding="utf-8",
            )
            deployment.write_text(
                'package demo.deployment\nimport "service.fidl"\n'
                "specification someip { for interfaces { Marker: Integer (optional); "
                "SomeIpServiceID: Integer; } }\n"
                "specification ipc { for interfaces { Marker: Integer (optional); "
                "IpcServiceId: Integer; } }\n"
                "specification diagnostic { for interfaces { Marker: Integer (optional); } }\n"
                "specification architecture extends someip {}\n"
                "define diagnostic for interface demo.API { Marker = 101 }\n"
                "define architecture for interface demo.API { SomeIpServiceID = 40 Marker = 1 }\n"
                "define ipc for interface demo.API { IpcServiceId = 80 Marker = 2 }\n"
                "define diagnostic for interface demo.API { Marker = 303 }\n"
                'define diagnostic for interface demo.DiagnosticsOnly { Marker = "invalid" }\n',
                encoding="utf-8",
            )

            main(["--src", str(deployment), "--dep", str(design), "--output", str(output)])
            ModelRegistry.deserialize(output.read_bytes())

        interfaces = [element for element in ModelRegistry.elements.values() if isinstance(element, ServiceInterface)]
        self.assertEqual(len(interfaces), 2)
        self.assertEqual(
            {
                interface.deployment_binding.network: interface.interface_deployment_properties
                for interface in interfaces
            },
            {
                NetworkKind.SOMEIP: {"SomeIpServiceID": 40, "Marker": 1},
                NetworkKind.IPC: {"IpcServiceId": 80, "Marker": 2},
            },
        )
        self.assertEqual(
            {interface.deployment_binding.network: interface.service_id for interface in interfaces},
            {NetworkKind.SOMEIP: 40, NetworkKind.IPC: 80},
        )
        self.assertTrue(all(interface.design_element.name.as_str == "API" for interface in interfaces))

    def run_parser(self, source: str, *, preprocess: bool = False) -> list[InterfaceDefinition]:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "input.fidl"
            output = Path(directory) / "model.pkl"
            path.write_text(source, encoding="utf-8")
            arguments = ["--src", str(path), "--output", str(output)]
            if preprocess:
                arguments.extend(["--need-preprocessor", "--defined", "FEATURE"])
            main(arguments)
            ModelRegistry.deserialize(output.read_bytes())
        return [element for element in ModelRegistry.elements.values() if isinstance(element, InterfaceDefinition)]

    def test_runner_preserves_shared_types_and_overloads_without_interface_inheritance(self) -> None:
        interfaces = self.run_parser("""package example
            typeCollection Types {
                struct Container { Types.Payload payload }
                struct Payload { Types.Container container }
            }
            interface Base { version { major 1 minor 0 } method ping {} }
            interface API extends Base {
                version { major 1 minor 0 }
                enumeration Errors { FAILED }
                method query:first { in { Types.Payload value } error Errors }
                method query:second { in { String value } }
                broadcast changed { out { Types.Payload value } }
                attribute Types.Payload status readonly
            }
        """)
        interface = interfaces[1]
        self.assertFalse(hasattr(interface, "base"))
        self.assertNotIn(SelectableIdentifier("ping"), interface.methods)
        container = next(
            element
            for element in ModelRegistry.elements.values()
            if isinstance(element, DataTypeBase) and element.name.as_str == "Container"
        )
        payload = next(
            element
            for element in ModelRegistry.elements.values()
            if isinstance(element, DataTypeBase) and element.name.as_str == "Payload"
        )
        errors = interface.datatypes[0]
        method = interface.methods[SelectableIdentifier("query:first")]
        self.assertIs(method.inputs[0].data_type, payload)
        self.assertIs(method.error_return_codes, errors)
        self.assertIs(container.fields[0].data_type, payload)
        self.assertIs(payload.fields[0].data_type, container)
        self.assertIs(ModelRegistry.elements[payload.id], payload)
        self.assertTrue(
            all(
                element.source_kind == DataTypeSource.FRANCA
                for element in ModelRegistry.elements.values()
                if isinstance(element, DataTypeBase)
            )
        )

    def test_preprocessor_still_passes_selected_source_in_memory(self) -> None:
        interfaces = self.run_parser(
            """package example
#if defined FEATURE
interface Selected { version { major 1 minor 0 } method ping {} }
#else
deliberately invalid source
#endif
""",
            preprocess=True,
        )
        self.assertEqual(interfaces[0].name.as_str, "Selected")

    def test_ignored_constructs_do_not_create_parallel_models(self) -> None:
        interface = self.run_parser("""package example
            interface API extends Missing manages Unresolved {
                version { major 1 minor 0 }
                const UInt32 ignored = 1
                method ping {}
                broadcast changed selective {}
                contract { PSM { initial Idle state Idle { on call ping -> Idle } } }
            }
        """)[0]
        self.assertEqual(len(interface.methods), 1)
        self.assertFalse(
            any(
                type(element).__module__.startswith("score.parsers.franca_parser.model")
                for element in ModelRegistry.elements.values()
            )
        )

    def test_invalid_model_is_not_exported(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.fidl"
            output = Path(directory) / "model.pkl"
            path.write_text("package example interface API { method query { error { FAILED } } }", encoding="utf-8")
            with self.assertRaises((ValueError, VisitError)):
                main(["--src", str(path), "--output", str(output)])
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
