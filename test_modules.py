#!/usr/bin/env python3
"""Test script to verify module details functionality."""

import asyncio
import re
import sys

def test_module_query_detection():
    """Test that module queries are properly detected."""
    # Pattern from server.py
    module_pattern = r"\b(module|modules|curriculum|syllabus|topics|lessons|content|subjects|topics covered)\b"
    
    test_cases = [
        ("What are the modules for AI for All?", True, "Specific course modules"),
        ("Show me the curriculum for WordPress", True, "WordPress curriculum"),
        ("What topics are covered in Web Development?", True, "Topics in course"),
        ("List the syllabus for Arduino course", True, "Arduino syllabus"),
        ("What subjects does LILIT teach?", True, "General subjects"),
        ("Tell me about the modules", True, "Generic modules request"),
        ("What are the courses?", False, "Course listing (not modules)"),
        ("How much does it cost?", False, "Pricing question"),
    ]
    
    print("=" * 70)
    print("TESTING MODULE QUERY DETECTION")
    print("=" * 70)
    
    passed = 0
    failed = 0
    
    for query, should_match, description in test_cases:
        q_lower = query.lower()
        matches = bool(re.search(module_pattern, q_lower))
        status = "✓ PASS" if matches == should_match else "✗ FAIL"
        
        if matches == should_match:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | {description}")
        print(f"       Query: '{query}'")
        print(f"       Expected: {should_match}, Got: {matches}")
        print()
    
    print(f"Results: {passed} passed, {failed} failed\n")
    return failed == 0


def test_course_mapping():
    """Test that module queries correctly map to courses."""
    courses_to_check = [
        ("AI for All", ["ai for all", "certificate ai for all", "e-certificate ai"]),
        ("Web Design WordPress", ["web design", "wordpress", "web design wordpress"]),
        ("Arduino Robotics", ["arduino", "robotics", "future robotics"]),
        ("Web Development", ["web development", "national certificate", "nvq", "web dev"]),
        ("AI Content Creation", ["content creation", "ai content", "e-certificate ai content"]),
    ]
    
    print("=" * 70)
    print("TESTING COURSE MAPPING FOR MODULES")
    print("=" * 70)
    
    test_queries = [
        ("What modules are in AI for All?", "AI for All"),
        ("Show curriculum for WordPress course", "Web Design WordPress"),
        ("Arduino robotics topics?", "Arduino Robotics"),
        ("Web Development syllabus", "Web Development"),
        ("AI Content Creation modules", "AI Content Creation"),
        ("Just modules without course", None),
    ]
    
    passed = 0
    failed = 0
    
    for query, expected_course in test_queries:
        q_lower = query.lower()
        course_found = None
        
        for course_name, keywords in courses_to_check:
            if any(keyword in q_lower for keyword in keywords):
                course_found = course_name
                break
        
        status = "✓ PASS" if course_found == expected_course else "✗ FAIL"
        
        if course_found == expected_course:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | Query: '{query}'")
        print(f"       Expected: {expected_course}, Got: {course_found}")
        print()
    
    print(f"Results: {passed} passed, {failed} failed\n")
    return failed == 0


def test_sinhala_module_detection():
    """Test Sinhala language module query detection."""
    print("=" * 70)
    print("TESTING SINHALA MODULE DETECTION")
    print("=" * 70)
    
    sinhala_pattern = r"[ක-ෆ]"
    
    test_cases = [
        ("AI for All ඉගෙනුම් කරුණු?", True, "Sinhala module query"),
        ("WordPress පාඨමාලාවේ විෂයන්?", True, "Sinhala curriculum"),
        ("What modules?", False, "English query"),
        ("දෙවැනි සිටුවම් විස්තරයන්", True, "Sinhala details request"),
    ]
    
    passed = 0
    failed = 0
    
    for query, should_have_sinhala, description in test_cases:
        has_sinhala = bool(re.search(sinhala_pattern, query))
        status = "✓ PASS" if has_sinhala == should_have_sinhala else "✗ FAIL"
        
        if has_sinhala == should_have_sinhala:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} | {description}")
        print(f"       Query: '{query}'")
        print(f"       Expected Sinhala: {should_have_sinhala}, Got: {has_sinhala}")
        print()
    
    print(f"Results: {passed} passed, {failed} failed\n")
    return failed == 0


def test_server_imports():
    """Test that server.py imports successfully with new functions."""
    print("=" * 70)
    print("TESTING SERVER IMPORTS WITH MODULE FUNCTIONALITY")
    print("=" * 70)
    
    try:
        import server
        
        # Check if the new function exists
        if hasattr(server, 'get_course_modules_from_pinecone'):
            print("✓ PASS | get_course_modules_from_pinecone function exists")
            return True
        else:
            print("✗ FAIL | get_course_modules_from_pinecone function not found")
            return False
            
    except Exception as e:
        print(f"✗ FAIL | Server import failed: {e}")
        return False


if __name__ == "__main__":
    results = []
    
    # Test 1: Module query detection
    results.append(("Module Query Detection", test_module_query_detection()))
    
    # Test 2: Course mapping
    results.append(("Course Mapping", test_course_mapping()))
    
    # Test 3: Sinhala detection
    results.append(("Sinhala Detection", test_sinhala_module_detection()))
    
    # Test 4: Server imports
    results.append(("Server Imports", test_server_imports()))
    
    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} | {test_name}")
    
    total_passed = sum(1 for _, p in results if p)
    total_tests = len(results)
    
    print(f"\nTotal: {total_passed}/{total_tests} tests passed")
    
    sys.exit(0 if total_passed == total_tests else 1)
