#!/bin/sh
export PYTHONPATH="/usr/lib/bestthemes${PYTHONPATH:+:$PYTHONPATH}"
exec /usr/bin/python3 -m bestthemes "$@"
