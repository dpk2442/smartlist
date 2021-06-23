#!/bin/sh

cd "$(dirname "$0")/.."
flake8 smartlist
exit $?
