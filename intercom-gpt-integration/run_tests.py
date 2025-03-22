#!/usr/bin/env python3
"""
Run all tests and generate a coverage report.
"""

import unittest
import coverage
import os
import sys

def run_tests_with_coverage():
    """Run all tests with coverage reporting."""
    # Start coverage measurement
    cov = coverage.Coverage(
        source=['services', 'utils'],
        omit=['*/__pycache__/*', '*/tests/*']
    )
    cov.start()
    
    # Discover and run tests
    loader = unittest.TestLoader()
    start_dir = os.path.join(os.path.dirname(__file__), 'tests')
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Stop coverage measurement and generate report
    cov.stop()
    cov.save()
    
    # Print report to console
    print("\nCoverage Report:")
    cov.report()
    
    # Generate HTML report
    html_dir = os.path.join(os.path.dirname(__file__), 'htmlcov')
    cov.html_report(directory=html_dir)
    print(f"\nHTML report generated in {html_dir}")
    
    # Return test result for exit code
    return result

def main():
    """Run tests and return appropriate exit code."""
    result = run_tests_with_coverage()
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    sys.exit(main()) 
