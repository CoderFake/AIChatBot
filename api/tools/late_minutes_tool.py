"""
Late Minutes Tracking Tool (TODO Tool)
Tracks late minutes for employees by day, month, week with random generation
"""
import random
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Type, List, Union
from langchain_core.tools import BaseTool
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from pydantic import BaseModel
from models.models import LateMinutesInput
from utils.logging import get_logger

logger = get_logger(__name__)


class LateMinutesTool(BaseTool):
    """
    TODO Tool for tracking employee late minutes
    Randomly generates late minutes data for specified users and time periods
    """
    name: str = "late_minutes_tracker"
    description: str = "Track late minutes for employees by day, week, month, or year. To use the tool, get the time the user wants to search and the checkin/checkout time in the labor regulations first"
    args_schema: Type[BaseModel] = LateMinutesInput
    category: str = "late_minutes"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        logger.info("Initialized Late Minutes Tracker tool")
        
        self._time_ranges = getattr(self, 'time_ranges', {
            'daily': (0, 45),
            'weekly': (0, 180), 
            'monthly': (0, 600),
            'yearly': (0, 4800)
        })
        
        self.requires_parameter_parsing = True
    
    def get_parsing_instructions(self) -> List[str]:
        """Provide dynamic parsing instructions based on tool schema"""
        instructions = []
        
        if hasattr(self, 'args_schema') and self.args_schema:
            schema = self.args_schema.model_json_schema()
            properties = schema.get('properties', {})
            
            for param_name, param_info in properties.items():
                description = param_info.get('description', f'Extract {param_name} parameter')
                instructions.append(f"{param_name}: {description}")
        
        if not instructions:
            instructions = [
                "Extract relevant parameters from the user query",
                "Focus on user identification and time-related information",
                "Convert time expressions to appropriate formats",
                "Exclude system-level parameters not relevant to tool functionality"
            ]
        
        return instructions
        
        # Indicate this tool requires parameter parsing
        self.requires_parameter_parsing = True
    
    def get_parsing_instructions(self) -> List[str]:
        """Provide dynamic parsing instructions for this tool"""
        return [
            "Extract user names, usernames, or email addresses from the query",
            "Identify time period: 'day', 'week', 'month', or 'year'",
            "Handle Vietnamese time expressions: 'ngày'->day, 'tuần'->week, 'tháng'->month, 'năm'->year",
            "Support multiple users: split comma-separated names or detect list patterns",
            "Extract checkin/checkout times if mentioned (e.g., '9:00', '09:00', '18:00')",
            "Handle time expressions: 'checkin lúc 9h', 'checkout 6h chiều', 'làm từ 8h đến 5h'",
            "Convert Vietnamese time: '8h', '9 giờ', '6h chiều' to HH:MM format",
            "Default checkin_time: '09:00', default checkout_time: '18:00' if not specified",
            "Default time_period: 'day' if not specified",
            "Convert relative time expressions to specific periods",
            "Focus only on extracting users, time periods, and work schedule information",
            "Do NOT include system parameters like query, user_id, user_role, department, access_levels"
        ]
    
    def _add_minutes_to_time(self, time_str: str, minutes: int) -> str:
        """Add minutes to a time string (HH:MM format)"""
        try:
            hour, minute = map(int, time_str.split(':'))
            total_minutes = hour * 60 + minute + minutes
            new_hour = (total_minutes // 60) % 24
            new_minute = total_minutes % 60
            return f"{new_hour:02d}:{new_minute:02d}"
        except:
            return time_str
    
    def _subtract_minutes_from_time(self, time_str: str, minutes: int) -> str:
        """Subtract minutes from a time string (HH:MM format)"""
        try:
            hour, minute = map(int, time_str.split(':'))
            total_minutes = hour * 60 + minute - minutes
            if total_minutes < 0:
                total_minutes += 24 * 60  # Handle day rollover
            new_hour = (total_minutes // 60) % 24
            new_minute = total_minutes % 60
            return f"{new_hour:02d}:{new_minute:02d}"
        except:
            return time_str
        
    def _generate_random_late_minutes(self, time_period: str, user: str, checkin_time: str = None, checkout_time: str = None) -> Dict[str, Any]:
        """Generate random late minutes data for a user based on time period and checkin/checkout times"""
        
        # Set random seed based on user name for consistency
        random.seed(hash(user) % 1000)
        
        # Parse checkin/checkout times if provided
        expected_checkin = checkin_time or "09:00"
        expected_checkout = checkout_time or "18:00"
        
        # Calculate work hours for context
        try:
            checkin_hour, checkin_min = map(int, expected_checkin.split(':'))
            checkout_hour, checkout_min = map(int, expected_checkout.split(':'))
            total_work_minutes = (checkout_hour * 60 + checkout_min) - (checkin_hour * 60 + checkin_min)
        except:
            total_work_minutes = 540  # Default 9 hours
        
        if time_period.lower() == "day":
            # Generate checkin lateness (0-45 minutes)
            daily_range = self._time_ranges.get('daily', (0, 45))
            checkin_late = random.randint(*daily_range)
            # Occasionally generate early checkout (0-30 minutes)
            checkout_early = random.randint(0, 30) if random.random() < 0.3 else 0
            
            late_minutes = checkin_late + checkout_early
            details = {
                "total_minutes": late_minutes,
                "checkin_late_minutes": checkin_late,
                "checkout_early_minutes": checkout_early,
                "expected_checkin": expected_checkin,
                "expected_checkout": expected_checkout,
                "actual_checkin": self._add_minutes_to_time(expected_checkin, checkin_late),
                "actual_checkout": self._subtract_minutes_from_time(expected_checkout, checkout_early),
                "periods": 1,
                "average_per_period": late_minutes
            }
        elif time_period.lower() == "week":
            # Generate data for each day of the week
            daily_data = []
            total_late = 0
            
            for day_idx in range(7):
                checkin_late = random.randint(0, 30)
                checkout_early = random.randint(0, 20) if random.random() < 0.25 else 0
                day_total = checkin_late + checkout_early
                total_late += day_total
                
                daily_data.append({
                    "checkin_late": checkin_late,
                    "checkout_early": checkout_early,
                    "total": day_total
                })
            
            late_minutes = total_late
            details = {
                "total_minutes": late_minutes,
                "periods": 7,
                "average_per_period": round(late_minutes / 7, 2),
                "expected_checkin": expected_checkin,
                "expected_checkout": expected_checkout,
                "daily_breakdown": {
                    "Monday": daily_data[0],
                    "Tuesday": daily_data[1], 
                    "Wednesday": daily_data[2],
                    "Thursday": daily_data[3],
                    "Friday": daily_data[4],
                    "Saturday": daily_data[5],
                    "Sunday": daily_data[6]
                }
            }
        elif time_period.lower() == "month":
            # Generate data for ~22 working days
            working_days = 22
            total_checkin_late = 0
            total_checkout_early = 0
            days_late = 0
            
            for _ in range(working_days):
                checkin_late = random.randint(0, 25)
                checkout_early = random.randint(0, 15) if random.random() < 0.2 else 0
                
                if checkin_late > 0 or checkout_early > 0:
                    days_late += 1
                
                total_checkin_late += checkin_late
                total_checkout_early += checkout_early
            
            late_minutes = total_checkin_late + total_checkout_early
            details = {
                "total_minutes": late_minutes,
                "checkin_late_minutes": total_checkin_late,
                "checkout_early_minutes": total_checkout_early,
                "periods": working_days,
                "average_per_period": round(late_minutes / working_days, 2),
                "working_days": working_days,
                "late_days": days_late,
                "expected_checkin": expected_checkin,
                "expected_checkout": expected_checkout
            }
        elif time_period.lower() == "year":
            working_days = 250
            monthly_totals = []
            total_checkin_late = 0
            total_checkout_early = 0
            
            for month in range(12):
                month_days = random.randint(18, 23)  
                month_checkin_late = sum([random.randint(0, 20) for _ in range(month_days)])
                month_checkout_early = sum([random.randint(0, 10) if random.random() < 0.15 else 0 for _ in range(month_days)])
                month_total = month_checkin_late + month_checkout_early
                
                monthly_totals.append({
                    "total": month_total,
                    "checkin_late": month_checkin_late,
                    "checkout_early": month_checkout_early
                })
                
                total_checkin_late += month_checkin_late
                total_checkout_early += month_checkout_early
            
            late_minutes = total_checkin_late + total_checkout_early
            details = {
                "total_minutes": late_minutes,
                "checkin_late_minutes": total_checkin_late,
                "checkout_early_minutes": total_checkout_early,
                "periods": 12,
                "average_per_period": round(late_minutes / 12, 2),
                "working_days": working_days,
                "expected_checkin": expected_checkin,
                "expected_checkout": expected_checkout,
                "monthly_breakdown": {
                    f"Month_{i+1}": monthly_totals[i] for i in range(12)
                }
            }
        else:
            # Default to daily
            checkin_late = random.randint(*self._daily_range)
            checkout_early = random.randint(0, 30) if random.random() < 0.3 else 0
            late_minutes = checkin_late + checkout_early
            
            details = {
                "total_minutes": late_minutes,
                "checkin_late_minutes": checkin_late,
                "checkout_early_minutes": checkout_early,
                "expected_checkin": expected_checkin,
                "expected_checkout": expected_checkout,
                "periods": 1,
                "average_per_period": late_minutes
            }
        
        return {
            "user": user,
            "time_period": time_period,
            "late_minutes": late_minutes,
            "details": details,
            "generated_at": datetime.now().isoformat()
        }
    
    def _format_response(self, results: List[Dict[str, Any]], time_period: str) -> str:
        """Format the response in a user-friendly way"""
        if not results:
            return "No data found for the specified users."
        
        response_lines = [f"=== Late Minutes Report ({time_period.title()}) ==="]
        
        # Add work schedule info if available
        if results and "details" in results[0]:
            details = results[0]["details"]
            if "expected_checkin" in details and "expected_checkout" in details:
                response_lines.append(f"📋 Work Schedule: {details['expected_checkin']} - {details['expected_checkout']}")
        
        response_lines.append("")
        
        total_late_minutes = 0
        total_checkin_late = 0
        total_checkout_early = 0
        
        for result in results:
            user = result["user"]
            late_minutes = result["late_minutes"]
            details = result["details"]
            
            total_late_minutes += late_minutes
            if "checkin_late_minutes" in details:
                total_checkin_late += details["checkin_late_minutes"]
            if "checkout_early_minutes" in details:
                total_checkout_early += details["checkout_early_minutes"]
            
            response_lines.append(f"👤 User: {user}")
            response_lines.append(f"⏰ Total Late Minutes: {late_minutes}")
            
            # Show checkin/checkout breakdown if available
            if "checkin_late_minutes" in details and "checkout_early_minutes" in details:
                response_lines.append(f"   📥 Late Checkin: {details['checkin_late_minutes']} minutes")
                response_lines.append(f"   📤 Early Checkout: {details['checkout_early_minutes']} minutes")
            
            # Show actual times for daily reports
            if time_period.lower() == "day" and "actual_checkin" in details:
                response_lines.append(f"   🕐 Actual Checkin: {details['actual_checkin']}")
                response_lines.append(f"   🕔 Actual Checkout: {details['actual_checkout']}")
            
            if time_period.lower() == "week" and "daily_breakdown" in details:
                response_lines.append("📅 Daily Breakdown:")
                for day, day_data in details["daily_breakdown"].items():
                    if isinstance(day_data, dict):
                        total_day = day_data.get('total', 0)
                        if total_day > 0:
                            checkin_late = day_data.get('checkin_late', 0)
                            checkout_early = day_data.get('checkout_early', 0)
                            response_lines.append(f"   {day}: {total_day} min (checkin: +{checkin_late}, checkout: -{checkout_early})")
                    elif day_data > 0:
                        response_lines.append(f"   {day}: {day_data} minutes")
            
            elif time_period.lower() == "month":
                response_lines.append(f"📊 Working Days: {details.get('working_days', 0)}")
                response_lines.append(f"📈 Days Late: {details.get('late_days', 0)}")
                response_lines.append(f"📉 Average per Day: {details.get('average_per_period', 0)} minutes")
                if "checkin_late_minutes" in details:
                    response_lines.append(f"   📥 Total Late Checkin: {details['checkin_late_minutes']} minutes")
                    response_lines.append(f"   📤 Total Early Checkout: {details['checkout_early_minutes']} minutes")
            
            elif time_period.lower() == "year" and "monthly_breakdown" in details:
                response_lines.append("📅 Top 3 Months with Most Late Minutes:")
                monthly_data = details["monthly_breakdown"]
                # Sort by total if dict contains objects, otherwise by value
                if monthly_data and isinstance(list(monthly_data.values())[0], dict):
                    sorted_months = sorted(monthly_data.items(), key=lambda x: x[1].get('total', 0), reverse=True)[:3]
                    for month, month_data in sorted_months:
                        if month_data.get('total', 0) > 0:
                            response_lines.append(f"   {month}: {month_data['total']} min (checkin: +{month_data.get('checkin_late', 0)}, checkout: -{month_data.get('checkout_early', 0)})")
                else:
                    sorted_months = sorted(monthly_data.items(), key=lambda x: x[1], reverse=True)[:3]
                    for month, minutes in sorted_months:
                        if minutes > 0:
                            response_lines.append(f"   {month}: {minutes} minutes")
                
                if "checkin_late_minutes" in details:
                    response_lines.append(f"📊 Year Total - Checkin Late: {details['checkin_late_minutes']} min, Checkout Early: {details['checkout_early_minutes']} min")
            
            response_lines.append("")
        
        if len(results) > 1:
            response_lines.append(f"📊 Total Late Minutes (All Users): {total_late_minutes}")
            if total_checkin_late > 0 or total_checkout_early > 0:
                response_lines.append(f"   📥 Total Late Checkin: {total_checkin_late} minutes")
                response_lines.append(f"   📤 Total Early Checkout: {total_checkout_early} minutes")
            response_lines.append(f"📈 Average per User: {round(total_late_minutes / len(results), 2)} minutes")
        
        return "\n".join(response_lines)
    
    def _run(
        self,
        users: List[str],
        time_period: str,
        specific_date: Optional[str] = None,
        checkin_time: Optional[str] = None,
        checkout_time: Optional[str] = None,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute late minutes tracking synchronously
        
        Args:
            users: List of usernames, names, or emails
            time_period: Time period to check ('day', 'week', 'month', 'year')
            specific_date: Optional specific date (currently not used in random generation)
            checkin_time: Expected checkin time in HH:MM format (e.g., '09:00')
            checkout_time: Expected checkout time in HH:MM format (e.g., '18:00')
            run_manager: Optional callback manager for tool run
        
        Returns:
            Formatted string with late minutes data
        """
        try:
            logger.info(f"Generating late minutes data for {len(users)} users, period: {time_period}, checkin: {checkin_time}, checkout: {checkout_time}")
            
            if not users:
                return "Error: No users specified"
            
            # Validate time period
            valid_periods = ["day", "week", "month", "year"]
            if time_period.lower() not in valid_periods:
                return f"Error: Invalid time period. Must be one of: {', '.join(valid_periods)}"
            
            # Generate data for each user
            results = []
            for user in users:
                user_data = self._generate_random_late_minutes(
                    time_period, 
                    user.strip(), 
                    checkin_time, 
                    checkout_time
                )
                results.append(user_data)
            
            # Format and return response
            formatted_response = self._format_response(results, time_period)
            
            logger.info(f"Generated late minutes data for {len(users)} users successfully")
            return formatted_response
            
        except Exception as e:
            error_msg = f"Error generating late minutes data: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    async def _arun(
        self,
        users: List[str],
        time_period: str,
        specific_date: Optional[str] = None,
        checkin_time: Optional[str] = None,
        checkout_time: Optional[str] = None,
        run_manager: Optional[AsyncCallbackManagerForToolRun] = None,
    ) -> str:
        """
        Execute late minutes tracking asynchronously
        
        Args:
            users: List of usernames, names, or emails
            time_period: Time period to check ('day', 'week', 'month', 'year')
            specific_date: Optional specific date (currently not used in random generation)
            checkin_time: Expected checkin time in HH:MM format (e.g., '09:00')
            checkout_time: Expected checkout time in HH:MM format (e.g., '18:00')
            run_manager: Optional async callback manager for tool run
        
        Returns:
            Formatted string with late minutes data
        """
        # For this TODO tool, async execution is the same as sync
        return self._run(users, time_period, specific_date, checkin_time, checkout_time, None)