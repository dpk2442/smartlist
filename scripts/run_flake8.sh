#!/bin/sh

cd "$(dirname "$0")/.."
flake8 smartlist
flake8 tests
exit $?
