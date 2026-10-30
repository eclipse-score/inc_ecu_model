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

"""Tests for generator-independent rendering and file output."""

import hashlib
import tempfile
import unittest
from pathlib import Path

from jinja2 import TemplateNotFound, UndefinedError

from score.generators.src.common.common_utils import generate_header_file_guard
from score.generators.src.common.output_writer import OutputWriter
from score.generators.src.common.template_renderer import TemplateRenderer


class CommonUtilsTest(unittest.TestCase):
    """Exercise shared guard calculation without datatype dependencies."""

    def test_guard_preserves_vector_style_with_a_96_bit_path_digest(self):
        """All Vector separators are replaced and the original path determines the digest."""
        path = "foo/bar-Count\\Value.h"

        guard = generate_header_file_guard(path)

        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:24].upper()
        self.assertEqual(guard, f"FOO_BAR_COUNT_VALUE_H_{digest}_")
        self.assertRegex(guard, r"^FOO_BAR_COUNT_VALUE_H_[0-9A-F]{24}_$")
        self.assertEqual(generate_header_file_guard(path), guard)

    def test_paths_with_the_same_readable_prefix_have_different_guards(self):
        """Separator, underscore and case differences remain in the digest input."""
        paths = ("foo/bar/Count.h", "foo_bar/Count.h", "foo/bar_Count.h", "Foo/bar/Count.h")

        guards = [generate_header_file_guard(path) for path in paths]

        self.assertEqual(len(set(guards)), len(paths))
        for guard in guards:
            self.assertTrue(guard.startswith("FOO_BAR_COUNT_H_"))

    def test_guard_collapses_double_underscores_including_at_the_digest_boundary(self):
        """Readable path normalization never creates reserved double underscores."""
        for path in ("foo__bar/Count.h", "foo/-bar/Count.h", "foo/Count.h_"):
            with self.subTest(path=path):
                guard = generate_header_file_guard(path)

                self.assertNotIn("__", guard)
                self.assertRegex(guard, r"^[A-Z][A-Z0-9_]*_[0-9A-F]{24}_$")

    def test_invalid_or_reserved_macro_names_are_rejected(self):
        """Invalid paths are rejected rather than silently adding a different prefix."""
        for path in ("", "_private/Count.h", "9foo/Count.h", "/foo/Count.h", "foo/Count?.h"):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "include guard"):
                generate_header_file_guard(path)


class OutputTest(unittest.TestCase):
    """Exercise the shared modules without importing datatype models."""

    def test_renderer_returns_text_with_literal_cpp_characters_and_trailing_newline(self):
        """Rendering preserves text rather than applying HTML escaping."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            template_dir = Path(temporary_directory)
            (template_dir / "example.j2").write_text("{{ value }}\n", encoding="utf-8")

            result = TemplateRenderer(template_dir).render("example.j2", {"value": "std::vector<int>"})

            self.assertEqual(result, "std::vector<int>\n")
            self.assertEqual(len(list(template_dir.iterdir())), 1)

    def test_missing_template_and_missing_variables_fail_explicitly(self):
        """No missing input silently produces incomplete generated text."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            template_dir = Path(temporary_directory)
            (template_dir / "example.j2").write_text("{{ required_value }}", encoding="utf-8")
            renderer = TemplateRenderer(template_dir)

            with self.assertRaises(UndefinedError):
                renderer.render("example.j2", {})
            with self.assertRaises(TemplateNotFound):
                renderer.render("missing.j2", {})

    def test_writer_creates_nested_files_with_utf8_and_lf_endings(self):
        """The writer does not impose header extensions or generator directories."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"

            OutputWriter(output_dir).write("config/settings.txt", "first\r\nsecond\rthird\n")

            self.assertEqual((output_dir / "config/settings.txt").read_bytes(), b"first\nsecond\nthird\n")

    def test_separate_writers_cannot_overwrite_the_same_output_file(self):
        """Collision detection also works across independent generator instances."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            OutputWriter(output_dir).write("shared.txt", "original")

            with self.assertRaises(FileExistsError):
                OutputWriter(output_dir).write("shared.txt", "replacement")

            self.assertEqual((output_dir / "shared.txt").read_text(encoding="utf-8"), "original")

    def test_invalid_paths_fail_before_creating_output_directories(self):
        """Absolute, empty, and parent traversal paths are rejected."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "out"
            for relative_path in ("", ".", "../escape.txt", "nested/../../escape.txt", "/absolute.txt"):
                with self.subTest(path=relative_path), self.assertRaises(ValueError):
                    OutputWriter(output_dir).write(relative_path, "unexpected")

            self.assertFalse(output_dir.exists())

    def test_symlinked_parent_cannot_escape_the_output_root(self):
        """Existing filesystem links do not bypass output containment."""
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "out"
            output_dir.mkdir()
            (output_dir / "escape").symlink_to(root, target_is_directory=True)

            with self.assertRaises(ValueError):
                OutputWriter(output_dir).write("escape/unexpected.txt", "unexpected")

            self.assertFalse((root / "unexpected.txt").exists())


if __name__ == "__main__":
    unittest.main()
