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

from pydantic import ValidationError

from score.ecu_model.common.version import Version


class TestVersion(unittest.TestCase):
    def test_default_version(self) -> None:
        self.assertEqual(str(Version()), "1.0.0")

    def test_versions_are_ordered_semantically(self) -> None:
        self.assertLess(Version(major=1, minor=2, patch=3), Version(major=1, minor=3, patch=0))

    def test_version_requires_complete_nonzero_version(self) -> None:
        with self.assertRaises(ValidationError):
            Version(major=1)
        with self.assertRaises(ValidationError):
            Version(major=0, minor=0, patch=0)

    def test_version_numbers_reject_boolean_values(self) -> None:
        with self.assertRaises(ValidationError):
            Version(major=True, minor=0, patch=1)


if __name__ == "__main__":
    unittest.main()
