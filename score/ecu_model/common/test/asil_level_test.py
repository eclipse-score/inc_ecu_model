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

import unittest

from score.ecu_model.common.asil_level import AsilLevel


class TestAsilLevel(unittest.TestCase):
    def test_given_enum_member_then_value_matches_expected_asil_string(self) -> None:
        self.assertEqual(AsilLevel.QM.value, "QM")
        self.assertEqual(AsilLevel.A.value, "ASIL-A")
        self.assertEqual(AsilLevel.B.value, "ASIL-B")
        self.assertEqual(AsilLevel.C.value, "ASIL-C")
        self.assertEqual(AsilLevel.D.value, "ASIL-D")

    def test_given_valid_asil_string_then_member_is_resolved(self) -> None:
        self.assertEqual(AsilLevel("QM"), AsilLevel.QM)
        self.assertEqual(AsilLevel("ASIL-A"), AsilLevel.A)
        self.assertEqual(AsilLevel("ASIL-B"), AsilLevel.B)
        self.assertEqual(AsilLevel("ASIL-C"), AsilLevel.C)
        self.assertEqual(AsilLevel("ASIL-D"), AsilLevel.D)

    def test_given_invalid_asil_string_then_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            AsilLevel("ASIL-X")

    def test_str_representation(self) -> None:
        self.assertEqual(str(AsilLevel.QM), "QM")
        self.assertEqual(str(AsilLevel.D), "ASIL-D")


if __name__ == "__main__":
    unittest.main()
