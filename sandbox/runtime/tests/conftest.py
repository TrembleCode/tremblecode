import os
import sys
from pathlib import Path

# config binds to env at first get_config(); set before any runtime import
os.environ.setdefault("TC_PROJECT_ID", "test-project")
os.environ.setdefault("TC_PROJECT_DIR", "/tmp/tc-test")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
