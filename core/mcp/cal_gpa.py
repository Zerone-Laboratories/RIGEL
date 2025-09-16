# This file is part of RIGEL Engine.
#
# RIGEL Engine is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# RIGEL Engine is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
NSBM University GPA Calculation Module for RIGEL AI Chatbot
Specifically designed for NSBM students and grading system
"""

from typing import List, Dict, Optional, Union
import json


class NSBMGPACalculator:
    """
    NSBM-specific GPA Calculator for AI Chatbot Usage
    Designed exclusively for NSBM University students
    """
    
    # NSBM Official Grading Scale
    NSBM_GRADE_SCALE = {
        'A+': 4.0, 'A': 4.0, 'A-': 3.7,
        'B+': 3.3, 'B': 3.0, 'B-': 2.7,
        'C+': 2.3, 'C': 2.0, 'C-': 1.7,
        'D+': 1.3, 'D': 1.0, 'F': 0.0
    }
    
    def __init__(self):
        """Initialize NSBM GPA Calculator"""
        self.courses = []
    def add_course(self, 
                   course_name: str, 
                   credits: float, 
                   grade: Union[str, float]) -> bool:
        """
        Add a course to the NSBM GPA calculation
        
        Args:
            course_name: Name of the course
            credits: Credit hours for the course
            grade: Grade received (NSBM letter grade or percentage)
            
        Returns:
            bool: True if course was added successfully
        """
        try:
            # Validate inputs
            if credits <= 0:
                raise ValueError("Credits must be positive")
                
            # Convert grade to GPA points using NSBM system
            gpa_points = self._convert_to_nsbm_gpa_points(grade)
            
            course = {
                'name': course_name,
                'credits': float(credits),
                'grade': grade,
                'gpa_points': gpa_points
            }
            
            self.courses.append(course)
            return True
            
        except (ValueError, TypeError) as e:
            print(f"Error adding course {course_name}: {str(e)}")
            return False
    
    def _convert_to_nsbm_gpa_points(self, grade: Union[str, float]) -> float:
        """Convert various grade formats to NSBM GPA points"""
        
        if isinstance(grade, (int, float)):
            # Treat as percentage and convert to NSBM scale
            return self._nsbm_percentage_to_gpa(grade)
        
        elif isinstance(grade, str):
            grade = grade.upper().strip()
            
            # Check NSBM scale
            if grade in self.NSBM_GRADE_SCALE:
                return self.NSBM_GRADE_SCALE[grade]
            
            # Try to parse as percentage
            try:
                percentage = float(grade)
                return self._nsbm_percentage_to_gpa(percentage)
            except ValueError:
                pass
        
        raise ValueError(f"Unable to convert grade '{grade}' to NSBM GPA points. Use NSBM letter grades (A+, A, A-, B+, B, B-, C+, C, C-, D+, D, F) or percentages (0-100).")
    
    def _nsbm_percentage_to_gpa(self, percentage: float) -> float:
        """Convert percentage to GPA points using NSBM scale"""
        if not (0 <= percentage <= 100):
            raise ValueError("Percentage must be between 0 and 100")
            
        if percentage >= 90: return 4.0    # A+/A
        elif percentage >= 85: return 3.7  # A-
        elif percentage >= 80: return 3.3  # B+
        elif percentage >= 75: return 3.0  # B
        elif percentage >= 70: return 2.7  # B-
        elif percentage >= 65: return 2.3  # C+
        elif percentage >= 60: return 2.0  # C
        elif percentage >= 55: return 1.7  # C-
        elif percentage >= 50: return 1.3  # D+
        elif percentage >= 45: return 1.0  # D
        else: return 0.0                   # F
    def calculate_gpa(self) -> Dict[str, Union[float, int, str]]:
        """
        Calculate NSBM GPA and provide comprehensive analysis
        
        Returns:
            Dict containing GPA calculation results and analysis
        """
        if not self.courses:
            return {
                'gpa': 0.0,
                'total_credits': 0,
                'total_courses': 0,
                'status': 'error',
                'message': 'No courses added'
            }
        
        total_grade_points = 0.0
        total_credits = 0.0
        grade_distribution = {}
        
        # Calculate totals and distribution
        for course in self.courses:
            total_grade_points += course['credits'] * course['gpa_points']
            total_credits += course['credits']
            
            # Grade distribution
            grade_key = str(course['grade'])
            grade_distribution[grade_key] = grade_distribution.get(grade_key, 0) + 1
        
        # Calculate GPA
        gpa = round(total_grade_points / total_credits, 3) if total_credits > 0 else 0.0
        
        # Determine NSBM academic standing
        standing = self._get_nsbm_academic_standing(gpa)
        
        return {
            'gpa': gpa,
            'total_credits': total_credits,
            'total_courses': len(self.courses),
            'total_grade_points': round(total_grade_points, 3),
            'academic_standing': standing,
            'grade_distribution': grade_distribution,
            'grading_system': 'NSBM University',
            'status': 'success',
            'courses': self.courses
        }
    
    def _get_nsbm_academic_standing(self, gpa: float) -> str:
        """Determine NSBM academic standing based on GPA"""
        if gpa >= 3.7:
            return "First Class Honours (Excellent)"
        elif gpa >= 3.3:
            return "Second Class Honours - Upper Division (Very Good)"
        elif gpa >= 3.0:
            return "Second Class Honours - Lower Division (Good)"
        elif gpa >= 2.0:
            return "General Pass (Satisfactory)"
        elif gpa >= 1.0:
            return "Academic Probation"
        else:
            return "Academic Dismissal Risk"
    
    def get_nsbm_improvement_suggestions(self) -> List[str]:
        """Generate NSBM-specific suggestions for GPA improvement"""
        result = self.calculate_gpa()
        if result['status'] == 'error':
            return ["Add courses to get improvement suggestions"]
        
        gpa = result['gpa']
        suggestions = []
        
        if gpa < 2.0:
            suggestions.extend([
                "Urgent: Meet with your NSBM academic advisor immediately",
                "Consider reducing course load to focus on core subjects",
                "Utilize NSBM tutoring services and study groups",
                "Attend all lectures and practical sessions",
                "Seek help from lecturers during office hours"
            ])
        elif gpa < 3.0:
            suggestions.extend([
                "Focus on improving study techniques and time management",
                "Form study groups with high-performing NSBM students",
                "Consider retaking failed or low-grade courses if allowed",
                "Attend NSBM academic skills workshops",
                "Use university library resources effectively"
            ])
        elif gpa < 3.3:
            suggestions.extend([
                "Aim for A grades in upcoming courses to reach Upper Second Class",
                "Focus on challenging but achievable course selections",
                "Maintain consistent study schedule throughout the semester",
                "Consider advanced courses in your area of strength"
            ])
        elif gpa < 3.7:
            suggestions.extend([
                "Excellent progress! Aim for First Class Honours",
                "Focus on achieving A+ and A grades consistently",
                "Consider research projects or honors thesis opportunities",
                "Engage in academic competitions and conferences"
            ])
        else:
            suggestions.extend([
                "Outstanding achievement! Maintain First Class Honours standard",
                "Consider advanced research opportunities with NSBM faculty",
                "Explore postgraduate study options",
                "Mentor junior students and lead study groups",
                "Apply for academic scholarships and awards"
            ])
        
        return suggestions
    
    def get_nsbm_grade_info(self, grade: str) -> Dict[str, Union[str, float]]:
        """Get detailed information about an NSBM grade"""
        try:
            gpa_points = self._convert_to_nsbm_gpa_points(grade)
            
            # Determine classification
            if gpa_points >= 3.7: classification = "First Class Honours"
            elif gpa_points >= 3.3: classification = "Second Class Honours - Upper"
            elif gpa_points >= 3.0: classification = "Second Class Honours - Lower"
            elif gpa_points >= 2.0: classification = "General Pass"
            elif gpa_points >= 1.0: classification = "Pass (Probation Risk)"
            else: classification = "Fail"
            
            # Determine percentage range
            if gpa_points >= 4.0: percentage = "90-100%"
            elif gpa_points >= 3.7: percentage = "85-89%"
            elif gpa_points >= 3.3: percentage = "80-84%"
            elif gpa_points >= 3.0: percentage = "75-79%"
            elif gpa_points >= 2.7: percentage = "70-74%"
            elif gpa_points >= 2.3: percentage = "65-69%"
            elif gpa_points >= 2.0: percentage = "60-64%"
            elif gpa_points >= 1.7: percentage = "55-59%"
            elif gpa_points >= 1.3: percentage = "50-54%"
            elif gpa_points >= 1.0: percentage = "45-49%"
            else: percentage = "0-44%"
            
            return {
                'input_grade': grade,
                'gpa_points': gpa_points,
                'classification': classification,
                'percentage_range': percentage,
                'status': 'success'
            }
            
        except ValueError as e:
            return {
                'input_grade': grade,
                'error': str(e),
                'status': 'error'
            }
    
    def clear_courses(self):
        """Clear all courses from the calculator"""
        self.courses = []
    
    def export_data(self) -> str:
        """Export NSBM GPA data as JSON string"""
        result = self.calculate_gpa()
        return json.dumps(result, indent=2)


# Legacy compatibility class
class Logic(NSBMGPACalculator):
    """Legacy Logic class for backward compatibility"""
    
    def __init__(self, listCredit: List[float], listGPV: List[float]):
        """
        Legacy constructor for backward compatibility
        
        Args:
            listCredit: List of credit hours
            listGPV: List of grade point values
        """
        super().__init__()
        
        # Validate inputs
        if len(listCredit) != len(listGPV):
            self._legacy_error = True
            return
        
        self._legacy_error = False
        
        # Add courses using legacy format
        for i, (credits, gpv) in enumerate(zip(listCredit, listGPV)):
            self.add_course(f"Course_{i+1}", credits, gpv)
    
    def getGPA(self) -> float:
        """
        Legacy GPA calculation method
        
        Returns:
            float: GPA value or -1.00 for error
        """
        if self._legacy_error:
            return -1.00
        
        result = self.calculate_gpa()
        return result.get('gpa', -1.00)


# Alias for backward compatibility
GPACalculator = NSBMGPACalculator