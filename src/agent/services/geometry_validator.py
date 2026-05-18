"""
Geometry Validation Service

Validates that a .3dm model's DOCUMENT-LEVEL objects are exclusively
BLOCK INSTANCES. Note: rhino3dm's model.Objects also lists the geometry
inside each InstanceDefinition (objects with Attributes
.IsInstanceDefinitionObject == True); that internal block geometry is
skipped — only top-level placed objects are checked:
- Top-level objects must be ONLY InstanceReference (no loose geometry)
- At least one block instance must exist
- Each placed instance has valid geometry
- Each placed instance has a non-degenerate bounding box
- Each placed instance has non-zero volume

See memory-bank/decisions.md.
"""

import structlog
from typing import List

try:
    import rhino3dm
except ImportError:
    rhino3dm = None  # For test environment without rhino3dm installed

# Conditional imports: src.agent.* preferred (tests + dev), fallback to direct (production)
try:
    from src.agent.constants import (
        GEOMETRY_CATEGORY_NAME,
        MIN_VALID_VOLUME,
        GEOMETRY_ERROR_INVALID,
        GEOMETRY_ERROR_NULL,
        GEOMETRY_ERROR_DEGENERATE_BBOX,
        GEOMETRY_ERROR_ZERO_VOLUME,
    )
except ImportError:
    from constants import (
        GEOMETRY_CATEGORY_NAME,
        MIN_VALID_VOLUME,
        GEOMETRY_ERROR_INVALID,
        GEOMETRY_ERROR_NULL,
        GEOMETRY_ERROR_DEGENERATE_BBOX,
        GEOMETRY_ERROR_ZERO_VOLUME,
    )

# Import backend schema for validation errors.
# ValidationErrorItem lives in src/backend/schemas.py. The bare `schemas`
# import resolves in the backend test container; the agent-worker (the real
# Celery worker / prod) only resolves `src.backend.schemas`. The previous
# try/except had two identical branches (no working fallback) and crashed the
# graph in the agent-worker — see memory-bank/decisions.md.
try:
    from schemas import ValidationErrorItem
except ModuleNotFoundError:
    from src.backend.schemas import ValidationErrorItem

logger = structlog.get_logger()


