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

"""Write generated text below an explicit output root."""

from pathlib import Path


class OutputWriter:
    """Write UTF-8 text with LF endings, rejecting escapes and existing files."""

    def __init__(self, output_dir: Path) -> None:
        """Bind writes to a single output root without creating it yet."""
        self._output_dir = output_dir.resolve()

    def write(self, relative_path: str, content: str) -> None:
        """Create one output file, never silently overwriting another artifact."""
        path = Path(relative_path)
        if not path.parts or path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Output path must be relative and remain below the output root: {relative_path}")
        destination = (self._output_dir / path).resolve()
        if not destination.is_relative_to(self._output_dir):
            raise ValueError(f"Output path escapes the output root: {relative_path}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(content.replace("\r\n", "\n").replace("\r", "\n"))
