#!/usr/bin/env bash
# One command to run the whole AEO stack. Passes all args through to the pipeline.
#   ./run.sh                       # MYNA baseline (myna.config.json)
#   ./run.sh --config client.json  # a client site
#   ./run.sh --no-citations        # skip live check
set -euo pipefail
cd "$(dirname "$0")"
python3 aeo_pipeline.py "$@"
