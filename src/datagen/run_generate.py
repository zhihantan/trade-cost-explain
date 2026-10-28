"""Serverless job entry point: generate the Meridian dataset straight into the landing Volume and verify the tie-out.

    spark_python_task: python_file=src/datagen/run_generate.py, parameters=["--out", "/Volumes/<catalog>/landing/raw"]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from meridian_datagen.main import main  # noqa: E402

if __name__ == "__main__":
    main()
