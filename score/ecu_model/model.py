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

import pickle
from typing import Any, ClassVar
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class ModelRegistry:
    """
    This class provides a registry for instances of ModelElement. All objects of type ModelElement are
    automatically tracked in the registry to ensure uniqueness and to make them resolvable by their identifier for the
    whole lifetime of the process.
    Future extensions, additional post-initialization, validation, etc. actions can be implemented here.
    """

    elements: ClassVar[dict[UUID, "ModelElement"]] = {}

    @classmethod
    def register(cls, element: "ModelElement") -> None:
        """
        Register a model element by its unique identifier.

        Args:
            element: Model element to register.

        Raises:
            TypeError: If the object is not a ModelElement.
            ValueError: If an element with the same ID already exists in the registry.
        """
        if not isinstance(element, ModelElement):
            raise TypeError(f"Expected instance of ModelElement, got {type(element).__name__}")
        if element.id in ModelRegistry.elements:
            raise ValueError(f"Duplicate instance {str(element)}")
        ModelRegistry.elements[element.id] = element

    @classmethod
    def serialize(cls) -> bytes:
        """
        Pickle the whole registry, i.e. every registered ModelElement.
        """
        return pickle.dumps(ModelRegistry.elements, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def deserialize(cls, data: bytes) -> int:
        """
        Replace the registry with a previously serialized one and return the number of restored elements.

        Args:
            data: Payload produced by serialize().

        Raises:
            TypeError: If the payload does not contain a registry of model elements.
        """
        restored = pickle.loads(data)
        if not isinstance(restored, dict) or not all(
            isinstance(key, UUID) and isinstance(value, ModelElement) for key, value in restored.items()
        ):
            raise TypeError("Payload does not contain a ModelRegistry")
        # Replacing the contents rather than the dict itself keeps existing references to the registry valid.
        ModelRegistry.elements.clear()
        ModelRegistry.elements.update(restored)
        return len(ModelRegistry.elements)


class ModelObject(BaseModel):
    """Base class providing common fields and behavior for model objects.

    Inheriting from this class does not automatically register instances in ModelRegistry.
    Inherit from ModelElement when automatic registration is required.
    """

    model_config = ConfigDict(
        validate_assignment=True,
    )

    id: UUID = Field(default_factory=uuid4, description="Unique identifier of the model element")
    description: str = Field(default="", description="Human-readable description of the model element")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, description={self.description})"


class ModelElement(ModelObject, ModelRegistry):
    """A model object automatically tracked in ModelRegistry."""

    def model_post_init(self, context: Any, /) -> None:
        """Register the element after its fields have been validated."""
        super().model_post_init(context)
        ModelRegistry.register(self)
