#!/bin/bash

cd "$(dirname "$0")"
./start.sh
status=$?
echo
read -r -p "Press Return to close this window..."
exit "$status"
