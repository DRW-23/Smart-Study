import json
import os
import pandas as pd

# Define paths relative to the project structure
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_path = os.path.join(BASE_DIR, "data", "kdu_student_dataset.csv")
jsonl_path = os.path.join(BASE_DIR, "data", "student_training_data.jsonl")

# 1. Load the KDU CSV dataset
df = pd.read_csv(csv_path)
print(f"Loaded {len(df)} rows from {csv_path}")

jsonl_records = []

# 2. Iterate through each student record
for _, row in df.iterrows():
    instruction = (
        "You are an expert academic advisor AI for the BSc (Hons) Information Technology program at KDU. "
        "Analyze the student's academic metrics, predict their final performance category (Excellent, Good, Average, or Poor), "
        "provide the reasoning behind the evaluation, and give a specific study recommendation for their weak subject."
    )
    
    student_input = (
        f"Degree Program: BSc (Hons) Information Technology\n"
        f"Study Hours per Week: {row['Study_Hours']}\n"
        f"Attendance Rate: {row['Attendance_%']}%\n"
        f"Assignment Marks: {row['Assignment_Marks']}\n"
        f"Quiz Marks: {row['Quiz_Marks']}\n"
        f"Previous GPA: {row['Previous_GPA']}\n"
        f"Identified Weak Subject: {row['Weak_Subject']}\n"
        f"Exam Days Remaining: {row['Exam_Days_Left']}"
    )
    
    performance = row['Performance_Class']
    weak_subject = row['Weak_Subject']
    exam_days = row['Exam_Days_Left']
    study_hours = row['Study_Hours']
    attendance = row['Attendance_%']
    gpa = row['Previous_GPA']
    
    # Generate tailored reasoning and recommendation
    if performance == "Excellent":
        output = (
            f"Predicted Performance: Excellent\n\n"
            f"Reasoning: The student exhibits strong academic consistency with an attendance rate of {attendance}% "
            f"and dedicates {study_hours} hours/week to study. A GPA of {gpa} indicates a solid foundation in the IT curriculum.\n\n"
            f"Recommendation: Maintain this study rhythm. Over the next {exam_days} days, prioritize "
            f"active recall, lab revision, and past paper practice specifically for {weak_subject} to retain top marks."
        )
    elif performance == "Good":
        output = (
            f"Predicted Performance: Good\n\n"
            f"Reasoning: The student is performing steadily with {attendance}% attendance and a {gpa} GPA, "
            f"but requires strategic revision to achieve an Excellent classification.\n\n"
            f"Recommendation: Increase weekly study time from {study_hours} hours by 3-5 additional hours. "
            f"Focus heavily on {weak_subject} by tackling practical problems and past semester exams over the next {exam_days} days."
        )
    elif performance == "Average":
        output = (
            f"Predicted Performance: Average\n\n"
            f"Reasoning: An attendance of {attendance}% and moderate continuous assessment scores indicate academic risk. "
            f"Current study efforts ({study_hours} hours/week) are insufficient with only {exam_days} days remaining before exams.\n\n"
            f"Recommendation: Structured intervention is necessary. Dedicate daily 2-hour revision sessions specifically "
            f"to foundational topics in {weak_subject} and consult lecture notes and tutorial help desks."
        )
    else:  # Poor
        output = (
            f"Predicted Performance: Poor\n\n"
            f"Reasoning: High academic risk flagged. Attendance at {attendance}% combined with low assignment and quiz marks "
            f"indicates urgent intervention is required to avoid module failure.\n\n"
            f"Recommendation: Immediate action required. Allocate at least 15-20 hours per week directly to core principles "
            f"in {weak_subject}. Review past tutorial sheets and meet with course instructors before the exam in {exam_days} days."
        )
        
    record = {
        "instruction": instruction,
        "input": student_input,
        "output": output
    }
    jsonl_records.append(record)

# 3. Export to JSONL format
with open(jsonl_path, "w", encoding="utf-8") as f:
    for record in jsonl_records:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

print(f"Successfully generated {jsonl_path} with {len(jsonl_records)} instruction samples.")