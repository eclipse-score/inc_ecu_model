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

"""Verify layout collection and C++ generation from trusted mock model pickles."""

import json
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from score.ecu_model.common.version import Version
from score.ecu_model.communication.service_interface import (
    Attribute,
    Broadcast,
    InterfaceDefinition,
    Method,
    ServiceInterface,
)
from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import DataTypeSource
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.model import ModelElement, ModelRegistry
from score.generators.src import generator_runner
from score.generators.src.layout.element_layout import ElementLayout, StringEncoding
from score.generators.src.layout.header_renderer import HeaderRenderer
from score.generators.src.layout.layout_collector import LayoutCollector
from score.generators.src.layout.layout_generator import LayoutGenerator

type _Member = Attribute | Method | Broadcast


class LayoutGeneratorTest(unittest.TestCase):
    """Exercise the shared generator contract without registering a production runner."""

    def setUp(self) -> None:
        """Keep generated model and interned layout instances local to each test."""
        original_models = ModelRegistry.elements
        original_layouts = ElementLayout._instances
        ModelRegistry.elements = {}
        ElementLayout._instances = {}
        self.addCleanup(setattr, ModelRegistry, "elements", original_models)
        self.addCleanup(setattr, ElementLayout, "_instances", original_layouts)

    @staticmethod
    def _service(
        *members: _Member,
        properties: dict[str, dict[str, object]] | None = None,
        deployment_name: str = "DemoDeployment",
        namespace: tuple[str, ...] = (),
    ) -> ServiceInterface:
        properties = {} if properties is None else properties
        attributes = {member.name: member for member in members if isinstance(member, Attribute)}
        methods = {member.name: member for member in members if isinstance(member, Method)}
        broadcasts = {member.name: member for member in members if isinstance(member, Broadcast)}
        design = InterfaceDefinition(
            name=Identifier("Demo"),
            version=Version(),
            attributes=attributes,
            methods=methods,
            broadcasts=broadcasts,
        )
        return ServiceInterface(
            name=Identifier(deployment_name),
            namespace=QualifiedName(tuple(Identifier(name) for name in namespace)),
            design_element=design,
            attribute_deployment_properties={name: properties.get(str(name), {}) for name in attributes},
            method_deployment_properties={name: properties.get(str(name), {}) for name in methods},
            broadcast_deployment_properties={name: properties.get(str(name), {}) for name in broadcasts},
        )

    @staticmethod
    def _model(*services: ServiceInterface):
        return {"service_interfaces": {service.id: service for service in services}}

    @staticmethod
    def _attribute(name: str = "value") -> Attribute:
        return Attribute(name=Identifier(name), data_type=PrimitiveDataType.UINT32)

    def test_collector_selects_only_concrete_deployments_in_registry_order(self) -> None:
        first = self._service(self._attribute())
        second = self._service(Method(name=SelectableIdentifier("call")))
        unrelated = ModelElement()
        model = self._model(first, second)
        model["data_types"] = {unrelated.id: unrelated}

        collected = LayoutCollector.collect(model)

        self.assertEqual(len(collected), 2)
        self.assertIs(collected[0], first)
        self.assertIs(collected[1], second)
        self.assertIn(unrelated.id, model["data_types"])

    def test_collector_does_not_read_deployments_from_datatype_section(self) -> None:
        service = self._service(self._attribute())
        model = {"data_types": {service.id: service}, "service_interfaces": {}}

        self.assertEqual(LayoutCollector.collect(model), ())
        self.assertEqual(LayoutCollector.collect({"data_types": {service.id: service}}), ())

    def test_models_without_members_produce_no_files(self) -> None:
        datatype = StructDataType(name="Status", source_kind=DataTypeSource.FRANCA)
        models = (
            {"data_types": {datatype.id: datatype}, "service_interfaces": {}},
            {"data_types": {datatype.id: datatype}},
            self._model(self._service()),
        )
        for model in models:
            with self.subTest(model=model), tempfile.TemporaryDirectory() as temporary_directory:
                output_dir = Path(temporary_directory) / "out"
                LayoutGenerator().generate(model, output_dir)
                self.assertFalse(output_dir.exists())

    def test_mock_pickle_runs_through_existing_runner_without_model_mutation(self) -> None:
        array = ArrayDataType(
            source_kind=DataTypeSource.FRANCA,
            is_inline=True,
            data_type=PrimitiveDataType.UINT16,
        )
        datatype = StructDataType(
            name="Status",
            source_kind=DataTypeSource.FRANCA,
            fields=(
                DataTypeField(
                    name=Identifier("samples"),
                    data_type=array,
                    deployment_properties={"SomeIpArrayLengthWidth": 2},
                ),
            ),
        )
        attribute = Attribute(name=Identifier("status"), data_type=datatype)
        service = self._service(
            attribute,
            properties={"status": {"SomeIpAttributeEndianess": "le", "SomeIpStructLengthWidth": 1}},
        )
        model = {"data_types": {datatype.id: datatype}, "service_interfaces": {service.id: service}}
        payload = pickle.dumps(model)
        restored = pickle.loads(payload)
        self.assertEqual(set(restored), {"data_types", "service_interfaces"})
        restored_service = restored["service_interfaces"][service.id]
        self.assertIs(
            restored_service.design_element.attributes[attribute.name].data_type, restored["data_types"][datatype.id]
        )
        before = restored_service.model_dump()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "model.pkl"
            input_path.write_bytes(payload)
            with patch.object(generator_runner, "GENERATOR_FACTORIES", (LayoutGenerator,)):
                generator_runner.GeneratorRunner().run(input_path, root / "out")
            content = (root / "out/someip/layouts.h").read_text(encoding="utf-8")
            report = json.loads((root / "out/someip/member_layouts.json").read_text(encoding="utf-8"))
            self.assertEqual(input_path.read_bytes(), payload)
            LayoutGenerator().generate(restored, root / "direct")
            self.assertEqual(content, (root / "direct/someip/layouts.h").read_text(encoding="utf-8"))
            self.assertEqual(
                report,
                json.loads((root / "direct/someip/member_layouts.json").read_text(encoding="utf-8")),
            )

        self.assertEqual(restored_service.model_dump(), before)
        self.assertIn("LittleEndian_8_2_4_1_Utf8", content)
        self.assertIn(
            "ByteOrder::kLittleEndian,\n    8U,\n    2U,\n    4U,\n    1U,\n    StringEncoding::kUtf8,", content
        )

    def test_registered_runner_runs_layout_generator(self) -> None:
        service = self._service(self._attribute())
        model = {"data_types": {}, "service_interfaces": {service.id: service}}
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_path = root / "model.pkl"
            input_path.write_bytes(pickle.dumps(model))

            generator_runner.GeneratorRunner().run(input_path, root / "out")

            self.assertTrue((root / "out/someip/layouts.h").is_file())
            self.assertTrue((root / "out/someip/member_layouts.json").is_file())

    def test_all_member_kinds_and_services_share_one_deduplicated_header(self) -> None:
        first = self._service(
            self._attribute(),
            Method(name=SelectableIdentifier("call")),
            Broadcast(name=SelectableIdentifier("event")),
            namespace=("first",),
        )
        second = self._service(self._attribute(), namespace=("second",))
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            LayoutGenerator().generate(self._model(first, second), root)
            content = (root / "someip/layouts.h").read_text(encoding="utf-8")
            report = json.loads((root / "someip/member_layouts.json").read_text(encoding="utf-8"))
            self.assertEqual([path.relative_to(root).as_posix() for path in root.rglob("*.h")], ["someip/layouts.h"])

        self.assertEqual(content.count("inline constexpr ElementLayout kLayout_"), 1)
        self.assertEqual(content.count('{"BigEndian_8_4_4_0_Utf8", &kLayout_'), 1)
        self.assertIn("FindLayout(", content)
        self.assertIn("return nullptr;", content)
        self.assertIn("namespace score::ecu_model::someip::layout", content)
        self.assertEqual(set(report["service_interfaces"]), {"first.DemoDeployment", "second.DemoDeployment"})
        demo = report["service_interfaces"]["first.DemoDeployment"]
        self.assertEqual(demo["fields"]["value"], {"Demo.value": "BigEndian_8_4_4_0_Utf8"})
        self.assertEqual(demo["methods"]["call"], {"Demo.call": "BigEndian_8_4_4_0_Utf8"})
        self.assertEqual(demo["events"]["event"], {"Demo.event": "BigEndian_8_4_4_0_Utf8"})

    def test_method_and_broadcast_deployment_properties_are_used(self) -> None:
        method = Method(name=SelectableIdentifier("call"))
        event = Broadcast(
            name=SelectableIdentifier("event"),
            outputs=[
                DataTypeField(
                    name=Identifier("text"),
                    data_type=PrimitiveDataType.STRING,
                    deployment_properties={"SomeIpStringEncoding": "utf16be", "SomeIpStringLengthWidth": 2},
                )
            ],
        )
        service = self._service(method, event, properties={"call": {"SomeIpMethodEndianess": "le"}})
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            LayoutGenerator().generate(self._model(service), root)
            content = (root / "someip/layouts.h").read_text(encoding="utf-8")

        self.assertIn("LittleEndian_8_4_4_0_Utf8", content)
        self.assertIn("BigEndian_8_4_2_0_Utf16", content)
        self.assertIn("StringEncoding::kUtf16,", content)

    def test_header_order_does_not_depend_on_service_registry_order(self) -> None:
        big = self._service(self._attribute(), deployment_name="DemoBig")
        little = self._service(
            self._attribute(),
            properties={"value": {"SomeIpAttributeEndianess": "le"}},
            deployment_name="DemoLittle",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            LayoutGenerator().generate(self._model(little, big), root / "first")
            LayoutGenerator().generate(self._model(big, little), root / "second")
            first = (root / "first/someip/layouts.h").read_bytes()
            self.assertEqual(first, (root / "second/someip/layouts.h").read_bytes())

        self.assertLess(first.index(b"kLayout_BigEndian"), first.index(b"kLayout_LittleEndian"))

    def test_repeated_calls_emit_only_layouts_used_by_current_model(self) -> None:
        big = self._service(self._attribute())
        little = self._service(self._attribute(), properties={"value": {"SomeIpAttributeEndianess": "le"}})
        generator = LayoutGenerator()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            generator.generate(self._model(little), root / "first")
            generator.generate(self._model(big), root / "second")
            content = (root / "second/someip/layouts.h").read_text(encoding="utf-8")

        self.assertIsNotNone(ElementLayout.find("LittleEndian_8_4_4_0_Utf8"))
        self.assertNotIn("LittleEndian", content.replace("kLittleEndian", ""))
        self.assertIn("kLayout_BigEndian_8_4_4_0_Utf8", content)

    def test_invalid_layout_fails_before_writing_header(self) -> None:
        service = self._service(
            self._attribute(),
            properties={"value": {"SomeIpStringEncoding": "utf16le", "SomeIpStringLengthWidth": 4}},
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "out"
            with self.assertRaisesRegex(RuntimeError, "conflicting endianess"):
                LayoutGenerator().generate(self._model(service), root)
            self.assertFalse(root.exists())

    def test_custom_path_and_overwrite_protection(self) -> None:
        model = self._model(self._service(self._attribute()))
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            generator = LayoutGenerator(header_path="demo/wire_layouts.h")
            generator.generate(model, root)
            header = root / "demo/wire_layouts.h"
            self.assertTrue(header.is_file())
            original = header.read_bytes()
            with self.assertRaises(FileExistsError):
                generator.generate(model, root)
            self.assertEqual(header.read_bytes(), original)

    def test_output_path_must_stay_below_output_root(self) -> None:
        model = self._model(self._service(self._attribute()))
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with self.assertRaises(ValueError):
                LayoutGenerator(header_path="../escape.h").generate(model, root / "out")
            self.assertFalse((root / "escape.h").exists())

    def test_renderer_preserves_all_six_layout_fields(self) -> None:
        layout = ElementLayout.intern(
            alignment_bits=128,
            vector_length_field_bytes=0,
            string_length_field_bytes=2,
            struct_length_field_bytes=4,
            string_encoding=StringEncoding.UTF16,
        )
        content = HeaderRenderer().render("someip/layouts.h", (layout,))
        self.assertIn(
            "ByteOrder::kBigEndian,\n    128U,\n    0U,\n    2U,\n    4U,\n    StringEncoding::kUtf16,", content
        )
        self.assertIn('{"BigEndian_128_0_2_4_Utf16", &kLayout_BigEndian_128_0_2_4_Utf16}', content)


if __name__ == "__main__":
    unittest.main()
