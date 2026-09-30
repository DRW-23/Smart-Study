"""Test the FIXED sanitizer against actual LLM HTML output."""
import re
import html as html_lib

def sanitize_llm_output(text):
    """Fixed version - processes semantic HTML BEFORE stripping tags."""
    if not text:
        return text
    
    # Step 1: Extract task-label spans
    text = re.sub(
        r'<span[^>]*class\s*=\s*["\']task-label["\'][^>]*>(.*?)</span>\s*',
        r'\1 ',
        text,
        flags=re.IGNORECASE
    )
    
    # Step 2: Convert task-item divs to "- content" lines (BEFORE stripping </div>)
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']task-item["\'][^>]*>(.*?)</div>',
        r'\n- \1',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']task-item["\'][^>]*>(.*?)(?=<div|$)',
        r'\n- \1',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    # Step 3: Convert section-label divs
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']section-label["\'][^>]*>(.*?)</div>',
        r'\n\1\n',
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']section-label["\'][^>]*>(.*?)(?=<|$)',
        r'\n\1\n',
        text,
        flags=re.IGNORECASE
    )
    
    # Step 4: Convert remaining closing tags to newlines
    text = re.sub(r'</div>|</p>|</li>|<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    
    # Step 5: Strip remaining HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Step 6: Collapse spaces
    text = re.sub(r'[^\S\n]+', ' ', text)
    
    # Step 7: Collapse blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Step 8: Unescape entities
    text = html_lib.unescape(text)
    
    # Step 9: Ensure checkmark lines become task items
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('\u2705') and not stripped.startswith('- \u2705'):
            cleaned_lines.append(f'- {stripped}')
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    return text.strip()


# === TEST 1: Full HTML-wrapped Phase (the exact bug) ===
print("=" * 60)
print("TEST 1: Full HTML-wrapped LLM response (Phase 2/4 bug)")
print("=" * 60)

test_html = '<div class="section-label">\u2705 Action Steps</div><div class="task-item"><span class="task-label">Watch:</span>"What is an Operating System?" on YouTube</div><div class="task-item"><span class="task-label">Code:</span>Write a simple C++ program to demonstrate process creation.</div><div class="task-item"><span class="task-label">Practice:</span>Complete OOP Basics on HackerRank</div><div class="task-item"><span class="task-label">Summarise:</span>Draw a diagram comparing monolithic vs microkernel.</div><div class="task-item"><span class="task-label">Self-test:</span>Write 5 exam-style questions</div><div class="task-item">\u2705 What is the primary function of an OS?</div><div class="task-item">\u2705 How does an OS manage memory?</div>'

result = sanitize_llm_output(test_html)
print(f"OUTPUT:\n{result}")
print()

# Verify all tasks got "- " prefix
print("--- Checking task lines ---")
task_count = 0
for line in result.split('\n'):
    stripped = line.strip()
    if stripped.startswith('-'):
        task_count += 1
        print(f"  OK: {stripped[:70]}")
print(f"\nTotal tasks found: {task_count}")
assert task_count >= 7, f"FAIL: Expected 7+ tasks, got {task_count}"
print("PASS!")

# === TEST 2: Mixed plain text + HTML ===
print("\n" + "=" * 60)
print("TEST 2: Explain text in plain, tasks in HTML")
print("=" * 60)

test_mixed = """Explain: Operating systems manage resources like a traffic cop.
Key concepts: Process Management, Memory Allocation, File Systems, Security
Tasks:
<div class="section-label">\u2705 Action Steps</div><div class="task-item"><span class="task-label">Watch:</span>"OS Basics" on YouTube</div><div class="task-item">\u2705 What is a process?</div><div class="task-item">\u2705 How does scheduling work?</div>"""

result2 = sanitize_llm_output(test_mixed)
print(f"OUTPUT:\n{result2}")

# Verify explain and tasks both parsed
has_explain = 'Explain:' in result2
has_tasks = result2.count('- ') >= 3
print(f"\nHas Explain: {has_explain}, Has 3+ tasks: {has_tasks}")
assert has_explain and has_tasks, "FAIL: Missing explain or tasks"
print("PASS!")

# === TEST 3: No HTML at all (should pass through unchanged) ===
print("\n" + "=" * 60)
print("TEST 3: Plain text (no HTML)")
print("=" * 60)

test_plain = """Explain: Networks connect computers together.
Key concepts: TCP/IP, DNS, Routing, Firewalls
Tasks:
- Watch: "Networking Basics" on YouTube
- Code: Write a socket server in Python
- Self-test: Write 5 questions
\u2705 What is TCP?
\u2705 How does DNS work?"""

result3 = sanitize_llm_output(test_plain)
print(f"OUTPUT:\n{result3}")
task_count3 = sum(1 for line in result3.split('\n') if line.strip().startswith('-'))
print(f"\nTotal tasks: {task_count3}")
assert task_count3 >= 5, f"FAIL: Expected 5+ tasks, got {task_count3}"
print("PASS!")

print("\n" + "=" * 60)
print("ALL TESTS PASSED!")
print("=" * 60)
