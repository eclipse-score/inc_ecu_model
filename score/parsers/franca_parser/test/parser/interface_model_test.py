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

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from lark.exceptions import VisitError

from score.ecu_model.communication.service_interface import InterfaceDefinition
from score.ecu_model.data_types.common import DataTypeBase, DataTypeSource
from score.ecu_model.data_types.identifier import SelectableIdentifier
from score.ecu_model.model import ModelRegistry
from score.parsers.franca_parser.franca_model_parser_runner import main


class InterfaceModelRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        ModelRegistry.elements.clear()

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
