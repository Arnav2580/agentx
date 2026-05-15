#!/bin/bash
set -e

echo "Demo scenarios available:"
ls tests/demo_scenarios
echo ""
echo "Try:"
echo "  python -m server.main"
echo "  juror verify tests/demo_scenarios/software_dev.py"
