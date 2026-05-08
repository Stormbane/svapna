"""Run LoRA training on the 2026-04-18 ceremony dataset.

Standalone runner. Invoked by scripts/train-ceremony.bat, which is either
scheduled via Windows Task Scheduler or run manually.

After training:
  - LoRA adapter saved to models/lora/2026-04-18/
  - latest symlink updated to point at 2026-04-18
  - heartbeat.bat (which uses models/lora/latest) picks up the new weights
"""

import sys
from pathlib import Path

# Make sure we can import svapna even if pip install -e wasn't done
project_root = Path(__file__).resolve().parent.parent
src = project_root / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from svapna.train.train import train

if __name__ == "__main__":
    from datetime import date
    training_data = project_root / "data" / "training" / f"{date.today()}.jsonl"
    if not training_data.exists():
        print(f"ERROR: training data not found at {training_data}")
        sys.exit(1)
    output = train(training_data)
    print(f"Training complete. Adapter at: {output}")
