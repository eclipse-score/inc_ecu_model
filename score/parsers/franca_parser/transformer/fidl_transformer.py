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

"""Lark transformer for a single FIDL source file."""

from collections.abc import Callable

from lark import Token, Tree, v_args

from score.ecu_model.common.version import Version
from score.ecu_model.communication.service_interface import Attribute, Broadcast, InterfaceDefinition, Method
from score.ecu_model.data_types.array import ArrayDataType
from score.ecu_model.data_types.common import (
    DataTypeBase,
    DataTypeOrReference,
    DataTypeSource,
)
from score.ecu_model.data_types.composite import DataTypeField
from score.ecu_model.data_types.enum import EnumDataType, EnumValue
from score.ecu_model.data_types.identifier import Identifier, QualifiedName, SelectableIdentifier
from score.ecu_model.data_types.map import MapDataType
from score.ecu_model.data_types.primitives import PrimitiveDataType
from score.ecu_model.data_types.struct import StructDataType
from score.ecu_model.data_types.typedef import TypedefDataType
from score.ecu_model.data_types.union import UnionDataType
from score.ecu_model.model import ModelElement
from score.parsers.franca_parser.model.fidl.fidl_file import FIDLFileModel
from score.parsers.franca_parser.model.fidl.type_collection import (
    TypeCollection,
)
from score.parsers.franca_parser.model.franca_file import (
    FrancaFileModel,
    FrancaTransformationContext,
)
from score.parsers.franca_parser.model.parsed_file import ParsedFile
from score.parsers.franca_parser.transformer.base_transformer import (
    FrancaFileTransformer,
    franca_integer,
)
from score.parsers.franca_parser.transformer.resolver.fidl_datatype_resolver import (
    FIDLDataTypeResolver,
    PendingDatatypeReference,
)

PRIMITIVE_TYPES = {
    "boolean": PrimitiveDataType.BOOL,
    "string": PrimitiveDataType.STRING,
    "bytebuffer": PrimitiveDataType.BYTES,
    "double": PrimitiveDataType.DOUBLE,
    "float": PrimitiveDataType.FLOAT,
    "uint8": PrimitiveDataType.UINT8,
    "uint16": PrimitiveDataType.UINT16,
    "uint32": PrimitiveDataType.UINT32,
    "uint64": PrimitiveDataType.UINT64,
    "int8": PrimitiveDataType.INT8,
    "int16": PrimitiveDataType.INT16,
    "int32": PrimitiveDataType.INT32,
    "int64": PrimitiveDataType.INT64,
}

# Grammar elements that may end up in a data type slot: a builtin, a declaration, or a not yet resolved name.
_DATA_TYPE_ELEMENTS = (QualifiedName, DataTypeBase, PrimitiveDataType)


