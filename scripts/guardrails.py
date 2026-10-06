def check_academic_rules(exam_days_left, daily_hours):
    warnings = []
    
    # Check for emergency exam timeline
    if exam_days_left <= 3:
        warnings.append("EMERGENCY REVISION MODE: Exam is in 3 days or less. High-yield summary and past paper drill prioritized.")
        
    # Check for burnout risk
    if daily_hours >= 8:
        warnings.append("BURNOUT ALERT: Planning 8+ hours of study per day is unsustainable. Ensure mandatory 15-minute breaks every 2 hours.")
        
    return warnings