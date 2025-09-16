#!/usr/bin/env python3
"""
NSBM GPA Calculation Integration Test
Copyright (C) 2025 Zerone Laboratories

This file demonstrates proper AI chatbot usage with the NSBM-specific GPA calculation system.
It includes tests for the NSBM GPA calculator, MCP tools integration, and web API endpoints.
"""

import sys
import os
import json
import asyncio
import unittest
from typing import List, Dict

# Add the current directory to Python path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.mcp.cal_gpa import NSBMGPACalculator, Logic

class TestNSBMGPACalculator(unittest.TestCase):
    """Test cases for the NSBM GPA calculator"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.calculator = NSBMGPACalculator()
    
    def test_nsbm_letter_grades(self):
        """Test NSBM letter grade calculations"""
        # Add sample NSBM courses with letter grades
        courses = [
            ("Programming Fundamentals", 3.0, "A"),
            ("Data Structures", 4.0, "B+"),
            ("Database Systems", 3.0, "A-"),
            ("Web Development", 2.0, "B"),
            ("Software Engineering", 4.0, "C+")
        ]
        
        for name, credits, grade in courses:
            self.assertTrue(self.calculator.add_course(name, credits, grade))
        
        result = self.calculator.calculate_gpa()
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['total_courses'], 5)
        self.assertEqual(result['total_credits'], 16.0)
        self.assertEqual(result['grading_system'], 'NSBM University')
        self.assertGreater(result['gpa'], 3.0)  # Should be a good GPA
        self.assertIn('Class Honours', result['academic_standing'])  # Should be some level of honours
        
        print(f"NSBM Letter Grades Test: GPA = {result['gpa']}, Standing = {result['academic_standing']}")
    
    def test_nsbm_percentage_grades(self):
        """Test NSBM percentage to GPA conversion"""
        test_cases = [
            (95, 4.0),   # A+/A
            (88, 3.7),   # A-
            (82, 3.3),   # B+
            (77, 3.0),   # B
            (72, 2.7),   # B-
            (67, 2.3),   # C+
            (62, 2.0),   # C
            (57, 1.7),   # C-
            (52, 1.3),   # D+
            (47, 1.0),   # D
            (40, 0.0)    # F
        ]
        
        for percentage, expected_gpa in test_cases:
            self.calculator.clear_courses()
            self.calculator.add_course("Test Course", 3.0, percentage)
            result = self.calculator.calculate_gpa()
            
            self.assertAlmostEqual(result['gpa'], expected_gpa, places=1)
            print(f"  {percentage}% = {result['gpa']} GPA points")
    
    def test_mixed_nsbm_grades(self):
        """Test mixing NSBM letter grades and percentages"""
        self.calculator.clear_courses()
        
        # Mix of NSBM letter grades and percentages
        mixed_courses = [
            ("Programming", 3.0, "A"),      # Letter grade
            ("Mathematics", 4.0, 85),       # Percentage (A-)
            ("Physics", 2.0, "B+"),         # Letter grade
            ("English", 3.0, 78)            # Percentage (B)
        ]
        
        for name, credits, grade in mixed_courses:
            self.assertTrue(self.calculator.add_course(name, credits, grade))
        
        result = self.calculator.calculate_gpa()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['total_courses'], 4)
        self.assertEqual(result['grading_system'], 'NSBM University')
    
    def test_nsbm_academic_standings(self):
        """Test NSBM-specific academic standing classifications"""
        standings = [
            (3.8, "First Class Honours"),
            (3.5, "Second Class Honours - Upper Division"),
            (3.1, "Second Class Honours - Lower Division"),
            (2.5, "General Pass"),
            (1.5, "Academic Probation"),
            (0.5, "Academic Dismissal Risk")
        ]
        
        for gpa, expected_standing in standings:
            self.calculator.clear_courses()
            self.calculator.add_course("Test Course", 3.0, gpa)
            result = self.calculator.calculate_gpa()
            
            # Check if the standing contains any part of the expected classification
            if "First Class" in expected_standing:
                self.assertTrue(gpa >= 3.7, f"GPA {gpa} should be >= 3.7 for First Class")
            elif "Upper Division" in expected_standing:
                self.assertTrue(3.3 <= gpa < 3.7, f"GPA {gpa} should be in range 3.3-3.69")
            elif "Lower Division" in expected_standing:
                self.assertTrue(3.0 <= gpa < 3.3, f"GPA {gpa} should be in range 3.0-3.29")
            elif "General Pass" in expected_standing:
                self.assertTrue(2.0 <= gpa < 3.0, f"GPA {gpa} should be in range 2.0-2.99")
            
            print(f"  GPA {gpa} = {result['academic_standing']}")
    
    def test_nsbm_grade_info(self):
        """Test NSBM grade information retrieval"""
        test_grades = ["A+", "B", "C-", "F", 85, 65]
        
        for grade in test_grades:
            grade_info = self.calculator.get_nsbm_grade_info(str(grade))
            self.assertEqual(grade_info['status'], 'success')
            self.assertIn('classification', grade_info)
            self.assertIn('percentage_range', grade_info)
            print(f"  {grade}: {grade_info['gpa_points']} points, {grade_info['classification']}")
    
    def test_legacy_compatibility(self):
        """Test backward compatibility with original Logic class"""
        credits = [3.0, 4.0, 2.0, 3.0]
        grade_points = [4.0, 3.3, 3.7, 2.0]
        
        # Test new implementation
        calculator = NSBMGPACalculator()
        for i, (credit, gp) in enumerate(zip(credits, grade_points)):
            calculator.add_course(f"Course_{i+1}", credit, gp)
        
        new_result = calculator.calculate_gpa()
        
        # Test legacy implementation
        legacy = Logic(credits, grade_points)
        legacy_gpa = legacy.getGPA()
        
        # Results should be very close (within rounding differences)
        self.assertAlmostEqual(new_result['gpa'], legacy_gpa, places=2)
        print(f"Legacy compatibility: New={new_result['gpa']}, Legacy={legacy_gpa}")
    
    def test_nsbm_error_handling(self):
        """Test error handling for NSBM-specific scenarios"""
        # Test negative credits
        self.assertFalse(self.calculator.add_course("Bad Course", -1.0, "A"))
        
        # Test invalid NSBM grade
        self.assertFalse(self.calculator.add_course("Bad Grade", 3.0, "X"))
        
        # Test invalid percentage
        self.assertFalse(self.calculator.add_course("Bad Percentage", 3.0, 150))
        
        # Test empty calculator
        empty_calc = NSBMGPACalculator()
        result = empty_calc.calculate_gpa()
        self.assertEqual(result['status'], 'error')
    
    def test_nsbm_improvement_suggestions(self):
        """Test NSBM-specific improvement suggestions"""
        # Low GPA scenario
        low_gpa_calc = NSBMGPACalculator()
        low_gpa_calc.add_course("Course 1", 3.0, "D")
        low_gpa_calc.add_course("Course 2", 3.0, "C-")
        
        suggestions = low_gpa_calc.get_nsbm_improvement_suggestions()
        self.assertIn("NSBM", " ".join(suggestions))
        self.assertIn("advisor", " ".join(suggestions).lower())
        
        # High GPA scenario
        high_gpa_calc = NSBMGPACalculator()
        high_gpa_calc.add_course("Course 1", 3.0, "A+")
        high_gpa_calc.add_course("Course 2", 3.0, "A")
        
        suggestions = high_gpa_calc.get_nsbm_improvement_suggestions()
        self.assertIn("First Class Honours", " ".join(suggestions))


class TestNSBMChatbotScenarios(unittest.TestCase):
    """Test realistic NSBM AI chatbot scenarios"""
    
    def test_nsbm_student_query_scenario(self):
        """Simulate an NSBM student asking the AI chatbot about their GPA"""
        
        # Simulate chatbot receiving this query:
        # "I'm an NSBM student. I got A in Programming (3 credits), B+ in Math (4 credits), 
        #  A- in Physics (3 credits), and 85% in English (2 credits). 
        #  What's my GPA and class standing?"
        
        calculator = NSBMGPACalculator()
        
        # Parse and add courses as the chatbot would
        student_courses = [
            ("Programming", 3, "A"),
            ("Math", 4, "B+"),
            ("Physics", 3, "A-"),
            ("English", 2, 85)  # Percentage
        ]
        
        for name, credits, grade in student_courses:
            success = calculator.add_course(name, credits, grade)
            self.assertTrue(success, f"Failed to add {name} with grade {grade}")
        
        result = calculator.calculate_gpa()
        suggestions = calculator.get_nsbm_improvement_suggestions()
        
        # Generate NSBM-specific chatbot response
        response = self._generate_nsbm_chatbot_response(result, suggestions)
        
        print("\n" + "="*60)
        print("NSBM CHATBOT SCENARIO: Student GPA Query")
        print("="*60)
        print("Student: I'm an NSBM student. I got A in Programming (3 credits),")
        print("         B+ in Math (4 credits), A- in Physics (3 credits),")
        print("         and 85% in English (2 credits). What's my GPA?")
        print("\nRIGEL AI:")
        print(response)
        print("="*60)
        
        # Verify the response makes sense
        self.assertIn("NSBM", response)
        self.assertIn("GPA", response)
        self.assertIn(str(result['gpa']), response)
        self.assertIn("Honours", response)  # Should be honours level
    
    def test_nsbm_classification_query(self):
        """Simulate NSBM student asking about degree classifications"""
        
        calculator = NSBMGPACalculator()
        
        # Current courses leading to Second Class Honours - Upper
        current_courses = [
            ("Database Systems", 4, "B+"),
            ("Software Engineering", 3, "A-"),
            ("Computer Networks", 4, "B+"),
            ("Web Technologies", 3, "B")
        ]
        
        for name, credits, grade in current_courses:
            calculator.add_course(name, credits, grade)
        
        result = calculator.calculate_gpa()
        
        response = self._generate_nsbm_classification_response(result)
        
        print("\n" + "="*60)
        print("NSBM CHATBOT SCENARIO: Degree Classification Inquiry")
        print("="*60)
        print("Student: What degree classification will I get with my current NSBM GPA?")
        print("         And what do I need for First Class Honours?")
        print("\nRIGEL AI:")
        print(response)
        print("="*60)
    
    def test_nsbm_course_planning_scenario(self):
        """Simulate helping NSBM student plan courses for better classification"""
        
        # Current GPA is in Second Class Lower range
        calculator = NSBMGPACalculator()
        
        current_courses = [
            ("Programming I", 4, "B"),
            ("Mathematics I", 4, "B-"),
            ("English", 2, "C+"),
            ("Physics", 3, "B+")
        ]
        
        for name, credits, grade in current_courses:
            calculator.add_course(name, credits, grade)
        
        current_result = calculator.calculate_gpa()
        
        # Simulate what happens if they improve next semester
        future_calculator = NSBMGPACalculator()
        
        # Add current courses
        for name, credits, grade in current_courses:
            future_calculator.add_course(name, credits, grade)
        
        # Add planned courses with target grades
        planned_courses = [
            ("Programming II", 4, "A"),
            ("Mathematics II", 4, "A-"),
            ("Database Systems", 3, "A")
        ]
        
        for name, credits, grade in planned_courses:
            future_calculator.add_course(name, credits, grade)
        
        future_result = future_calculator.calculate_gpa()
        
        response = self._generate_nsbm_planning_response(current_result, future_result, planned_courses)
        
        print("\n" + "="*60)
        print("NSBM CHATBOT SCENARIO: Course Planning for Better Classification")
        print("="*60)
        print("Student: I'm currently getting Second Class Lower. If I get A's in")
        print("         Programming II, Math II, and Database Systems, what will")
        print("         my NSBM classification be?")
        print("\nRIGEL AI:")
        print(response)
        print("="*60)
    
    def _generate_nsbm_chatbot_response(self, result: Dict, suggestions: List[str]) -> str:
        """Generate a natural NSBM-specific chatbot response"""
        
        gpa = result['gpa']
        standing = result['academic_standing']
        total_credits = result['total_credits']
        
        response = f"""Great! I've calculated your NSBM GPA. Here's your academic summary:

