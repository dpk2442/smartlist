cd "$(dirname "$0")/.."
pytest --verbose --cov-config tox.ini --cov-report html --cov-report term --cov smartlist --html test_report.html --self-contained-html tests
