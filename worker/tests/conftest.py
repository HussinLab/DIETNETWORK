import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo's worker/ dir -> `import worker.*`

# Set by tests/run_unit_tests.sh, which mounts dataTest/fixtures read-only
# into the container this runs in. Unset (host runs without Docker) means
# the plink-dependent tests are skipped -- see test_pipeline.py.
FIXTURES_DIR = os.environ.get("FIXTURES_DIR")
