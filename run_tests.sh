#!/bin/bash
TESTS="tests"

# cd "$PY2MANY_HOME"

# Run Translation tests
sudo ./setup.py install

## Base tests
# py2many --julia=1 "$TESTS/cases" --outdir=../pyjl_tests/cases-py2many
# python py2many.py --julia=1 tests/cases --outdir=../pyjl_tests/cases-py2many # Temporary for windows
# Example with config
# py2many --julia=1 --config=pyjl/test_files/setup.ini "$TESTS/cases/sealed.py" --outdir=../pyjl_tests/cases-py2many

## Python tests
# py2many --julia=1 "$TESTS/cases_py" --outdir=../pyjl_tests/cases_py-py2many
# py2many --julia=1 "$TESTS/cases_py/test_dict.py" --outdir=../pyjl_tests/cases_py-py2many # Specific file
# python py2many.py --julia=1 "$TESTS/cases_py" --outdir=../pyjl_tests/cases_py-py2many # Temporary for windows

## Performance tests
# py2many --julia=1 "$TESTS/performance_tests" --outdir=../pyjl_tests/performance_tests-py2many
# py2many --julia=1 "$TESTS/performance_tests/sieve/sieve.py" --outdir=../pyjl_tests/performance_tests-py2many/sieve
# python py2many.py --julia=1 tests/performance_tests --outdir=../pyjl_tests/performance_tests-py2many # Temporary for windows

## Pywin tests
# py2many --julia=1 "../pyjl_tests/pywin" --outdir=../pyjl_tests/pywin-py2many
# python py2many.py --julia=1 "../pyjl_tests/pywin" --outdir=../pyjl_tests/pywin-py2many # Temporary for windows
# python py2many.py --julia=1 "../pyjl_tests/pywin/win32com_/ext_modules/pywintypes.py" --outdir=../pyjl_tests/pywin-py2many/win32com_/ext_modules
# py2many --julia=1 "../pyjl_tests/pywin/win32com_" --outdir=../pyjl_tests/pywin-py2many/win32com_
# py2many --julia=1 "../pyjl_tests/pywin/win32com_/client/combrowse.py" --outdir=../pyjl_tests/pywin-py2many/win32com_/client

# Retinaface
# py2many --julia=1 "../pyjl_tests/retinaface" --outdir=../pyjl_tests/retinaface-py2many

# Neural network
python py2many.py --julia=1 "../pyjl_tests/network/" --outdir=../pyjl_tests/network-py2many # Windows

# Run Transpiler Tests
# TODO