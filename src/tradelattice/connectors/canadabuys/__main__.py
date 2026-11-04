import sys

from tradelattice.connectors import _base
from tradelattice.connectors.canadabuys import NAME, fetch

if __name__ == "__main__":
    sys.exit(_base.run_cli(NAME, fetch, None))
