"""Sorgt dafür, dass das Repo-Root auf sys.path liegt, damit `import src...`
in den Tests funktioniert."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