class GeometryValidator:
    """
    Service for validating geometric integrity of Rhino objects.

    Performs 3D geometry validation to detect:
    - Invalid geometry (Rhino's internal validity checks)
    - Null/missing geometry
    - Degenerate bounding boxes
    - Zero-volume solids (Brep/Mesh)
    """

    def __init__(self):
        """Initialize geometry validator with logging."""
        logger.info("geometry_validator.initialized")

    def _get_object_id(self, obj) -> str:
        """
        Extract object ID from Rhino object attributes.

        Args:
            obj: Rhino File3dmObject

        Returns:
            String representation of object UUID
        """
        return str(obj.Attributes.Id)

    def validate_geometry(
        self,
        model  # rhino3dm.File3dm (type hint omitted for test compatibility)
    ) -> List[ValidationErrorItem]:
        """
        Validate all geometric objects in a .3dm file.

        Args:
            model: Parsed rhino3dm File3dm object

        Returns:
            List of ValidationErrorItem for objects with invalid geometry.
            Empty list if all geometry is valid.

        Examples:
            >>> validator = GeometryValidator()
            >>> model = rhino3dm.File3dm.Read("valid_model.3dm")
            >>> errors = validator.validate_geometry(model)
            >>> len(errors)
            0
        """
        errors = []

        # Defensive programming
        if model is None:
            logger.warning("geometry_validator.validate_geometry.none_input")
            return errors

        # A valid block .3dm must be composed EXCLUSIVELY of BLOCK INSTANCES
        # (InstanceReference) at the DOCUMENT level.
        #
        # IMPORTANT: rhino3dm's model.Objects also contains the geometry that
        # makes up each InstanceDefinition (Breps on T_Jnt/ref/… layers). That
        # is the *internal* geometry of the blocks, NOT loose document geometry,
        # and must NOT be validated nor counted. Such objects carry
        # Attributes.IsInstanceDefinitionObject == True. We only inspect the
        # top-level placed objects (IsInstanceDefinitionObject == False).
        # See memory-bank/decisions.md.
        instances = []
        non_instances = []  # (object_id, geometry_type) of disallowed geometry
        for obj in model.Objects:
            # Skip block-definition internal geometry (content of the blocks).
            if getattr(obj.Attributes, "IsInstanceDefinitionObject", False):
                continue
            if obj.Geometry is None:
                # No geometry at all is also not a valid block instance.
                non_instances.append((self._get_object_id(obj), "None"))
                continue
            geom_type = obj.Geometry.__class__.__name__
            if geom_type == "InstanceReference":
                instances.append(obj)
            else:
                non_instances.append((self._get_object_id(obj), geom_type))

        logger.info(
            "geometry_validator.validate_geometry.started",
            total_objects=len(model.Objects),
            top_level_objects=len(instances) + len(non_instances),
            instance_count=len(instances),
            non_instance_count=len(non_instances),
        )

        # Rule 1: the model must contain ONLY block instances.
        if non_instances:
            from collections import Counter
            type_breakdown = dict(Counter(t for _, t in non_instances))
            errors.append(ValidationErrorItem(
                category=GEOMETRY_CATEGORY_NAME,
                target="model",
                message=(
                    f"Model must contain only block instances (InstanceReference); "
                    f"found {len(non_instances)} disallowed geometry object(s): "
                    f"{type_breakdown}."
                ),
            ))
            logger.debug("geometry_validator.validation_failed",
                         failure_reason="non_instance_geometry_present",
                         non_instance_types=type_breakdown)

        # Rule 2: there must be at least one block instance.
        if not instances:
            errors.append(ValidationErrorItem(
                category=GEOMETRY_CATEGORY_NAME,
                target="model",
                message=(
                    "No block instances (InstanceReference) found in the model; "
                    "a valid block .3dm must contain at least one placed instance."
                ),
            ))
            logger.info("geometry_validator.validate_geometry.completed",
                        instances_checked=0, errors_found=len(errors))
            return errors

        for obj in instances:
            object_id = self._get_object_id(obj)
            geom = obj.Geometry

            # Check 1: Invalid instance geometry
            if not geom.IsValid:
                errors.append(ValidationErrorItem(
                    category=GEOMETRY_CATEGORY_NAME,
                    target=object_id,
                    message=GEOMETRY_ERROR_INVALID
                ))
                logger.debug("geometry_validator.validation_failed",
                            object_id=object_id,
                            failure_reason="invalid_geometry")

            # Check 2: Degenerate bounding box of the placed instance
            # rhino3dm GetBoundingBox() takes no arguments (unlike .NET Rhino API)
            bbox = geom.GetBoundingBox()
            if not bbox.IsValid:
                errors.append(ValidationErrorItem(
                    category=GEOMETRY_CATEGORY_NAME,
                    target=object_id,
                    message=GEOMETRY_ERROR_DEGENERATE_BBOX
                ))
                logger.debug("geometry_validator.validation_failed",
                            object_id=object_id,
                            failure_reason="degenerate_bbox")
                continue  # cannot compute a meaningful volume without a bbox

            # Check 3: Zero-volume placed instance
            volume = (bbox.Max.X - bbox.Min.X) * (bbox.Max.Y - bbox.Min.Y) * (bbox.Max.Z - bbox.Min.Z)
            if volume < MIN_VALID_VOLUME:
                errors.append(ValidationErrorItem(
                    category=GEOMETRY_CATEGORY_NAME,
                    target=object_id,
                    message=GEOMETRY_ERROR_ZERO_VOLUME.format(min_volume=MIN_VALID_VOLUME)
                ))
                logger.debug("geometry_validator.validation_failed",
                            object_id=object_id,
                            failure_reason="zero_volume",
                            volume=volume)

        logger.info("geometry_validator.validate_geometry.completed",
                    instances_checked=len(instances),
                    errors_found=len(errors))

        return errors
