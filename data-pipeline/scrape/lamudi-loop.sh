#!/bin/bash
# usage: lamudi-loop.sh URL TAG
for i in $(seq 1 30); do
  xvfb-run -a node lamudi.mjs "$1" "$2" 80
  code=$?
  echo "exit $code (round $i)"
  [ $code -ne 3 ] && break
  sleep 150
done