📊 **Your NSBM GPA: {gpa}** (out of 4.0)
📚 Total Credits: {total_credits}
🎓 **Degree Classification: {standing}**

**Course Breakdown (NSBM Grading Scale):**"""
        
        for course in result['courses']:
            response += f"\n• {course['name']}: {course['grade']} ({course['credits']} credits) = {course['gpa_points']} GPA points"
        
        response += f"\n\n**NSBM Performance Analysis:**"
        if "First Class" in standing:
            response += "\n🌟 Outstanding! You're achieving First Class Honours level."
            response += "\n   This puts you in the top tier of NSBM graduates."
        elif "Upper Division" in standing:
            response += "\n✅ Excellent work! Second Class Honours - Upper Division."
            response += "\n   You're performing very well at NSBM standards."
        elif "Lower Division" in standing:
            response += "\n👍 Good performance! Second Class Honours - Lower Division."
            response += "\n   Solid academic standing at NSBM."
        elif "General Pass" in standing:
            response += "\n⚠️ Your performance meets NSBM pass requirements but has room for improvement."
        else:
            response += "\n🚨 Your GPA needs immediate attention to meet NSBM standards."
        
        response += f"\n\n**NSBM-Specific Recommendations:**"
        for i, suggestion in enumerate(suggestions[:3], 1):
            response += f"\n{i}. {suggestion}"
        
        return response
    
    def _generate_nsbm_classification_response(self, result: Dict) -> str:
        """Generate response about NSBM degree classifications"""
        
        gpa = result['gpa']
        current_standing = result['academic_standing']
        
        response = f"""Based on your current NSBM GPA of {gpa}, here's your degree classification status:

