#!/usr/bin/env python3
"""Auto-fix code formatting issues for CI/CD compliance."""

import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report status."""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"{'='*60}")
    print(f"Running: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.stdout:
            print(result.stdout)
        
        if result.returncode == 0:
            print(f"✅ {description} - COMPLETED")
            return True
        else:
            print(f"⚠️  {description} - HAD WARNINGS")
            if result.stderr:
                print(f"Stderr: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print(f"❌ Command not found. Install with: pip install {cmd[0]}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main execution."""
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      FLOWCHART GENERATOR - AUTO-FIX FORMATTING        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    
    # Directories to format
    dirs = ['src', 'cli', 'tests']
    existing_dirs = [d for d in dirs if Path(d).exists()]
    
    if not existing_dirs:
        print("❌ No source directories found (src, cli, tests)")
        return 1
    
    print(f"\nFormatting directories: {', '.join(existing_dirs)}")
    
    results = []
    
    # 1. Auto-fix with black
    results.append(run_command(
        ['black'] + existing_dirs,
        "Format code with Black"
    ))
    
    # 2. Auto-fix with isort
    results.append(run_command(
        ['isort'] + existing_dirs,
        "Sort imports with isort"
    ))
    
    # 3. Check with flake8 (non-fixing)
    print(f"\n{'='*60}")
    print("🔍 Checking code quality with flake8")
    print(f"{'='*60}")
    
    flake8_result = subprocess.run(
        ['flake8'] + existing_dirs + [
            '--max-line-length=120',
            '--extend-ignore=E203,W503',
            '--statistics',
            '--count'
        ],
        capture_output=True,
        text=True
    )
    
    if flake8_result.stdout:
        print(flake8_result.stdout)
    
    if flake8_result.returncode == 0:
        print("✅ No flake8 issues found")
        results.append(True)
    else:
        print("⚠️  Some flake8 warnings (review manually)")
        results.append(False)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print(f"{'='*60}")
    
    tasks = [
        "Black formatting",
        "Import sorting",
        "Flake8 checks"
    ]
    
    for task, result in zip(tasks, results):
        status = "✅" if result else "⚠️ "
        print(f"{status} {task}")
    
    success_count = sum(results)
    total = len(results)
    
    print(f"\nCompleted: {success_count}/{total} tasks")
    
    if success_count == total:
        print("\n✅ All formatting fixes applied successfully!")
        print("\nNext steps:")
        print("1. Review changes: git diff")
        print("2. Test locally: python -m cli.main --version")
        print("3. Commit: git commit -am 'Apply code formatting fixes'")
        return 0
    else:
        print("\n⚠️  Some issues remain. Review output above.")
        print("\nTo install missing tools:")
        print("pip install black isort flake8")
        return 1


if __name__ == "__main__":
    sys.exit(main())
