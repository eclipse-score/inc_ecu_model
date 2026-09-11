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

"""Common Lark node transformations for Franca source files."""

from lark import Transformer, v_args

from score.ecu_model.common.common_name_types import Identifier, QualifiedName


class FrancaFileTransformer(Transformer):
    """Base Lark transformer for a single Franca source file."""

    @staticmethod
    def fi_fqn(names: list[Identifier]) -> QualifiedName:
        """Build a Franca fully qualified name."""
        return QualifiedName(names=names)

    @staticmethod
    @v_args(inline=True)
    def f_valid_id(name: object) -> Identifier:
        """Build a validated Franca identifier."""
        return Identifier(str(name).replace("^", ""))

    @staticmethod
    @v_args(inline=True)
    def fi_keywords(keyword: object) -> Identifier:
        """Build an escaped Franca keyword identifier."""
        return Identifier(str(keyword).replace("^", ""))
