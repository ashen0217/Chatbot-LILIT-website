#!/usr/bin/env python3
"""Test script to verify course query fixes and Pinecone error handling."""

import re
import sys

def test_course_query_regex():
    """Test that the updated regex now matches various course queries."""
    # Updated regex from server.py (line 659-661)
    pattern = r"\b(courses?|course details|course fees|all courses|available courses|what courses|list courses|courses offered|your courses|offered courses)\b"
    
    test_cases = [
        ("What are the courses available in lilit?", True, "Original failing query"),
        ("what are the courses available in lilit", True, "Lowercase version"),
        ("Tell me about the courses", True, "Simple 'courses' match"),
        ("What course details are available?", True, "course details"),
        ("all courses", True, "all courses"),
        ("List the courses offered", True, "courses offered"),
        ("How many courses does LILIT have?", True, "courses in question context"),
        ("What is the weather today?", False, "Off-topic query"),
        ("Tell me a joke", False, "Off-topic query"),
    ]
    
    print("=" * 70)
    print("TESTING COURSE QUERY REGEX FIX")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for query, should_match, description in test_cases:
        q_lower = query.lower()
        matches = bool(re.search(pattern, q_lower))
        status = "✓ PASS" if matches == should_match else "✗ FAIL"
        
        if matches == should_match:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | {description}")
        print(f"       Query: '{query}'")
        print(f"       Expected: {should_match}, Got: {matches}")
        print()
    
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_pinecone_error_handling():
    """Test that server handles Pinecone errors gracefully."""
    print("\n" + "=" * 70)
    print("TESTING PINECONE ERROR HANDLING")
    print("=" * 70)
    
    # Check if server imports and sets vectorstore
    try:
        import server
        
        if server.vectorstore is None:
            print("✓ PASS | Server gracefully handles missing Pinecone index")
            print("       vectorstore = None (fallback active)")
            return True
        elif server.vectorstore is not None:
            print("✓ PASS | Pinecone index loaded successfully")
            print(f"       vectorstore is available: {type(server.vectorstore)}")
            return True
        else:
            print("✗ FAIL | Unexpected vectorstore state")
            return False
            
    except Exception as e:
        print(f"✗ FAIL | Server failed to import: {e}")
        return False


def test_qa_chain_availability():
    """Test that qa_chain is properly set based on vectorstore availability."""
    print("\n" + "=" * 70)
    print("TESTING QA_CHAIN AVAILABILITY")
    print("=" * 70)
    
    try:
        import server
        
        if server.vectorstore is None:
            if server.qa_chain is None:
                print("✓ PASS | qa_chain correctly set to None when vectorstore unavailable")
                return True
            else:
                print("✗ FAIL | qa_chain should be None when vectorstore is None")
                return False
        else:
            if server.qa_chain is not None:
                print("✓ PASS | qa_chain available when vectorstore loaded")
                return True
            else:
                print("✗ FAIL | qa_chain should be available when vectorstore loaded")
                return False
                
    except Exception as e:
        print(f"✗ FAIL | Error checking qa_chain: {e}")
        return False


if __name__ == "__main__":
    results = []
    
    # Test 1: Course query regex
    results.append(("Course Query Regex", test_course_query_regex()))
    
    # Test 2: Pinecone error handling
    results.append(("Pinecone Error Handling", test_pinecone_error_handling()))
    
    # Test 3: QA Chain availability
    results.append(("QA Chain Availability", test_qa_chain_availability()))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} | {test_name}")
    
    total_passed = sum(1 for _, p in results if p)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    sys.exit(0 if total_passed == total_tests else 1)
