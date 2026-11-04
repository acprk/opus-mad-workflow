"""Repository-relative paths. Override the project root with the MAD_ROOT environment variable."""
import os

ROOT = os.environ.get("MAD_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WK = os.path.join(ROOT, "work")


def P(rel):
    """Resolve a path stored relative to ROOT (absolute paths pass through)."""
    return rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
