"""
schemaperfect: tools for generating Python APIs from JSON schemas
"""
from .schemaperfect import SchemaBase, Undefined, SchemaValidationError
from .decorator import schemaclass
from .utils import SchemaInfo
from .codegen import SchemaModuleGenerator
from .version import version as __version__


__all__ = (
    "SchemaBase",
    "Undefined",
    "schemaclass",
    "SchemaInfo",
    "SchemaModuleGenerator",
    "SchemaValidationError"
)
