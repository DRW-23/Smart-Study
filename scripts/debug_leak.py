"""Debug exactly why HTML still leaks through the sanitizer."""
import re
import html as html_lib
import sys
sys.stdout.reconfigure(encoding='utf-8')

def sanitize_llm_output(text):
    if not text:
        return text
    text = re.sub(r'<span[^>]*class\s*=\s*["\']task-label["\'][^>]*>(.*?)</span>\s*', r'\1 ', text, flags=re.IGNORECASE)
    text = re.sub(r'<div[^>]*class\s*=\s*["\']task-item["\'][^>]*>(.*?)</div>', r'\n- \1', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<div[^>]*class\s*=\s*["\']task-item["\'][^>]*>(.*?)(?=<div|$)', r'\n- \1', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'<div[^>]*class\s*=\s*["\']section-label["\'][^>]*>(.*?)</div>', r'\n\1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<div[^>]*class\s*=\s*["\']section-label["\'][^>]*>(.*?)(?=<|$)', r'\n\1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>|</p>|</li>|<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = html_lib.unescape(text)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('✅') and not stripped.startswith('- ✅'):
            cleaned_lines.append(f'- {stripped}')
        else:
            cleaned_lines.append(line)
    return '\n'.join(cleaned_lines).strip()


# =====================================================================
# TEST THE EXACT TRUNCATED HTML FROM PHASE 4 IN THE USER'S OUTPUT
# =====================================================================
print("=" * 70)
print("CASE 1: Exact Phase 4 truncated pattern (Watch: cut off at end)")
print("=" * 70)

# This is what Phase 4 looks like - the HTML is CUT OFF mid-stream
# because the LLM hit the token limit inside the HTML output
case1 = '<div class="section-label">✅ Action Steps</div><div class="task-item"><span class="task-label">Watch:<'
result1 = sanitize_llm_output(case1)
print(f"INPUT:  {repr(case1)}")
print(f"OUTPUT: {repr(result1)}")
has_html = bool(re.search(r'<[^>]+', result1))
print(f"HTML remaining: {has_html} {'❌ FAIL' if has_html else '✅ PASS'}")

print()
print("=" * 70)
print("CASE 2: Complete HTML but with escaped backslash in content")
print("=" * 70)

# Phase 2 content has \* which could break regex
case2 = '<div class="section-label">✅ Action Steps</div><div class="task-item"><span class="task-label">Watch:</span>"Programming 101" on YouTube</div><div class="task-item"><span class="task-label">Code:</span>Write a Java program using +, -, \\*, / operators.</div><div class="task-item"><span class="task-label">Self-test:</span></div><div class="task-item">✅ What is the purpose?</div>'
result2 = sanitize_llm_output(case2)
print(f"OUTPUT:\n{result2}")
has_html2 = bool(re.search(r'<[a-z]', result2, re.IGNORECASE))
print(f"\nHTML remaining: {has_html2} {'❌ FAIL' if has_html2 else '✅ PASS'}")

print()
print("=" * 70)
print("CASE 3: Truncated HTML (token limit hit mid-tag) - THE ROOT CAUSE")
print("=" * 70)

# When the LLM hits token limit, the output is cut off mid-HTML
# e.g. the closing </div> never arrives
case3 = '''Explain: A function is like a recipe.
Key concepts: Functions, Scope, Arrays, Return Values
Tasks:
<div class="section-label">✅ Action Steps</div><div class="task-item"><span class="task-label">Watch:</span>"Functions in Java" on YouTube</div><div class="task-item"><span class="task-label">Code:</span>Write a Java method that adds two numbers'''
# Note: TRUNCATED - no </div> at the end!

result3 = sanitize_llm_output(case3)
print(f"OUTPUT:\n{result3}")
has_html3 = bool(re.search(r'<[a-z]', result3, re.IGNORECASE))
print(f"\nHTML remaining: {has_html3} {'❌ FAIL' if has_html3 else '✅ PASS'}")

print()
print("=" * 70)
print("CASE 4: Nuclear fallback - strip ALL remaining < > chars")
print("=" * 70)

# What if we just aggressively strip anything that looks like a tag?
def sanitize_nuclear(text):
    """Nuclear option: after all regex, strip any remaining < > """
    text = sanitize_llm_output(text)
    # If any HTML-like pattern remains, strip it completely
    while re.search(r'<[^>]*>', text):
        text = re.sub(r'<[^>]*>', '', text)
    # Also remove any orphaned < or truncated tags like "<div..." with no >
    text = re.sub(r'<[^>]*$', '', text, flags=re.MULTILINE)
    return text.strip()

result4 = sanitize_nuclear(case1)  # Truncated tag
print(f"Nuclear on Case 1: {repr(result4)}")
has_html4 = bool(re.search(r'<', result4))
print(f"HTML remaining: {has_html4} {'❌ FAIL' if has_html4 else '✅ PASS'}")

result4b = sanitize_nuclear(case3)  # Truncated div
print(f"\nNuclear on Case 3:\n{result4b}")
has_html4b = bool(re.search(r'<', result4b))
print(f"HTML remaining: {has_html4b} {'❌ FAIL' if has_html4b else '✅ PASS'}")
