#!/usr/bin/env python3
"""Comprehensive test runner - runs all tests and validations."""

import sys
import subprocess
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print("\n" + "="*60)
    print(f"🔍 {description}")
    print("="*60)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=False,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print(f"\n✅ {description} - PASSED")
            return True
        else:
            print(f"\n❌ {description} - FAILED (exit code {result.returncode})")
            return False
    except Exception as e:
        print(f"\n❌ {description} - ERROR: {e}")
        return False


def main():
    """Run all validation and test suites."""
    print("""\n
╔══════════════════════════════════════════════════════════╗
║   FLOWCHART GENERATOR - COMPREHENSIVE TEST SUITE         ║
╚══════════════════════════════════════════════════════════╝

    """)
    
    results = {}
    
    # 1. Code validation
    results['code_validation'] = run_command(
        [sys.executable, "validate_code.py"],
        "Code Syntax & Structure Validation"
    )
    
    # 2. Unit tests
    results['unit_tests'] = run_command(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short", "-k", "not test_e2e"],
        "Unit Tests"
    )
    
    # 3. E2E tests
    results['e2e_tests'] = run_command(
        [sys.executable, "-m", "pytest", "tests/test_e2e.py", "-v", "--tb=short"],
        "End-to-End Integration Tests"
    )
    
    # 4. Quick validation with test_runner
    results['quick_validation'] = run_command(
        [sys.executable, "test_runner.py"],
        "Quick Validation Tests"
    )
    
    # 5. Example validation
    print("\n" + "="*60)
    print("🔍 Example Files Validation")
    print("="*60)
    
    examples_dir = Path("examples")
    if examples_dir.exists():
        example_files = list(examples_dir.glob("*.txt"))
        examples_passed = 0
        
        for example in example_files:
            result = run_command(
                [sys.executable, "-m", "cli.main", "validate", str(example)],
                f"Validate {example.name}"
            )
            if result:
                examples_passed += 1
        
        results['examples'] = examples_passed == len(example_files)
        print(f"\n✅ Examples validation: {examples_passed}/{len(example_files)} passed")
    else:
        print("⚠️  Examples directory not found")
        results['examples'] = False
    
    # Summary
    print("\n" + "="*60)
    print("📊 OVERALL SUMMARY")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTest Suites:")
    for name, passed_test in results.items():
        status = "✅ PASSED" if passed_test else "❌ FAILED"
        print(f"  • {name.replace('_', ' ').title()}: {status}")
    
    print(f"\nTotal: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n" + "="*60)
        print("🎉 ALL TESTS PASSED! 🎉")
        print("="*60)
        print("\nYour flowchart generator is fully functional!")
        print("\nTry it out:")
        print("  python -m cli.main generate examples/simple_workflow.txt -o test.png")
        print("\nNext steps:")
        print("  • Start building new features")
        print("  • Add more test cases")
        print("  • Contribute to the project")
        return 0
    else:
        print("\n" + "="*60)
        print("⚠️  SOME TESTS FAILED")
        print("="*60)
        print("\nPlease review the failures above and fix them.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
