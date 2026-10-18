def check_academic_rules(exam_days_left, daily_hours, confidence=None, study_style=None):
    """
    Evaluate a student's study plan against a set of academic guardrail rules.

    Parameters
    ----------
    exam_days_left : int   – Calendar days remaining before the exam.
    daily_hours    : int   – Hours per day the student plans to study.
    confidence     : str   – Student's self-assessed level (optional).
                             One of: "Complete Beginner", "Know the Basics",
                                     "Intermediate", "Advanced Revision".
    study_style    : str   – Preferred study mode (optional).

    Returns
    -------
    list[str] – Zero or more human-readable warning strings.
    """
    warnings = []
    total_hours = exam_days_left * daily_hours

    # -- Rule 1: Emergency revision mode ----------------------------------------
    if exam_days_left <= 3:
        warnings.append(
            "EMERGENCY REVISION MODE: Exam is in 3 days or less. "
            "High-yield summary and past paper drill prioritized."
        )

    # -- Rule 2: Burnout risk ----------------------------------------------------
    if daily_hours >= 8:
        warnings.append(
            "BURNOUT ALERT: Planning 8+ hours of study per day is unsustainable. "
            "Ensure mandatory 15-minute breaks every 2 hours."
        )

    # -- Rule 3: Total hours too low (compressed plan) ---------------------------
    # Heuristic: fewer than 10 total hours is almost certainly insufficient
    # for any meaningful exam preparation.
    if total_hours < 10:
        warnings.append(
            "COMPRESSED PLAN WARNING: Your total available study time is only "
            f"{total_hours} hours ({exam_days_left} day(s) x {daily_hours} hr/day). "
            "This is very tight -- prioritise the highest-yield topics and practice "
            "past questions exclusively."
        )

    # -- Rule 4: Zero-productivity risk (last-minute crammer) --------------------
    if exam_days_left == 1 and daily_hours <= 2:
        warnings.append(
            "CRITICAL - LAST DAY & LOW HOURS: You have only 1 day left and "
            f"{daily_hours} hour(s) planned. Focus solely on must-know definitions, "
            "formulas, and a single past paper. Do not attempt new topics."
        )

    # -- Rule 5: Beginner + very little time -------------------------------------
    if confidence == "Complete Beginner" and exam_days_left <= 7:
        warnings.append(
            "SCOPE ALERT (Beginner): As a complete beginner with only "
            f"{exam_days_left} day(s) remaining, attempting the full syllabus "
            "is unrealistic. Narrow your focus to the 3-4 core topics most likely "
            "to appear on the exam."
        )

    # -- Rule 6: Overconfidence check --------------------------------------------
    if confidence == "Advanced Revision" and total_hours < 15:
        warnings.append(
            "OVERCONFIDENCE CHECK: Even at an Advanced Revision level, "
            f"{total_hours} total hours may not be enough for thorough preparation. "
            "Ensure your revision covers edge-case questions and tricky past-paper formats."
        )

    # -- Rule 7: Overplanning / too spread out -----------------------------------
    if total_hours > 200:
        warnings.append(
            "OVERPLANNING WARNING: Your plan spans "
            f"{total_hours} hours in total ({exam_days_left} day(s) x {daily_hours} hr/day). "
            "Such a long horizon risks losing focus and motivation. "
            "Consider breaking the plan into weekly sprint goals with clear milestones."
        )

    # -- Rule 8: Cram spike (short window + high daily load) ---------------------
    if daily_hours >= 6 and exam_days_left <= 7:
        warnings.append(
            "CRAM SPRINT ADVISORY: Studying "
            f"{daily_hours} hours/day for {exam_days_left} day(s) is intense. "
            "Use the Pomodoro technique: 50-minute focused blocks followed by "
            "10-minute breaks. Sleep at least 7 hours -- consolidation is critical."
        )

    return warnings