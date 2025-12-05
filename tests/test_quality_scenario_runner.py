# tests/test_quality_scenario_runner.py
"""
Quality Scenario Test Runner

This script runs all quality scenario tests and provides detailed reporting
on whether each response measure is fulfilled or not.

TODO: This test module requires database connectivity. When running in CI 
environments without PostgreSQL, tests may be skipped gracefully.
"""

import pytest
import time
import sys
import os
import json
from datetime import datetime, timezone
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from src.tactics.manager import QualityTacticsManager
    from src.database import SessionLocal
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    import_error = str(e)
    QualityTacticsManager = None
    SessionLocal = None


class QualityScenarioReporter:
    """Reporter for quality scenario test results."""
    
    def __init__(self):
        self.results = {}
        self.start_time = None
        self.end_time = None
    
    def start_testing(self):
        """Start the testing session."""
        self.start_time = datetime.now(timezone.utc)
        print("\n" + "="*80)
        print("🎯 QUALITY SCENARIO VALIDATION TEST SUITE")
        print("="*80)
        print(f"Started at: {self.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("="*80)
    
    def end_testing(self):
        """End the testing session and generate summary."""
        self.end_time = datetime.now(timezone.utc)
        duration = (self.end_time - self.start_time).total_seconds()
        
        print("\n" + "="*80)
        print("📊 QUALITY SCENARIO VALIDATION SUMMARY")
        print("="*80)
        print(f"Completed at: {self.end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"Total Duration: {duration:.2f} seconds")
        print("="*80)
        
        # Generate detailed summary
        self._generate_summary()
    
    def _generate_summary(self):
        """Generate detailed summary of all test results."""
        if not self.results:
            print("⚠️  No test results recorded.")
            return
        
        # Group results by quality attribute
        quality_attributes = {
            'Availability': [],
            'Security': [],
            'Modifiability': [],
            'Performance': [],
            'Integrability': [],
            'Testability': [],
            'Usability': []
        }
        
        for scenario_id, result in self.results.items():
            if scenario_id.startswith('A.'):
                quality_attributes['Availability'].append((scenario_id, result))
            elif scenario_id.startswith('S.'):
                quality_attributes['Security'].append((scenario_id, result))
            elif scenario_id.startswith('M.'):
                quality_attributes['Modifiability'].append((scenario_id, result))
            elif scenario_id.startswith('P.'):
                quality_attributes['Performance'].append((scenario_id, result))
            elif scenario_id.startswith('I.'):
                quality_attributes['Integrability'].append((scenario_id, result))
            elif scenario_id.startswith('T.'):
                quality_attributes['Testability'].append((scenario_id, result))
            elif scenario_id.startswith('U.'):
                quality_attributes['Usability'].append((scenario_id, result))
        
        # Print summary for each quality attribute
        total_scenarios = 0
        fulfilled_scenarios = 0
        
        for qa_name, scenarios in quality_attributes.items():
            if not scenarios:
                continue
                
            print(f"\n📋 {qa_name.upper()} QUALITY ATTRIBUTE")
            print("-" * 50)
            
            qa_fulfilled = 0
            for scenario_id, result in scenarios:
                total_scenarios += 1
                if result['fulfilled']:
                    fulfilled_scenarios += 1
                    qa_fulfilled += 1
                    status = "✅ FULFILLED"
                else:
                    status = "❌ NOT FULFILLED"
                
                print(f"  {scenario_id}: {status}")
                print(f"    Response Measure: {result['response_measure']}")
                print(f"    Target: {result['target_value']}")
                print(f"    Actual: {result['actual_value']}")
                print()
            
            qa_success_rate = (qa_fulfilled / len(scenarios)) * 100 if scenarios else 0
            print(f"  {qa_name} Success Rate: {qa_success_rate:.1f}% ({qa_fulfilled}/{len(scenarios)})")
        
        # Overall summary
        overall_success_rate = (fulfilled_scenarios / total_scenarios) * 100 if total_scenarios > 0 else 0
        
        print(f"\n🎯 OVERALL RESULTS")
        print("-" * 30)
        print(f"Total Scenarios Tested: {total_scenarios}")
        print(f"Fulfilled Scenarios: {fulfilled_scenarios}")
        print(f"Overall Success Rate: {overall_success_rate:.1f}%")
        
        if overall_success_rate == 100.0:
            print(f"\n🎉 ALL QUALITY SCENARIOS SUCCESSFULLY VALIDATED!")
            print("   The retail management system meets all documented quality requirements.")
        elif overall_success_rate >= 90.0:
            print(f"\n✅ EXCELLENT QUALITY VALIDATION!")
            print(f"   {overall_success_rate:.1f}% of scenarios fulfilled - system meets most quality requirements.")
        elif overall_success_rate >= 80.0:
            print(f"\n⚠️  GOOD QUALITY VALIDATION")
            print(f"   {overall_success_rate:.1f}% of scenarios fulfilled - some improvements needed.")
        else:
            print(f"\n❌ QUALITY VALIDATION NEEDS IMPROVEMENT")
            print(f"   {overall_success_rate:.1f}% of scenarios fulfilled - significant improvements required.")
        
        print("="*80)
    
    def record_result(self, scenario_id, response_measure, actual_value, target_value, fulfilled):
        """Record a test result."""
        self.results[scenario_id] = {
            'response_measure': response_measure,
            'actual_value': actual_value,
            'target_value': target_value,
            'fulfilled': fulfilled,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }


def run_quality_scenario_tests():
    """Run all quality scenario tests with detailed reporting."""
    reporter = QualityScenarioReporter()
    reporter.start_testing()
    
    try:
        # Run pytest with the quality scenario tests
        pytest_args = [
            "tests/test_quality_scenarios.py",
            "-v",
            "--tb=short",
            "--capture=no"  # Show print statements
        ]
        
        exit_code = pytest.main(pytest_args)
        
        if exit_code == 0:
            print("\n✅ All quality scenario tests passed!")
        else:
            print(f"\n❌ Some quality scenario tests failed (exit code: {exit_code})")
        
    except Exception as e:
        print(f"\n💥 Error running quality scenario tests: {e}")
        exit_code = 1
    
    finally:
        reporter.end_testing()
    
    return exit_code


if __name__ == "__main__":
    exit_code = run_quality_scenario_tests()
    sys.exit(exit_code)
