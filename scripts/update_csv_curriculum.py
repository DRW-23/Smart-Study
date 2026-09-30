import pandas as pd
import random
import os

# Define the path to your current CSV
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_path = os.path.join(BASE_DIR, "data", "student_performance_dataset.csv")

# 1. Load the existing generic dataset
df = pd.read_csv(csv_path)

# 2. Filtered list of IT-specific modules from the KDU curriculum
kdu_it_modules = [
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
    "IT41043: Database Administration"
]

# 3. Replace the generic "Weak_Subject" column with real KDU modules
df['Weak_Subject'] = [random.choice(kdu_it_modules) for _ in range(len(df))]

# 4. Save this as a NEW file so you don't lose the original
new_csv_path = os.path.join(BASE_DIR, "data", "kdu_student_dataset.csv")
df.to_csv(new_csv_path, index=False)

print(f"Success! Updated dataset saved to: {new_csv_path}")