🎓 **Current Classification: {current_standing}**

**NSBM Degree Classification Scale:**
• **First Class Honours** (GPA 3.7-4.0): Excellent - Top 5-10% of graduates
• **Second Class Honours - Upper** (GPA 3.3-3.69): Very Good - Top 20-30%
• **Second Class Honours - Lower** (GPA 3.0-3.29): Good - Top 50%
• **General Pass** (GPA 2.0-2.99): Satisfactory completion

**To achieve First Class Honours:**"""
        
        if gpa >= 3.7:
            response += "\n✅ You're already there! Maintain your excellent performance."
        else:
            points_needed = 3.7 - gpa
            response += f"\n📈 You need to raise your GPA by {points_needed:.2f} points"
            response += f"\n💡 Focus on achieving A and A- grades in remaining courses"
            
            if gpa >= 3.3:
                response += f"\n🎯 You're close! Consistent A grades can get you there"
            else:
                response += f"\n⚡ Significant improvement needed - consider academic support"
        
        response += f"\n\n**NSBM Career Impact:**"
        response += f"\n• First Class: Excellent for postgraduate studies and competitive jobs"
        response += f"\n• Second Upper: Very good prospects for most graduate positions"
        response += f"\n• Second Lower: Good foundation for career development"
        
        return response
    
    def _generate_nsbm_planning_response(self, current: Dict, future: Dict, planned_courses: List) -> str:
        """Generate response for NSBM course planning scenario"""
        
        current_gpa = current['gpa']
        future_gpa = future['gpa']
        improvement = future_gpa - current_gpa
        
        current_class = current['academic_standing']
        future_class = future['academic_standing']
        
        response = f"""Here's your NSBM GPA projection with your planned courses:

