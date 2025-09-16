#!/usr/bin/env python3
"""
RIGEL AI - NSBM GPA Calculation Demo
Copyright (C) 2025 Zerone Laboratories

This demo showcases the NSBM-specific GPA calculation features for AI chatbot integration.
"""

import sys
import os
import json
import time
from typing import Dict, List

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.mcp.cal_gpa import NSBMGPACalculator, Logic


def print_header(title: str):
    """Print a formatted header"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*20} {title} {'='*20}")


def simulate_typing(text: str, delay: float = 0.03):
    """Simulate typing effect for demo"""
    for char in text:
        print(char, end='', flush=True)
        time.sleep(delay)
    print()


def demo_nsbm_basic_calculation():
    """Demo basic NSBM GPA calculation"""
    print_section("NSBM Basic GPA Calculation")
    
    calculator = NSBMGPACalculator()
    
    print("👤 NSBM Student Query:")
    simulate_typing("\"I need to calculate my NSBM GPA for this semester.\"")
    
    print("\n🤖 RIGEL AI Response:")
    simulate_typing("I'll help you calculate your NSBM GPA. Please provide your course details.")
    
    print("\n📚 NSBM Course Data:")
    courses = [
        ("Programming Fundamentals", 4.0, "A"),
        ("Mathematics for Computing", 4.0, "B+"),
        ("Database Systems", 3.0, "A-"),
        ("Web Development", 3.0, 85),  # Percentage
        ("Software Engineering", 4.0, "B")
    ]
    
    for name, credits, grade in courses:
        print(f"   • {name}: {credits} credits, Grade: {grade}")
        calculator.add_course(name, credits, grade)
    
    result = calculator.calculate_gpa()
    
    print(f"\n🎯 NSBM GPA Result:")
    print(f"   📊 GPA: {result['gpa']}")
    print(f"   📚 Total Credits: {result['total_credits']}")
    print(f"   🎓 Academic Standing: {result['academic_standing']}")
    print(f"   🏫 Grading System: {result['grading_system']}")
    
    return result


def demo_nsbm_degree_classifications():
    """Demo NSBM degree classification system"""
    print_section("NSBM Degree Classification System")
    
    print("👤 NSBM Student Query:")
    simulate_typing("\"What are the degree classifications at NSBM and what GPA do I need?\"")
    
    print("\n🤖 RIGEL AI Response:")
    simulate_typing("Here are the NSBM degree classifications:")
    
    classifications = [
        ("First Class Honours", 3.7, 4.0),
        ("Second Class Honours - Upper Division", 3.3, 3.69),
        ("Second Class Honours - Lower Division", 3.0, 3.29),
        ("General Pass", 2.0, 2.99),
        ("Academic Probation", 1.0, 1.99),
        ("Academic Dismissal Risk", 0.0, 0.99)
    ]
    
    for classification, min_gpa, max_gpa in classifications:
        print(f"\n🎓 {classification}")
        print(f"   • GPA Range: {min_gpa} - {max_gpa}")
        
        # Demo with sample GPA
        test_gpa = (min_gpa + max_gpa) / 2
        calculator = NSBMGPACalculator()
        calculator.add_course("Sample Course", 3.0, test_gpa)
        result = calculator.calculate_gpa()
        
        print(f"   • Example GPA {test_gpa}: {result['academic_standing']}")


def demo_nsbm_grade_conversion():
    """Demo NSBM grade conversion features"""
    print_section("NSBM Grade Conversion")
    
    print("👤 NSBM Student Query:")
    simulate_typing("\"Can you explain the NSBM grading scale and convert these grades for me?\"")
    
    print("\n🤖 RIGEL AI Response:")
    simulate_typing("I'll explain the NSBM grading scale and convert your grades.")
    
    calculator = NSBMGPACalculator()
    
    test_grades = ["A+", "B", "C-", "F", 88, 65, 45]
    
    print("\n📋 NSBM Grade Conversions:")
    for grade in test_grades:
        grade_info = calculator.get_nsbm_grade_info(str(grade))
        if grade_info['status'] == 'success':
            print(f"\n   📌 Grade: {grade}")
            print(f"      • GPA Points: {grade_info['gpa_points']}")
            print(f"      • Classification: {grade_info['classification']}")
            print(f"      • Percentage Range: {grade_info['percentage_range']}")
        else:
            print(f"\n   ❌ Grade: {grade} - {grade_info['message']}")


def demo_nsbm_improvement_planning():
    """Demo NSBM-specific improvement planning"""
    print_section("NSBM Academic Improvement Planning")
    
    print("👤 NSBM Student Query:")
    simulate_typing("\"My current NSBM GPA is low. How can I improve to get First Class Honours?\"")
    
    print("\n🤖 RIGEL AI Response:")
    simulate_typing("Let me analyze your current situation and create an improvement plan.")
    
    # Current courses (low GPA scenario)
    current_calc = NSBMGPACalculator()
    current_courses = [
        ("Programming I", 4.0, "C+"),
        ("Mathematics I", 4.0, "C"),
        ("English", 2.0, "B-"),
        ("Physics", 3.0, "C+")
    ]
    
    print("\n📚 Current NSBM Courses:")
    for name, credits, grade in current_courses:
        print(f"   • {name}: {credits} credits, Grade: {grade}")
        current_calc.add_course(name, credits, grade)
    
    current_result = current_calc.calculate_gpa()
    print(f"\n📊 Current Status:")
    print(f"   • GPA: {current_result['gpa']}")
    print(f"   • Classification: {current_result['academic_standing']}")
    
    # Future scenario with improvements
    future_calc = NSBMGPACalculator()
    
    # Add current courses
    for name, credits, grade in current_courses:
        future_calc.add_course(name, credits, grade)
    
    # Add planned improvements
    planned_courses = [
        ("Programming II", 4.0, "A"),
        ("Mathematics II", 4.0, "A-"),
        ("Database Systems", 3.0, "A"),
        ("Software Engineering", 4.0, "B+")
    ]
    
    print(f"\n🎯 Planned NSBM Courses (with target grades):")
    for name, credits, grade in planned_courses:
        print(f"   • {name}: {credits} credits, Target: {grade}")
        future_calc.add_course(name, credits, grade)
    
    future_result = future_calc.calculate_gpa()
    improvement = future_result['gpa'] - current_result['gpa']
    
    print(f"\n📈 Projected Results:")
    print(f"   • Future GPA: {future_result['gpa']}")
    print(f"   • Future Classification: {future_result['academic_standing']}")
    print(f"   • Improvement: +{improvement:.3f} points")
    
    # Get NSBM-specific suggestions
    suggestions = current_calc.get_nsbm_improvement_suggestions()
    print(f"\n💡 NSBM-Specific Recommendations:")
    for i, suggestion in enumerate(suggestions[:4], 1):
        print(f"   {i}. {suggestion}")


def demo_nsbm_chatbot_scenarios():
    """Demo realistic NSBM chatbot interaction scenarios"""
    print_section("NSBM AI Chatbot Scenarios")
    
    scenarios = [
        {
            "query": "I'm an NSBM student. What GPA do I need for First Class Honours?",
            "response": "For First Class Honours at NSBM, you need a GPA of 3.7 or higher (out of 4.0). This is equivalent to maintaining mostly A and A- grades."
        },
        {
            "query": "Can you convert 82% to NSBM GPA points?",
            "response": "82% at NSBM equals a B+ grade, which is worth 3.3 GPA points."
        },
        {
            "query": "What's the difference between Second Class Upper and Lower at NSBM?",
            "response": "Second Class Honours - Upper Division requires GPA 3.3-3.69, while Lower Division requires GPA 3.0-3.29. The difference affects graduate school admissions and job prospects."
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n🔄 Scenario {i}:")
        print("👤 NSBM Student:")
        simulate_typing(f'   "{scenario["query"]}"')
        
        print("\n🤖 RIGEL AI:")
        simulate_typing(f'   {scenario["response"]}')
        
        time.sleep(1)


def demo_nsbm_api_integration():
    """Demo NSBM API integration examples"""
    print_section("NSBM API Integration")
    
    print("👤 External Application Query:")
    simulate_typing("\"Integrate NSBM GPA calculation into our student portal.\"")
    
    print("\n🤖 RIGEL AI Response:")
    simulate_typing("Here are the available NSBM-specific API endpoints:")
    
    api_examples = [
        {
            "endpoint": "POST /nsbm/gpa/calculate",
            "description": "Calculate NSBM GPA with detailed analysis",
            "example": {
                "course_names": ["Programming", "Mathematics", "Physics"],
                "credits": [4.0, 4.0, 3.0],
                "grades": ["A", "B+", "85"]
            }
        },
        {
            "endpoint": "POST /nsbm/gpa/simple",
            "description": "Simple NSBM GPA calculation",
            "example": {
                "credits": [3.0, 4.0, 2.0],
                "grade_points": [4.0, 3.3, 3.7]
            }
        },
        {
            "endpoint": "POST /nsbm/gpa/grade-info",
            "description": "Get NSBM grade information",
            "example": {
                "grade": "B+"
            }
        }
    ]
    
    for api in api_examples:
        print(f"\n📡 {api['endpoint']}")
        print(f"   Purpose: {api['description']}")
        print(f"   Example Request:")
        print(f"   {json.dumps(api['example'], indent=6)}")


def demo_nsbm_legacy_compatibility():
    """Demo backward compatibility with legacy NSBM code"""
    print_section("NSBM Legacy Compatibility")
    
    print("🔄 Testing backward compatibility with existing NSBM Logic class...")
    
    # Test data
    credits = [4.0, 3.0, 4.0, 2.0]
    grade_points = [4.0, 3.3, 3.7, 2.0]
    
    # Legacy implementation
    legacy = Logic(credits, grade_points)
    legacy_gpa = legacy.getGPA()
    
    # New NSBM implementation
    new_calc = NSBMGPACalculator()
    for i, (credit, gp) in enumerate(zip(credits, grade_points)):
        new_calc.add_course(f"Course_{i+1}", credit, gp)
    
    new_result = new_calc.calculate_gpa()
    
    print(f"\n📊 Compatibility Test Results:")
    print(f"   • Legacy GPA: {legacy_gpa}")
    print(f"   • New NSBM GPA: {new_result['gpa']}")
    print(f"   • Difference: {abs(new_result['gpa'] - legacy_gpa):.6f}")
    print(f"   • Status: {'✅ Compatible' if abs(new_result['gpa'] - legacy_gpa) < 0.01 else '❌ Incompatible'}")


def main():
    """Main demo function"""
    print_header("RIGEL AI - NSBM GPA CALCULATION SYSTEM DEMO")
    
    print("🎓 Welcome to the NSBM GPA Calculation System Demo")
    print("   This demonstration showcases AI chatbot integration for NSBM students")
    print("   Developed by Zerone Laboratories © 2025")
    
    # Run all demos
    demo_nsbm_basic_calculation()
    demo_nsbm_degree_classifications()
    demo_nsbm_grade_conversion()
    demo_nsbm_improvement_planning()
    demo_nsbm_chatbot_scenarios()
    demo_nsbm_api_integration()
    demo_nsbm_legacy_compatibility()
    
    print_header("NSBM GPA SYSTEM DEMO COMPLETE")
    print("🎉 The NSBM GPA calculation system is ready for production use!")
    print("\n✨ Key Features Demonstrated:")
    print("   ✅ NSBM-specific grading scale (A+ to F)")
    print("   ✅ Degree classification system (First Class Honours, etc.)")
    print("   ✅ Grade conversion (letters, percentages, GPA points)")
    print("   ✅ Academic improvement planning")
    print("   ✅ AI chatbot integration scenarios")
    print("   ✅ REST API endpoints")
    print("   ✅ Legacy code compatibility")
    
    print("\n🎯 Ready for NSBM Student Queries:")
    print("   • 'Calculate my NSBM GPA'")
    print("   • 'What classification will I get?'")
    print("   • 'How do I achieve First Class Honours?'")
    print("   • 'Convert my grades to NSBM scale'")


if __name__ == "__main__":
    main()
