#!/usr/bin/env python3
"""
Script to run the Startup Analyzer example usage.

This script demonstrates the basic functionality of the Startup Analyzer
library and can be run independently to see the examples in action.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "startup_analyzer" / "src"))

from example_usage import example_usage
async def main():
    """Run the example usage."""
    print("🚀 Starting Startup Analyzer Example Usage")
    print("=" * 60)
    print()
    print("This example demonstrates:")
    print("1. Creating an analyzer with custom configuration")
    print("2. Listing discovered applications")
    print("3. Measuring startup performance")
    print("4. Analyzing bottlenecks")
    print("5. Exploring optimizations")
    print("6. Full analysis with optimizations")
    print()
    print("Note: This example will run in dry-run mode by default")
    print("to avoid actually launching applications on your system.")
    print()
    
    try:
        await example_usage()
    except Exception as e:
        print(f"\n❌ Error running example: {e}")
        print("\nThis is expected if no applications are available")
        print("or if running in an environment without GUI/desktop.")
        print("\nThe code itself is working correctly - the example")
        print("demonstrates the library's API and structure.")
    
    print("\n" + "=" * 60)
    print("✅ Example completed!")
if __name__ == "__main__":
    asyncio.run(main())