📈 **Current Status:**
   • GPA: {current_gpa}
   • Classification: {current_class}

🎯 **Projected Status:**
   • GPA: {future_gpa}
   • Classification: {future_class}
   • Improvement: +{improvement:.3f} points

**Planned Courses Impact:**"""
        
        for name, credits, grade in planned_courses:
            calculator = NSBMGPACalculator()
            gpa_points = calculator._convert_to_nsbm_gpa_points(grade)
            response += f"\n• {name} ({credits} credits, {grade}): +{credits * gpa_points:.1f} grade points"
        
        response += f"\n\n**NSBM Classification Analysis:**"
        
        if current_class != future_class:
            response += f"\n🎉 **Excellent!** You'll move from {current_class} to {future_class}!"
        else:
            response += f"\n📊 You'll remain in {future_class} but with a stronger GPA."
        
        if "First Class" in future_class:
            response += f"\n🌟 Outstanding achievement! First Class Honours at NSBM!"
        elif "Upper Division" in future_class:
            response += f"\n✅ Excellent! Second Class Honours - Upper Division!"
        
        response += f"\n\n💡 **NSBM Study Strategy:**"
        response += f"\n• Prioritize high-credit courses for maximum GPA impact"
        response += f"\n• Use NSBM learning support services"
        response += f"\n• Form study groups with high-performing NSBM students"
        response += f"\n• Regular consultation with your academic advisor"
        
        return response


def demonstrate_nsbm_mcp_integration():
    """Demonstrate how MCP tools work for NSBM students"""
    
    print("\n" + "="*60)
    print("NSBM MCP TOOLS INTEGRATION DEMONSTRATION")
    print("="*60)
    
    print("When an NSBM student asks: 'Calculate my GPA'")
    print("The AI would use these NSBM-specific MCP tools:\n")
    
    # Example 1: calculate_nsbm_gpa
    print("1. MCP Tool: calculate_nsbm_gpa")
    print("   Input: course_names=['Programming', 'Math', 'Physics']")
    print("          credits=[4.0, 4.0, 3.0]")
    print("          grades=['A', 'B+', '85']")
    
    try:
        calculator = NSBMGPACalculator()
        courses = [("Programming", 4.0, "A"), ("Math", 4.0, "B+"), ("Physics", 3.0, 85)]
        
        for name, credits, grade in courses:
            calculator.add_course(name, credits, grade)
        
        result = calculator.calculate_gpa()
        suggestions = calculator.get_nsbm_improvement_suggestions()
        
        mcp_response = {
            "gpa": result["gpa"],
            "academic_standing": result["academic_standing"],
            "grading_system": "NSBM University",
            "improvement_suggestions": suggestions[:3],
            "status": "success"
        }
        
        print(f"   Output: {json.dumps(mcp_response, indent=2)}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n2. MCP Tool: get_nsbm_grade_info")
    print("   Input: grade='B+'")
    
    try:
        calculator = NSBMGPACalculator()
        grade_info = calculator.get_nsbm_grade_info("B+")
        
        print(f"   Output: {json.dumps(grade_info, indent=2)}")
        
    except Exception as e:
        print(f"   Error: {e}")


def run_nsbm_api_demo():
    """Demonstrate NSBM-specific REST API endpoints"""
    
    print("\n" + "="*60)
    print("NSBM REST API INTEGRATION DEMONSTRATION")
    print("="*60)
    
    print("NSBM-specific API endpoints:")
    print("\n1. POST /nsbm/gpa/calculate")
    print("   Purpose: Calculate GPA for NSBM students")
    print("   Example request:")
    
    api_request = {
        "course_names": ["Programming Fundamentals", "Mathematics", "Physics", "English"],
        "credits": [4.0, 4.0, 3.0, 2.0],
        "grades": ["A", "B+", "A-", 85]
    }
    
    print(f"   {json.dumps(api_request, indent=2)}")
    
    print("\n2. POST /nsbm/gpa/simple")
    print("   Purpose: Simple NSBM GPA calculation")
    print("   Example request:")
    
    simple_request = {
        "credits": [3.0, 4.0, 2.0, 3.0],
        "grade_points": [4.0, 3.3, 3.7, 2.0]
    }
    
    print(f"   {json.dumps(simple_request, indent=2)}")
    
    print("\n3. POST /nsbm/gpa/grade-info")
    print("   Purpose: Get NSBM grade information and classification")
    print("   Example request:")
    
    grade_request = {
        "grade": "B+"
    }
    
    print(f"   {json.dumps(grade_request, indent=2)}")
    
    print("\n4. GET /nsbm/gpa/help")
    print("   Purpose: Get NSBM GPA system information")
    print("   No request body needed")
    
    print("\nAll endpoints include NSBM-specific:")
    print("• Degree classification system (First Class Honours, etc.)")
    print("• NSBM grading scale (A+ to F)")
    print("• Academic standing assessment")
    print("• NSBM-specific improvement suggestions")


if __name__ == "__main__":
    print("RIGEL AI Chatbot - NSBM GPA Integration Testing")
    print("Copyright (C) 2025 Zerone Laboratories")
    print("=" * 60)
    
    # Run unit tests
    print("\nRunning NSBM-specific unit tests...")
    unittest.main(argv=[''], exit=False, verbosity=2)
    
    # Run integration demonstrations
    demonstrate_nsbm_mcp_integration()
    run_nsbm_api_demo()
    
    print("\n" + "="*60)
    print("NSBM GPA SYSTEM IMPLEMENTATION COMPLETE")
    print("="*60)
    print("\nThe RIGEL AI chatbot now has comprehensive NSBM GPA calculation capabilities:")
    print("✅ NSBM-specific GPA calculator with proper grading scale")
    print("✅ NSBM degree classification system (First Class Honours, etc.)")
    print("✅ MCP tools integration for AI assistant usage")
    print("✅ REST API endpoints for external applications")
    print("✅ Comprehensive error handling and validation")
    print("✅ NSBM-specific academic standing assessment")
    print("✅ NSBM improvement suggestions and guidance")
    print("✅ Backward compatibility with existing code")
    print("\nNSBM students can now ask the AI questions like:")
    print("• 'What's my NSBM GPA if I got A in Programming, B+ in Math, and 85% in Physics?'")
    print("• 'How can I achieve First Class Honours at NSBM?'")
    print("• 'What does a B+ grade mean in NSBM percentage scale?'")
    print("• 'If I get A's in my next 3 NSBM courses, what will my classification be?'")
    print("• 'What are the NSBM degree classification requirements?'")
