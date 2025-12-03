#!/bin/bash
set -e

# If arguments are provided, pass them to python
if [ $# -gt 0 ]; then
    exec python main.py "$@"
else
    # If no arguments, start an interactive shell
    exec /bin/bash
fi
