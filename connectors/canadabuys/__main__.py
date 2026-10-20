import sys

from connectors import _base
from connectors.canadabuys import NAME, fetch

if __name__ == "__main__":
    sys.exit(_base.run_cli(NAME, fetch, None))
