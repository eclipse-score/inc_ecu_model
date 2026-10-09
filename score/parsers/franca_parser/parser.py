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

"""Lark parsing and import discovery for declared Franca source files."""

from pathlib import Path
from typing import Iterable, Optional, Union

from lark import Lark
from lark.exceptions import VisitError

from score.parsers.franca_parser.model.fidl.fidl_file import FIDLFileModel
from score.parsers.franca_parser.model.parsed_file import ParsedFile
from score.parsers.franca_parser.transformer.file_graph_transformer import (
    FrancaFileGraphTransformer,
)
from score.parsers.franca_parser.transformer.import_transformer import (
    FrancaImportTransformer,
)
from score.parsers.franca_parser.preprocessor.batch_runner import BatchRunner
from score.parsers.runner.common import Parser, ParsingPathInfo


class FrancaParser:
    """Parse declared FIDL and FDEPL files with their imports exactly once."""

    def __init__(
        self,
        root_files: list[Path],
        dependency_files: list[Path],
        defined: Optional[list[str]] = None,
        need_preprocessor: bool = False,
    ) -> None:
        """
        Initialize the FrancaParser with root files, dependency files, and optional preprocessor settings.

        :param root_files: List of root Franca source files to parse.
        :param dependency_files: List of dependency Franca source files.
        :param defined: List of preprocessor definitions. For example, if "foo" is in this list, any conditional
            compilation like `#if defined foo ... #endif` will be activated.
        :param need_preprocessor: Flag indicating whether preprocessing is needed.
        """
        self._root_files = root_files
        self._allowed_files = {path.resolve() for path in root_files + dependency_files}
        self._parsed_files: dict[Path, ParsedFile] = {}
        self._grammar_directory = Path(__file__).parent / "grammar"
        self._grammar_names = {
            ".fidl": "franca_fidl.lark",
            ".fdepl": "franca_fdepl.lark",
        }
        self._parsers: dict[str, Lark] = {}
        self._defined = defined or []
        self._need_preprocessor = need_preprocessor

    @property
    def parsed_files(self) -> dict[Path, ParsedFile]:
        """Return parsed files indexed by canonical source path."""
        return self._parsed_files

    def parse_files(self) -> dict[Path, ParsedFile]:
        """Discover and parse every root file and transitive declared import."""
        pending_files = list(self._root_files)
        preprocessed_files = self._preprocess_files(
            self._allowed_files,
            self._defined,
            self._need_preprocessor,
        )

        while pending_files:
            file_path = pending_files.pop().resolve()
            if file_path in self._parsed_files:
                continue
            if file_path not in self._allowed_files:
                raise FileNotFoundError(f"Franca source is not declared as srcs or deps: {file_path}")
            parsed_file = ParsedFile(
                file_path=file_path,
                parse_tree=self._parser_for(file_path).parse(preprocessed_files[str(file_path)]),
            )
            collector = FrancaImportTransformer(lambda import_uri: self._resolve_import_path(file_path, import_uri))
            try:
                collector.transform(parsed_file.parse_tree)
            except VisitError as error:
                if isinstance(error.orig_exc, FileNotFoundError):
                    raise error.orig_exc from error
                raise
            parsed_file.imports = collector.imported_namespaces
            self._parsed_files[file_path] = parsed_file
            pending_files.extend(imported.file_path for imported in parsed_file.imports)
        return self._parsed_files

    def _parser_for(self, file_path: Path) -> Lark:
        """Return the cached parser for a supported file type, creating it on demand."""
        suffix = file_path.suffix
        grammar_name = self._grammar_names.get(suffix)
        if grammar_name is None:
            raise ValueError(f"Unsupported Franca source type: {file_path}")
        if suffix not in self._parsers:
            self._parsers[suffix] = Lark(
                (self._grammar_directory / grammar_name).read_text(),
                parser="lalr",
                import_paths=[self._grammar_directory],
            )
        return self._parsers[suffix]

    def _resolve_import_path(self, importing_file: Path, import_uri: str) -> Path:
        candidate = (importing_file.parent / import_uri).resolve()
        if candidate in self._allowed_files:
            return candidate
        raise FileNotFoundError(f"Could not resolve declared Franca import '{import_uri}' in '{importing_file}'")

    @staticmethod
    def _preprocess_files(
        file_list: Iterable[Union[str, Path]],
        defined_list: list[str],
        need_preprocessor: bool,
    ) -> dict[str, str]:
        if need_preprocessor:
            batch_runner = BatchRunner(file_list=file_list, defined_list=defined_list)
            file_contents = batch_runner.batch_run()
        else:
            file_contents = {}
            for file_path in file_list:
                resolved_path = Path(file_path).resolve()
                file_contents[str(resolved_path)] = resolved_path.read_text(encoding="utf-8")
        return file_contents


class WrapperFrancaParser(Parser):
    def __init__(self, path_info: ParsingPathInfo) -> None:
        """Adapter from runner input to Franca parsing and model transformation."""
        super().__init__(path_info)

        self.franca_files = path_info.src_files
        self.dependency_files = path_info.ext_info.get("dependency_files", ())
        self.defined = path_info.ext_info.get("defined")
        self.need_preprocessor = path_info.ext_info.get("need_preprocessor", False)

    def parse(self) -> dict[str, object]:
        """Parse Franca files and return the transformed file models."""
        if not self.franca_files:
            result: dict[str, object] = {"data_types": {}}
            return result

        root_paths = [Path(file_path) for file_path in self.franca_files]
        dep_paths = [Path(file_path) for file_path in self.dependency_files]

        franca_parser = FrancaParser(
            root_files=root_paths,
            dependency_files=dep_paths,
            defined=self.defined,
            need_preprocessor=self.need_preprocessor,
        )
        parsed_files = franca_parser.parse_files()
        transformed_files = FrancaFileGraphTransformer(parsed_files).transform_files()
        datatypes = {}
        for file_model in transformed_files.values():
            if isinstance(file_model, FIDLFileModel):
                datatypes.update(file_model._datatype_index)

        result = {"data_types": datatypes}

        return result