class FIDLTransformer(FrancaFileTransformer):
    """Transform one FIDL source file into declaration models."""

    def __init__(
        self,
        transformed_files: dict[object, FrancaFileModel],
        transformation_context: FrancaTransformationContext,
    ) -> None:
        """Create a transformer with declarations visible from completed imports."""
        super().__init__()
        self._import_resolver = FIDLDataTypeResolver(transformed_files)
        self._transformation_context = transformation_context
        self._pending_datatype_references_by_declaration: dict[int, list[PendingDatatypeReference]] = {}
        self._pending_datatype_references: list[PendingDatatypeReference] = []

    @property
    def pending_datatype_references(self) -> list[PendingDatatypeReference]:
        """Return datatype references unresolved after local FIDL resolution."""
        return self._pending_datatype_references

    def transform_file(self, parsed_file: ParsedFile) -> FIDLFileModel:
        """Produce the file model available to dependent FIDL transformations."""

        file_model = self.transform(parsed_file.parse_tree)
        file_model.file_path = parsed_file.file_path
        file_model.imported_files = parsed_file.imports
        self._apply_declaration_metadata(file_model)
        return file_model

    @staticmethod
    def _declaration_namespace(
        package: QualifiedName,
        type_def_scope: TypeCollection | InterfaceDefinition,
    ) -> QualifiedName:
        """Return the namespace of declarations owned by one type collection."""
        names = list(package.names)
        if type_def_scope.name is not None:
            names.append(type_def_scope.name)
        return QualifiedName(tuple(names))

    @classmethod
    def _apply_declaration_metadata(cls, file_model: FIDLFileModel) -> None:
        """
        * Update the `namespace` field of each interface within the `file_model` parameter.
        * Update the `namespace` and `source_uri` fields of each datatype within every `typeCollection` and `interface`
          blocks of the `file_model` parameter.
        """
        # 1. Update the `namespace` field of each interface
        for interface in file_model.interfaces:
            interface.namespace = file_model.namespace

        # 2. Update the `namespace` and `source_uri` fields of each datatype within type collections and interfaces.
        for type_def_scope in [*file_model.type_collections, *file_model.interfaces]:
            namespace = cls._declaration_namespace(file_model.namespace, type_def_scope)
            for datatype in type_def_scope.datatypes:
                datatype.namespace = namespace
                datatype.source_uri = str(file_model.file_path)

    @staticmethod
    def _next_enum_value(value: int | float | bool | str | None) -> int:
        """Apply the legacy implicit enum-value progression."""
        if isinstance(value, int):
            return value + 1
        return 0

    def resolve_local_references(self, file_model: FIDLFileModel) -> None:
        """Bind references not resolved from imports during transformation."""
        self._pending_datatype_references = self._import_resolver.resolve_local_references(
            self._pending_datatype_references,
            file_model,
        )

    def _record_datatype_references(self, datatype: DataTypeBase) -> None:
        if isinstance(datatype, TypedefDataType):
            self._record_reference(datatype, datatype.data_type, lambda value: setattr(datatype, "data_type", value))
        elif isinstance(datatype, EnumDataType):
            self._record_reference(datatype, datatype.extends, lambda value: setattr(datatype, "extends", value))
        elif isinstance(datatype, (StructDataType, UnionDataType)):
            self._record_reference(datatype, datatype.extends, lambda value: setattr(datatype, "extends", value))
            for field in datatype.fields:
                self._record_field_references(datatype, field)
        elif isinstance(datatype, ArrayDataType):
            self._record_reference(datatype, datatype.data_type, lambda value: setattr(datatype, "data_type", value))
        elif isinstance(datatype, MapDataType):
            self._record_reference(datatype, datatype.key_type, lambda value: setattr(datatype, "key_type", value))
            self._record_reference(datatype, datatype.value_type, lambda value: setattr(datatype, "value_type", value))

    def _record_field_references(self, datatype: ModelElement, field: DataTypeField) -> None:
        if isinstance(field.data_type, ArrayDataType) and field.data_type.is_inline:
            self._record_reference(
                datatype,
                field.data_type.data_type,
                lambda value: setattr(field.data_type, "data_type", value),
            )
        else:
            self._record_reference(datatype, field.data_type, lambda value: setattr(field, "data_type", value))

    def _record_reference(
        self,
        datatype: ModelElement,
        reference: object,
        bind: Callable[[DataTypeOrReference], None],
    ) -> None:
        if isinstance(reference, QualifiedName):
            self._pending_datatype_references_by_declaration.setdefault(id(datatype), []).append(
                PendingDatatypeReference(reference, bind, datatype)
            )

    @staticmethod
    @v_args(inline=True)
    def start(model_root: FIDLFileModel) -> FIDLFileModel:
        """Unwrap the grammar's top-level start rule."""
        return model_root

    @v_args(inline=True)
    def fi_model_root(self, package: QualifiedName, *elements: object) -> FIDLFileModel:
        """Build the FIDL file model from its transformed type collections."""
        # 1. Transform type collections and interfaces
        type_collections: list[TypeCollection] = []  # All `typeCollection` elements in the FIDL file.
        interfaces: list[InterfaceDefinition] = []  # All `interface` elements in the FIDL file.
        used_valid_ids: set[str] = set()  # Duplication check for the names of type collections and interfaces
        for element in elements:
            if isinstance(element, InterfaceDefinition):
                interfaces.append(element)
            elif isinstance(element, TypeCollection):
                type_collections.append(element)
            else:
                continue

            if element.name is None:
                continue
            name = element.name.as_str
            if name in used_valid_ids:
                raise ValueError(f"Duplicate ID {name} found in {self._transformation_context.file_path}")
            used_valid_ids.add(name)

        # 2. Build the FIDL file model
        file_model = FIDLFileModel(
            file_path=self._transformation_context.file_path,
            namespace=package,
            imported_files=self._transformation_context.imported_files,
            type_collections=type_collections,
            interfaces=interfaces,
        )

        # 3. Resolve local references within the FIDL file
        self.resolve_local_references(file_model)
        return file_model

    @staticmethod
    @v_args(inline=True)
    def fi_model_elements(element: object) -> object:
        """Unwrap top-level FIDL model elements."""
        return element

    @staticmethod
    @v_args(inline=True)
    def f_version(major: object, minor: object) -> Version:
        """Transform a FIDL major and minor version declaration."""
        return Version(major=int(str(major)), minor=int(str(minor)), patch=0)

    @v_args(inline=True)
    def fi_type_collection(self, *elements: object) -> TypeCollection:
        """Collect datatype declarations owned by one FIDL type collection."""
        collection = TypeCollection(name=None)
        for element in elements:
            if isinstance(element, Identifier):
                collection.name = element
            elif isinstance(element, DataTypeBase):
                collection.datatypes.append(element)
                for pending in self._pending_datatype_references_by_declaration.pop(id(element), []):
                    pending.owning_collection = collection
                    self._pending_datatype_references.append(pending)
        return collection

    @v_args(inline=True)
    def fi_type(self, datatype: DataTypeBase) -> DataTypeBase:
        """Unwrap one FIDL datatype declaration."""
        if isinstance(datatype, PrimitiveDataType):
            raise ValueError(
                "Bare FIDL primitive datatype declarations are not supported "
                f"in {self._transformation_context.file_path}"
            )
        return datatype

    @staticmethod
    @v_args(inline=True)
    def builtin(data_type: PrimitiveDataType) -> PrimitiveDataType:
        """Unwrap a FIDL primitive type reference."""
        return data_type

    @v_args(inline=True)
    def imported(self, reference: QualifiedName) -> QualifiedName:
        """Keep named references pending until all declarations in the file are available."""
        return reference

    @v_args(inline=True)
    def interval(self, _interval: object) -> object:
        """Reject unsupported FIDL integer interval types."""
        raise ValueError(f"FIDL Integer intervals are not supported in {self._transformation_context.file_path}")

    @v_args(inline=True)
    def fi_type_def(self, *elements: object) -> TypedefDataType:
        """Transform a FIDL typedef declaration."""
        name = next(element for element in elements if isinstance(element, Identifier))
        data_type = next(element for element in elements if isinstance(element, _DATA_TYPE_ELEMENTS))
        datatype = TypedefDataType(name=name, source_kind=DataTypeSource.FRANCA, data_type=data_type)
        self._record_datatype_references(datatype)
        return datatype

    @v_args(inline=True)
    def fi_enumeration_type(self, *elements: object) -> EnumDataType:
        """Transform a FIDL enum declaration and its implicit values."""
        name = next(element for element in elements if isinstance(element, Identifier))
        extends = next((element for element in elements if isinstance(element, _DATA_TYPE_ELEMENTS)), None)
        values: list[EnumValue] = []
        next_value = 0
        for element in elements:
            if not isinstance(element, EnumValue):
                continue
            value = next_value if element.value is None else element.value
            next_value = self._next_enum_value(value)
            if element.value is None:
                element.value = value
            values.append(element)
        enum = EnumDataType(
            name=name,
            source_kind=DataTypeSource.FRANCA,
            extends=extends,
            values=tuple(values),
        )
        self._record_datatype_references(enum)
        return enum

    @staticmethod
    @v_args(inline=True)
    def fi_enumerator(*elements: object) -> EnumValue:
        """Transform one FIDL enum literal."""
        name = next(element for element in elements if isinstance(element, Identifier))
        is_negative = any(isinstance(element, Token) and str(element) == "-" for element in elements)
        value = next(
            (element for element in elements if isinstance(element, int) and not isinstance(element, bool)), None
        )
        if any(isinstance(element, (bool, float, str)) and not isinstance(element, Token) for element in elements):
            raise ValueError("FIDL enum values must be integer literals")
        if is_negative and value is not None:
            value = -value
        return EnumValue(name=name, value=value)

    @v_args(inline=True)
    def fi_struct_type(self, *elements: object) -> StructDataType:
        """Transform a FIDL struct declaration."""
        datatype = StructDataType(
            name=next(element for element in elements if isinstance(element, Identifier)),
            source_kind=DataTypeSource.FRANCA,
            extends=next((element for element in elements if isinstance(element, _DATA_TYPE_ELEMENTS)), None),
            fields=tuple(element for element in elements if isinstance(element, DataTypeField)),
        )
        self._record_datatype_references(datatype)
        return datatype

    @v_args(inline=True)
    def fi_union_type(self, *elements: object) -> UnionDataType:
        """Transform a FIDL union declaration."""
        datatype = UnionDataType(
            name=next(element for element in elements if isinstance(element, Identifier)),
            source_kind=DataTypeSource.FRANCA,
            extends=next((element for element in elements if isinstance(element, _DATA_TYPE_ELEMENTS)), None),
            fields=tuple(element for element in elements if isinstance(element, DataTypeField)),
        )
        self._record_datatype_references(datatype)
        return datatype

    @v_args(inline=True)
    def fi_array_type(self, *elements: object) -> ArrayDataType:
        """Transform a named FIDL array declaration."""
        name = next(element for element in elements if isinstance(element, Identifier))
        data_type = next(element for element in elements if isinstance(element, _DATA_TYPE_ELEMENTS))
        dimensions = next((element for element in elements if isinstance(element, tuple)), None)
        dimension_min, dimension_max = dimensions if dimensions is not None else (None, None)
        datatype = ArrayDataType(
            name=name,
            source_kind=DataTypeSource.FRANCA,
            data_type=data_type,
            dimension_min=dimension_min,
            dimension_max=dimension_max,
        )
        self._record_datatype_references(datatype)
        return datatype

    @v_args(inline=True)
    def fi_map_type(self, *elements: object) -> MapDataType:
        """Transform a FIDL map declaration."""
        name = next(element for element in elements if isinstance(element, Identifier))
        data_types = [element for element in elements if isinstance(element, _DATA_TYPE_ELEMENTS)]
        key_type, value_type = data_types
        datatype = MapDataType(name=name, source_kind=DataTypeSource.FRANCA, key_type=key_type, value_type=value_type)
        self._record_datatype_references(datatype)
        return datatype

    @staticmethod
    @v_args(inline=True)
    def fi_map_from(data_type: object) -> object:
        """Unwrap the map key type reference."""
        return data_type

    @staticmethod
    @v_args(inline=True)
    def fi_map_to(data_type: object) -> object:
        """Unwrap the map value type reference."""
        return data_type

    @staticmethod
    @v_args(inline=True)
    def fi_field(field: DataTypeField) -> DataTypeField:
        """Unwrap a FIDL field declaration."""
        return field

    @staticmethod
    @v_args(inline=True)
    def fi_annotated_field(_annotation: object, field: DataTypeField) -> DataTypeField:
        """Unwrap a FIDL field declaration preceded by annotations."""
        return field

    @staticmethod
    @v_args(inline=True)
    def fi_plain_field(field: DataTypeField) -> DataTypeField:
        """Unwrap an unannotated FIDL field declaration."""
        return field

    @v_args(inline=True)
    def fi_element_declaration(self, data_type: object, *elements: object) -> DataTypeField:
        """Transform a FIDL struct or union field declaration."""
        field_name = next(element for element in elements if isinstance(element, Identifier))
        dimensions = next((element for element in elements if isinstance(element, tuple)), None)
        if dimensions is not None:
            dimension_min, dimension_max = dimensions
            data_type = ArrayDataType(
                source_kind=DataTypeSource.FRANCA,
                data_type=data_type,
                is_inline=True,
                dimension_min=dimension_min,
                dimension_max=dimension_max,
            )
        return DataTypeField(name=field_name, data_type=data_type)

    @staticmethod
    @v_args(inline=True)
    def fi_array_dimension(*dimensions: tuple[str, int]) -> tuple[int | None, int | None]:
        """Preserve the explicitly provided FIDL array bounds."""
        bounds = dict(dimensions)
        return bounds.get("lower"), bounds.get("upper")

    @staticmethod
    @v_args(inline=True)
    def lower_dim(value: object) -> tuple[str, int]:
        """Transform an explicit lower array dimension bound."""
        return "lower", franca_integer(value)

    @staticmethod
    @v_args(inline=True)
    def upper_dim(value: object) -> tuple[str, int]:
        """Transform an explicit upper array dimension bound."""
        return "upper", franca_integer(value)

    @staticmethod
    @v_args(inline=True)
    def integer(value: object) -> int:
        """Transform a decimal, hexadecimal, or binary integer literal."""
        return franca_integer(value)

    @v_args(inline=True)
    def boolean_type(self) -> PrimitiveDataType:
        """Transform the Boolean primitive type name."""
        return PRIMITIVE_TYPES["boolean"]

    @staticmethod
    @v_args(inline=True)
    def boolean_literal(value: object) -> bool:
        """Transform a Boolean literal."""
        return str(value) == "true"

    @v_args(inline=True)
    def string_type(self) -> PrimitiveDataType:
        """Transform the String primitive type name."""
        return PRIMITIVE_TYPES["string"]

    @staticmethod
    @v_args(inline=True)
    def string_literal(value: object) -> str:
        """Transform a string literal while preserving escape text."""
        return str(value).strip("'\"")

    @v_args(inline=True)
    def float_type(self) -> PrimitiveDataType:
        """Transform the Float primitive type name."""
        return PRIMITIVE_TYPES["float"]

    @staticmethod
    @v_args(inline=True)
    def float_literal(value: object) -> str:
        """Transform a Float literal while preserving its source spelling."""
        return str(value)

    @v_args(inline=True)
    def bytebuffer(self) -> PrimitiveDataType:
        """Transform the ByteBuffer primitive type name."""
        return PRIMITIVE_TYPES["bytebuffer"]

    @v_args(inline=True)
    def double_type(self) -> PrimitiveDataType:
        """Transform the Double primitive type name."""
        return PRIMITIVE_TYPES["double"]

    @staticmethod
    @v_args(inline=True)
    def double_literal(value: object) -> str:
        """Transform a Double literal while preserving its source spelling."""
        return str(value)

    @v_args(inline=True)
    def uint8(self) -> PrimitiveDataType:
        """Transform the UInt8 primitive type name."""
        return PRIMITIVE_TYPES["uint8"]

    @v_args(inline=True)
    def uint16(self) -> PrimitiveDataType:
        """Transform the UInt16 primitive type name."""
        return PRIMITIVE_TYPES["uint16"]

    @v_args(inline=True)
    def uint32(self) -> PrimitiveDataType:
        """Transform the UInt32 primitive type name."""
        return PRIMITIVE_TYPES["uint32"]

    @v_args(inline=True)
    def uint64(self) -> PrimitiveDataType:
        """Transform the UInt64 primitive type name."""
        return PRIMITIVE_TYPES["uint64"]

    @v_args(inline=True)
    def int8(self) -> PrimitiveDataType:
        """Transform the Int8 primitive type name."""
        return PRIMITIVE_TYPES["int8"]

    @v_args(inline=True)
    def int16(self) -> PrimitiveDataType:
        """Transform the Int16 primitive type name."""
        return PRIMITIVE_TYPES["int16"]

    @v_args(inline=True)
    def int32(self) -> PrimitiveDataType:
        """Transform the Int32 primitive type name."""
        return PRIMITIVE_TYPES["int32"]

    @v_args(inline=True)
    def int64(self) -> PrimitiveDataType:
        """Transform the Int64 primitive type name."""
        return PRIMITIVE_TYPES["int64"]

    @staticmethod
    @v_args(inline=True)
    def fi_id_with_selector(name: Identifier, selector: Identifier | None = None) -> SelectableIdentifier:
        """Transform a method or broadcast name with an optional selector."""
        return SelectableIdentifier(f"{name}:{selector}" if selector is not None else str(name))

    @staticmethod
    @v_args(inline=True)
    def interface_element(element: object = None) -> object:
        """Return one interface member or datatype declaration."""
        return element

    @v_args(inline=True)
    def fi_interface(self, *elements: object) -> InterfaceDefinition:
        """Lark callback."""
        annotation = next(
            (
                str(element.children[0])
                for element in elements
                if isinstance(element, Tree) and element.data == "f_annotation_block"
            ),
            "",
        )
        name = next((element for element in elements if isinstance(element, Identifier)), None)
        if name is None:
            raise ValueError(f"Interface requires a name in {self._transformation_context.file_path}")
        version = next((element for element in elements if isinstance(element, Version)), None)
        if version is None:
            raise ValueError(
                f"Interface '{name}' requires an explicit version in {self._transformation_context.file_path}"
            )

        methods: dict[SelectableIdentifier, Method] = {}
        broadcasts: dict[SelectableIdentifier, Broadcast] = {}
        attributes: dict[Identifier, Attribute] = {}
        datatypes: list[DataTypeBase] = []
        used_member_names: set[str] = set()
        for element in elements:
            if not isinstance(element, (Method, Broadcast, Attribute, DataTypeBase)):
                continue
            element_name = element.name.as_str
            if element_name in used_member_names:
                raise ValueError(
                    f"Duplicate interface member '{element_name}' in {self._transformation_context.file_path}"
                )
            used_member_names.add(element_name)

            if isinstance(element, Method):
                methods[element.name] = element
            elif isinstance(element, Broadcast):
                broadcasts[element.name] = element
            elif isinstance(element, Attribute):
                attributes[element.name] = element
            elif isinstance(element, DataTypeBase):
                datatypes.append(element)

        interface = InterfaceDefinition(
            name=name,
            description=annotation,
            version=version,
            methods=methods,
            broadcasts=broadcasts,
            attributes=attributes,
            datatypes=datatypes,
        )
        for declaration in [*datatypes, *methods.values(), *broadcasts.values(), *attributes.values()]:
            for pending in self._pending_datatype_references_by_declaration.pop(id(declaration), []):
                pending.owning_collection = interface
                self._pending_datatype_references.append(pending)
        return interface

    @staticmethod
    def fi_method_input(arguments: list[DataTypeField]) -> tuple[str, list[DataTypeField]]:
        """Label method input fields for method construction."""
        return "inputs", arguments

    @staticmethod
    def fi_method_output(arguments: list[DataTypeField]) -> tuple[str, list[DataTypeField]]:
        """Label method output fields for method construction."""
        return "outputs", arguments

    fi_broadcast_output = fi_method_output

    @staticmethod
    def fi_fire_and_forget(_elements: list[object]) -> bool:
        """Mark a fire-and-forget method."""
        return True

    @staticmethod
    @v_args(inline=True)
    def fi_method_error(reference: QualifiedName) -> QualifiedName:
        """Return a named method error reference for later resolution."""
        return reference

    @staticmethod
    def fi_enumeration_type_body(_elements: list[object]) -> None:
        """Reject anonymous method error enumerations."""
        raise ValueError("Anonymous method error enumerations are not supported; reference a named enumeration")

    def _validate_parameter_names(self, name: SelectableIdentifier, arguments: list[DataTypeField]) -> None:
        """Require unique parameter names within one input or output block."""
        if len({argument.name for argument in arguments}) != len(arguments):
            raise ValueError(f"Duplicate parameter in '{name}' ({self._transformation_context.file_path})")

    @v_args(inline=True)
    def fi_method(self, *elements: object) -> Method:
        """Lark callback."""
        description = next(
            (
                str(element.children[0])
                for element in elements
                if isinstance(element, Tree) and element.data == "f_annotation_block"
            ),
            "",
        )
        name = next((element for element in elements if isinstance(element, SelectableIdentifier)), None)
        if name is None:
            raise ValueError(f"Method requires a name in {self._transformation_context.file_path}")
        fire_and_forget = any(element is True for element in elements)
        inputs = next((element[1] for element in elements if isinstance(element, tuple) and element[0] == "inputs"), [])
        outputs = next(
            (element[1] for element in elements if isinstance(element, tuple) and element[0] == "outputs"), []
        )
        error_description = next(
            (
                str(element.children[0].children[0])
                for element in elements
                if isinstance(element, Tree) and element.data == "fi_error_comment"
            ),
            "",
        )
        error = next((element for element in elements if isinstance(element, QualifiedName)), None)

        self._validate_parameter_names(name, inputs)
        self._validate_parameter_names(name, outputs)
        if fire_and_forget and (outputs or error is not None):
            raise ValueError(f"fireAndForget method '{name}' has output or error")

        method = Method(
            name=name,
            description=description,
            inputs=inputs,
            outputs=outputs,
            error_return_codes=error,
            error_description=error_description,
            fire_and_forget=fire_and_forget,
        )
        for argument in [*method.inputs, *method.outputs]:
            self._record_field_references(method, argument)
        self._record_reference(method, error, lambda value: setattr(method, "error_return_codes", value))
        return method

    @staticmethod
    def fi_selective(_elements: list[object]) -> bool:
        """Mark a selective broadcast."""
        return True

    @v_args(inline=True)
    def fi_broadcast(self, *elements: object) -> Broadcast:
        """Transform a broadcast and record its output datatype references."""
        description = next(
            (
                str(element.children[0])
                for element in elements
                if isinstance(element, Tree) and element.data == "f_annotation_block"
            ),
            "",
        )
        name = next((element for element in elements if isinstance(element, SelectableIdentifier)), None)
        if name is None:
            raise ValueError(f"Broadcast requires a name in {self._transformation_context.file_path}")
        selective = any(element is True for element in elements)
        outputs = next(
            (element[1] for element in elements if isinstance(element, tuple) and element[0] == "outputs"), []
        )
        self._validate_parameter_names(name, outputs)
        broadcast = Broadcast(name=name, description=description, outputs=outputs, selective=selective)
        for argument in broadcast.outputs:
            self._record_field_references(broadcast, argument)
        return broadcast

    @staticmethod
    def access_q_readonly(_elements: list[object]) -> str:
        """Return the readonly attribute access qualifier."""
        return "readonly"

    @staticmethod
    def access_q_no_read(_elements: list[object]) -> str:
        """Return the no-read attribute access qualifier."""
        return "noRead"

    @staticmethod
    def access_q_no_subscriptions(_elements: list[object]) -> str:
        """Return the no-subscriptions attribute access qualifier."""
        return "noSubscriptions"

    @staticmethod
    def attr_access_qualifier(qualifiers: list[str]) -> set[str]:
        """Collect attribute access qualifiers."""
        return set(qualifiers)

    @v_args(inline=True)
    def fi_attribute(self, *elements: object) -> Attribute:
        """Lark callback."""
        description = next(
            (
                str(element.children[0])
                for element in elements
                if isinstance(element, Tree) and element.data == "f_annotation_block"
            ),
            "",
        )
        declaration = next((element for element in elements if isinstance(element, DataTypeField)), None)
        if declaration is None:
            raise ValueError(f"Attribute requires a type and name in {self._transformation_context.file_path}")
        qualifiers = next((element for element in elements if isinstance(element, set)), None)
        if qualifiers is None:
            raise ValueError(f"Attribute requires an access qualifier node in {self._transformation_context.file_path}")

        attribute = Attribute(
            name=declaration.name,
            description=description,
            data_type=declaration.data_type,
            has_getter="noRead" not in qualifiers,
            has_setter="readonly" not in qualifiers,
            subscribable="noSubscriptions" not in qualifiers,
        )
        if isinstance(attribute.data_type, ArrayDataType) and attribute.data_type.is_inline:
            self._record_reference(
                attribute,
                attribute.data_type.data_type,
                lambda value: setattr(attribute.data_type, "data_type", value),
            )
        else:
            self._record_reference(attribute, attribute.data_type, lambda value: setattr(attribute, "data_type", value))
        return attribute

    @staticmethod
    def f_annotation_block(annotations: list[Tree]) -> Tree:
        """Lark callback."""
        description = "".join(str(token) for annotation in annotations for token in annotation.children)
        return Tree("f_annotation_block", [description])
