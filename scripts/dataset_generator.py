# -*- coding: utf-8 -*-
"""
Synthetic dataset generator for KDU BSc (Hons) IT student profiles.


Usage:
    python scripts/dataset_generator.py
    python scripts/dataset_generator.py --rows 1000 --output data/my_dataset.csv --seed 99
"""

import argparse
import os
import random

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# KDU BIT Curriculum -- all 24 official modules mapped from the programme spec
# ---------------------------------------------------------------------------
KDU_IT_MODULES = [
    "IT11012: Information Technology Concepts",
    "IT11022: Fundamentals of Computer Programming",
    "IT11042: Fundamentals of Computer Systems",
    "IT12023: Object Oriented Programming",
    "IT12033: Fundamentals of Database Management Systems",
    "IT12042: Computer Systems Architecture",
    "IT12062: Computer Network Systems I",
    "IT12072: Web Technologies",
    "IT21013: Rapid Application Development",
    "IT21022: System Analysis and Design",
    "IT21043: Advanced Database Management Systems",
    "IT22013: Data Structures and Algorithms",
    "IT22022: Software Engineering",
    "IT22032: Operating Systems",
    "IT31042: Mobile Computing",
    "IT31062: Information and Data Security",
    "IT31093: Essentials of Artificial Intelligence",
    "IT32012: Distributed Systems",
    "IT32033: Cyber Security",
    "IT32043: Cloud Computing and Virtualization",
    "IT32073: Machine Learning",
    "IT41013: Data Mining and Data Warehousing",
    "IT41032: Advanced Computer Network Systems II",
    "IT41043: Database Administration",
]

# ---------------------------------------------------------------------------
# Performance classification thresholds
# ---------------------------------------------------------------------------
def classify_performance(study_hours, attendance, assignment_marks, quiz_marks, gpa):
    """
    Rule-based heuristic that assigns a Performance_Class label.
    Returns one of: 'Excellent', 'Good', 'Average', 'Poor'
    """
    score = 0

    if study_hours >= 35:
        score += 3
    elif study_hours >= 25:
        score += 2
    elif study_hours >= 15:
        score += 1

    if attendance >= 85:
        score += 3
    elif attendance >= 70:
        score += 2
    elif attendance >= 55:
        score += 1

    if assignment_marks >= 75:
        score += 2
    elif assignment_marks >= 55:
        score += 1

    if quiz_marks >= 75:
        score += 2
    elif quiz_marks >= 55:
        score += 1

    if gpa >= 3.5:
        score += 3
    elif gpa >= 2.8:
        score += 2
    elif gpa >= 2.0:
        score += 1

    if score >= 11:
        return "Excellent"
    elif score >= 8:
        return "Good"
    elif score >= 5:
        return "Average"
    else:
        return "Poor"


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------
def generate_student_profiles(n_rows=500, seed=42):
    """
    Generate n_rows synthetic KDU IT student records with realistic
    statistical distributions for each feature.
    """
    rng = np.random.default_rng(seed)
    random.seed(seed)

    records = []
    for _ in range(n_rows):
        study_hours    = int(np.clip(rng.normal(loc=25, scale=10), 2, 50))
        attendance     = int(np.clip(rng.normal(loc=72, scale=15), 30, 100))
        assignment_mks = int(np.clip(rng.normal(loc=62, scale=18), 20, 100))
        quiz_mks       = int(np.clip(rng.normal(loc=60, scale=18), 20, 100))
        gpa            = round(float(np.clip(rng.normal(loc=2.5, scale=0.6), 1.0, 4.0)), 2)
        weak_subject   = random.choice(KDU_IT_MODULES)
        exam_days      = int(rng.integers(1, 61))
        perf_class     = classify_performance(
            study_hours, attendance, assignment_mks, quiz_mks, gpa
        )

        records.append({
            "Study_Hours"      : study_hours,
            "Attendance_%"     : attendance,
            "Assignment_Marks" : assignment_mks,
            "Quiz_Marks"       : quiz_mks,
            "Previous_GPA"     : gpa,
            "Weak_Subject"     : weak_subject,
            "Exam_Days_Left"   : exam_days,
            "Performance_Class": perf_class,
        })

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Generate a synthetic KDU IT student dataset."
    )
    parser.add_argument("--rows", type=int, default=500,
                        help="Number of student records to generate (default: 500)")
    parser.add_argument(
        "--output", type=str,
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "kdu_student_dataset.csv"
        ),
        help="Output CSV file path"
    )
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed for reproducibility (default: 42)")
    args = parser.parse_args()

    print(f"[dataset_generator] Generating {args.rows} student profiles (seed={args.seed}) ...")
    df = generate_student_profiles(n_rows=args.rows, seed=args.seed)

    print("\nPerformance class distribution:")
    print(df["Performance_Class"].value_counts().to_string())
    print()

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"[dataset_generator] Saved {len(df)} records to {args.output}")


if __name__ == "__main__":
    main()

