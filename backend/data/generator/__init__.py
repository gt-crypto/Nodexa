"""Generator package for synthetic financial data."""
from backend.data.generator.config import GeneratorConfig
from backend.data.generator.service import generate_dataset

__all__ = [
    "GeneratorConfig",
    "generate_dataset",
]
