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


class ModelRegistry(BaseModel):
    """
    This class provides a registry for instances of ModelElement. All objects of type ModelElement are
    automatically tracked in the registry to ensure uniqueness and to make them resolvable by their identifier for the
    whole lifetime of the process.
    Future extensions, additional post-initialization, validation, etc. actions can be implemented here.
    """

    elements: ClassVar[dict[UUID, "ModelElement"]] = {}

    def model_post_init(self, context: Any, /) -> None:
        """
        Post-initialization hook for the model. Overwrite of BaseModel.model_post_init() method.

        This method is called after the model is instantiated and all field validators are applied.

        Args:
            context: Additional context for post-initialization actions.

        Raises:
            TypeError: If the instance is neither the root ModelRegistry nor a ModelElement.
            ValueError: If an instance with the same ID already exists in the registry.
        """
        if type(self) is ModelRegistry:
            # The registry root itself is not tracked in the registry.
            return
        if not isinstance(self, ModelElement):
            raise TypeError(f"Expected instance of ModelElement, got {type(self).__name__}")
        if self.id in ModelRegistry.elements.keys():
            raise ValueError(f"Duplicate instance {str(self)}")
        ModelRegistry.elements[self.id] = self

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


class ModelElement(ModelRegistry):
    """
    Base class to be used by all objects tracked in ModelRegistry.elements.
    """

    """
    Basic configuration for the model element.
    Set strict validation for the model fields, so that the model is re-validated whenever assigned.
    See https://pydantic.dev/docs/validation/dev/api/pydantic/config/ for more details.
    """
    model_config = ConfigDict(
        validate_assignment=True,
    )

    """
    Properties of the model element.
    """
    id: UUID = Field(default_factory=uuid4, description="Unique identifier of the model element")
    description: str = Field(default="", description="Human-readable description of the model element")

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id}, description={self.description})"


class CustomModelElement(ModelElement):
    """
    Abstract base class for domain-specific, proprietary, or OEM extensions injected via plugins.

    Subclasses inherit UUID tracking and registration within ModelRegistry.
    Direct instantiation of CustomModelElement is rejected.
    """

    def model_post_init(self, context: Any, /) -> None:
        """Reject direct instantiation of the abstract CustomModelElement."""
        if type(self) is CustomModelElement:
            raise TypeError("CustomModelElement is abstract, instantiate a concrete custom model element")
        super().model_post_init(context)
