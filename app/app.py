import streamlit as st
import ollama
from ollama import Client as OllamaClient
import sys
import os
import re
from fpdf import FPDF
import html as html_lib

# Link the guardrails file
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from scripts.guardrails import check_academic_rules


# --- POST-PROCESSING: Sanitize LLM Output ---
def sanitize_llm_output(text):
    """Strip raw HTML tags and clean up common LLM formatting issues.
    Converts block-level HTML into newlines so the line-by-line parser still works.
    
    IMPORTANT: Semantic HTML extraction (task-item, task-label, section-label)
    must happen BEFORE generic tag stripping, or the structure is lost.
    """
    if not text:
        return text
    
    # Step 0: Unescape HTML entities FIRST so encoded tags become real tags
    # that our regex patterns can catch. This prevents &lt;div&gt; from
    # surviving the stripping pass and re-appearing as <div> later.
    text = html_lib.unescape(text)
    
    # Step 1: Extract task-label spans INSIDE their parent elements first
    # <span ...task-label...>Watch:</span>text  →  Watch: text
    # Use flexible pattern: any attributes, any quoting style
    text = re.sub(
        r'<span[^>]*class\s*=\s*["\']?task-label["\']?[^>]*>(.*?)</span>\s*',
        r'\1 ',
        text,
        flags=re.IGNORECASE
    )
    
    # Step 2: Convert task-item divs to "- content" lines
    # Handle both self-closing patterns: <div ...>content</div> and unclosed
    # Flexible pattern: any attribute order, optional quotes
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']?task-item["\']?[^>]*>(.*?)</div>',
        r'\n- \1',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    # Also catch any remaining task-item divs without closing tags
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']?task-item["\']?[^>]*>(.*?)(?=<div|<p|$)',
        r'\n- \1',
        text,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    # Step 3: Convert section-label divs to their text on a new line
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']?section-label["\']?[^>]*>(.*?)</div>',
        r'\n\1\n',
        text,
        flags=re.IGNORECASE
    )
    # Catch section-label without closing tag
    text = re.sub(
        r'<div[^>]*class\s*=\s*["\']?section-label["\']?[^>]*>(.*?)(?=<|$)',
        r'\n\1\n',
        text,
        flags=re.IGNORECASE
    )
    
    # Step 4: Convert remaining block-level closing tags to newlines
    text = re.sub(r'</div>|</p>|</li>|</ul>|</ol>|</table>|</tr>|</td>|</th>|<br\s*/?>',  '\n', text, flags=re.IGNORECASE)
    
    # Step 5: Strip ALL remaining HTML tags (opening tags, etc.)
    # Loop to handle nested tags that may be revealed after outer tags are stripped
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'<[^>]+>', ' ', text)
    
    # Step 6: Collapse multiple spaces on the same line (preserve newlines)
    text = re.sub(r'[^\S\n]+', ' ', text)
    
    # Step 7: Collapse 3+ blank lines into max 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Step 8: Unescape any NEW entities that might have appeared from nested HTML
    text = html_lib.unescape(text)
    
    # Step 9: Ensure ✅-prefixed lines are treated as task items
    # Convert "✅ question text" to "- ✅ question text" if not already prefixed
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('✅') and not stripped.startswith('- ✅'):
            cleaned_lines.append(f'- {stripped}')
        else:
            cleaned_lines.append(line)
    text = '\n'.join(cleaned_lines)
    
    # Step 10: NUCLEAR FALLBACK — strip ANY surviving HTML
    # Remove any orphaned/truncated tags (e.g. '<div class=...' with no closing >)
    text = re.sub(r'<[^>]*$', '', text, flags=re.MULTILINE)  # truncated open tag at line end
    # Final loop: keep stripping until no tags remain
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r'<[^>]*>', '', text)
    # Remove any bare < that wasn't part of a valid tag
    text = re.sub(r'<', '', text)
    
    return text.strip()


def split_concepts(raw_concepts_str):
    """Split concatenated concept strings into individual items.
    Handles comma-separated, newline-separated, and run-together concepts.
    """
    if not raw_concepts_str:
        return []
    # First try comma/semicolon split
    parts = re.split(r'[,;\n]', raw_concepts_str)
    result = []
    for p in parts:
        p = p.strip().strip('-•* ')
        if not p:
            continue
        # If a part is very long (>60 chars) and has no commas, it may be
        # multiple concepts run together with capital letter boundaries
        # e.g. "OSI 7-Layer modelTCP/IP Reference ModelPhysical Layer"
        if len(p) > 50:
            # Split on boundaries where lowercase is immediately followed by uppercase
            sub_parts = re.split(r'(?<=[a-z])(?=[A-Z])', p)
            # Also split on boundaries where a closing paren/digit is followed by uppercase
            expanded = []
            for sp in sub_parts:
                expanded.extend(re.split(r'(?<=[)\d])(?=[A-Z])', sp))
            result.extend([s.strip() for s in expanded if s.strip()])
        else:
            result.append(p)
    return result


# Complete KDU IT Syllabus Dictionary
SUBJECT_SYLLABUS = {
    "IT11012: Information Technology Concepts": ["1. Evolution of IT and Hardware Basics", "2. Operating Systems and Software Classifications", "3. Introduction to Networks and the Internet", "4. IT Ethics, Privacy, and Security Fundamentals"],
    "IT11022: Fundamentals of Computer Programming": ["1. Problem Solving, Algorithms, and Flowcharts", "2. Data Types, Variables, and Basic Operators", "3. Control Structures (If/Else, Switch, Loops)", "4. Functions, Scope, and Basic Arrays"],
    "IT11042: Fundamentals of Computer Systems": ["1. Number Systems and Boolean Algebra", "2. Logic Gates and Combinational Circuits", "3. CPU Architecture and Instruction Execution Cycle", "4. Memory Hierarchy and Secondary Storage"],
    "IT12023: Object Oriented Programming": ["1. Classes, Objects, and Encapsulation", "2. Inheritance, Method Overriding, and Polymorphism", "3. Abstract Classes and Interfaces", "4. Exception Handling and File Input/Output"],
    "IT12033: Fundamentals of Database Management Systems": ["1. ER Modeling and Relational Schema Mapping", "2. SQL: DDL, DML, Joins, and Subqueries", "3. Relational Algebra and Normalization (1NF to 3NF)", "4. Database Security and Integrity Constraints"],
    "IT12042: Computer Systems Architecture": ["1. Instruction Set Architecture (ISA) & Addressing Modes", "2. Pipelining, Hazards, and CPU Performance", "3. Cache Memory Mapping and Virtual Memory", "4. Input/Output Systems and Interrupt Handling"],
    "IT12062: Computer Network Systems I": ["1. OSI 7-Layer and TCP/IP Reference Models", "2. Physical Layer: Transmission Media & Encoding", "3. Data Link Layer: Framing, Error Detection, & MAC", "4. IP Addressing, Subnetting, and Ethernet Standards"],
    "IT12072: Web Technologies": ["1. Semantic HTML5 & CSS3 Responsive Layouts", "2. JavaScript Core Syntax and DOM Manipulation", "3. Client-Server Architecture and HTTP Protocols", "4. Form Validation, Web Accessibility, and Basic UI/UX"],
    "IT21013: Rapid Application Development": ["1. RAD Principles, Agile Prototyping, and GUI Design", "2. Event-Driven Programming and Control Properties", "3. Database Connectivity (CRUD Operations)", "4. Packaging, Testing, and Application Deployment"],
    "IT21022: System Analysis and Design": ["1. Systems Development Life Cycle (SDLC) Models", "2. Requirements Engineering and Feasibility Analysis", "3. UML Modeling: Use Case, Activity, and Class Diagrams", "4. System Architecture, Testing, and Transition"],
    "IT21043: Advanced Database Management Systems": ["1. Query Processing, Evaluation, and Optimization", "2. ACID Properties, Concurrency Control, and Locking", "3. Database Recovery Protocols and Logging", "4. Distributed Databases and NoSQL Paradigms"],
    "IT22013: Data Structures and Algorithms": ["1. Linear Structures: Arrays, Linked Lists, Stacks, Queues", "2. Non-Linear Structures: Binary Search Trees and Graphs", "3. Sorting and Searching Algorithms Analysis", "4. Big-O Asymptotic Notation and Complexity"],
    "IT22022: Software Engineering": ["1. Agile/Scrum Methodologies vs Waterfall", "2. Software Requirements Specification (SRS) Documentation", "3. Architectural Design Patterns and Software Quality", "4. Verification, Validation, and Testing Strategies"],
    "IT22032: Operating Systems": ["1. OS Architecture, System Calls, and Process Control", "2. CPU Scheduling Algorithms and Concurrency Synchronization", "3. Deadlock Detection, Prevention, and Recovery", "4. Memory Management: Paging, Segmentation, and File Systems"],
    "IT31042: Mobile Computing": ["1. Mobile Architecture, Activities, and Lifecycle", "2. Intent Mechanisms, UI Layouts, and Event Handlers", "3. Local Data Persistence (SQLite/Room) and REST APIs", "4. Mobile Security, Permissions, and Deployment"],
    "IT31062: Information and Data Security": ["1. Symmetric and Asymmetric Cryptographic Algorithms", "2. Key Exchange, Digital Signatures, and Certificates", "3. Access Control Models, Authentication, and Firewalls", "4. Threat Landscapes, Vulnerability Management, and Risk"],
    "IT31093: Essentials of Artificial Intelligence": ["1. Uninformed and Heuristic Search Algorithms (A*, Minimax)", "2. Knowledge Representation, First-Order Logic, and Inference", "3. Probabilistic Reasoning and Expert Systems", "4. Foundations of Machine Learning and Neural Networks"],
    "IT32012: Distributed Systems": ["1. Architectures, Remote Procedure Calls (RPC), and Middleware", "2. Clock Synchronization and Distributed Mutual Exclusion", "3. Replication Strategies and Distributed File Systems", "4. Fault Tolerance, Consensus, and Distributed Transactions"],
    "IT32033: Cyber Security": ["1. Vulnerability Assessment and Penetration Testing Workflows", "2. Malware Analysis, Reverse Engineering, and Threat Hunting", "3. Web Application Security and OWASP Top 10 Mitigation", "4. Incident Response Lifecycle and Digital Forensics"],
    "IT32043: Cloud Computing and Virtualization": ["1. Cloud Models (IaaS, PaaS, SaaS) and Service Architecture", "2. Hypervisor Architectures, Containers, and Microservices", "3. Cloud Storage Systems, Virtual Networks, and Auto-scaling", "4. Cloud Security, Compliance, and Migration Strategies"],
    "IT32073: Machine Learning": ["1. Supervised Learning: Regression and Classification Models", "2. Unsupervised Learning: Clustering and Dimensionality Reduction", "3. Model Evaluation Metrics, Overfitting, and Cross-Validation", "4. Introduction to Deep Learning and Gradient Descent"],
    "IT41013: Data Mining and Data Warehousing": ["1. Data Warehouse Schemas (Star, Snowflake) and ETL Pipelines", "2. OLAP Operations and Multidimensional Analysis", "3. Association Rule Mining (Apriori), Decision Trees, Clustering", "4. Data Preprocessing, Cleaning, and Transformation"],
    "IT41032: Advanced Computer Network Systems II": ["1. Routing Protocols: OSPF, BGP, and Policy-Based Routing", "2. IPv6 Migration, Multicasting, and Advanced Switching", "3. Quality of Service (QoS) Mechanisms and Traffic Engineering", "4. Software Defined Networking (SDN) and Network Automation"],
    "IT41043: Database Administration": ["1. DBMS Instance Architecture, Memory, and Storage Management", "2. Security Configuration, Role-Based Access, and Auditing", "3. Backup Topologies, Point-in-Time Recovery, and Failover", "4. Performance Profiling, Index Optimization, and Tuning"]
}

# Curated Resource Links Dictionary
SUBJECT_RESOURCES = {
    "IT12062: Computer Network Systems I": {
        "youtube": "[NetworkChuck: Free CCNA Playlist](https://www.youtube.com/playlist?list=PLIhvC56v63IJVXv0GJcl9vO5Z6znCVb1P)",
        "docs": "Cisco Networking Academy",
    },
    "IT11022: Fundamentals of Computer Programming": {
        "youtube": "[FreeCodeCamp: C/C++ Course](https://www.youtube.com/@freecodecamp)",
        "docs": "W3Schools Programming Reference",
    },
    "IT12033: Fundamentals of Database Management Systems": {
        "youtube": "[Caleb Curry: Database Design](https://www.youtube.com/@CalebCurry)",
        "docs": "MySQL / PostgreSQL Official Docs",
    }
}

# --- PDF Generation Function ---
def _safe(text):
    """Remove characters that latin-1 can't encode (emojis, etc.)."""
    if not text:
        return ""
    return text.encode('latin-1', 'ignore').decode('latin-1').strip()


class StudyPlanPDF(FPDF):
    """FPDF subclass with a proper footer method so page numbers
    never collide with content."""
    def __init__(self, subject_code, total_pages_ref):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.subject_code = subject_code
        self.total_pages_ref = total_pages_ref  # list so we can mutate it later

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", 'I', 7.5)
        self.set_text_color(100, 116, 139)
        self.set_draw_color(220, 220, 220)
        self.set_line_width(0.3)
        self.line(15, self.get_y() - 1, 195, self.get_y() - 1)
        self.cell(90, 5, f"SmartStudy AI  |  KDU Academic Advisory", align='L')
        self.cell(0,  5, f"Page {self.page_no()} of {{nb}}", align='R')


def create_pdf(plan_data, subject_name):
    """
    Build a structured, styled PDF study plan from plan_data dict.
    """
    PAGE_W    = 210
    MARGIN    = 15
    CONTENT_W = PAGE_W - 2 * MARGIN
    LABEL_COL = 22   # width of task-type label column (WATCH / CODE / etc.)
    TEXT_COL  = CONTENT_W - LABEL_COL

    # ─────── COLOUR PALETTE  (R, G, B) ───────
    C_HEADER_BG   = (30,  27,  75)
    C_HEADER_TXT  = (255, 255, 255)
    C_ACCENT      = (99,  102, 241)
    C_PHASE_BG    = (241, 240, 255)
    C_PHASE_BORD  = (99,  102, 241)
    C_LABEL_TXT   = (99,  102, 241)
    C_BODY_TXT    = (30,  30,  30)
    C_TASK_BG_A   = (248, 248, 252)   # alternate row tints
    C_TASK_BG_B   = (255, 255, 255)
    C_TASK_BORD   = (220, 218, 245)
    C_CONCEPT_BG  = (224, 231, 255)
    C_CONCEPT_TXT = (55,  48,  163)
    C_GREEN       = (74,  222, 128)
    C_GREEN_BG    = (240, 253, 244)
    C_TIPS_BG     = (255, 247, 237)
    C_TIPS_BORD   = (251, 146, 60)
    C_TIPS_LBL    = (194, 65,  12)
    C_MUTED       = (100, 116, 139)
    C_RULE        = (220, 220, 220)

    code = subject_name.split(':')[0].strip()
    total_ref = [0]
    pdf = StudyPlanPDF(code, total_ref)
    pdf.alias_nb_pages()          # enables {nb} in footer
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()

    # ── helpers ──────────────────────────────────────────────────────────
    FOOTER_MARGIN = 20          # reserved space at bottom for footer
    PAGE_BOTTOM   = 297 - FOOTER_MARGIN   # usable Y limit (A4 = 297mm)

    def fc(*rgb):  pdf.set_fill_color(*rgb)
    def tc(*rgb):  pdf.set_text_color(*rgb)
    def dc(*rgb):  pdf.set_draw_color(*rgb)

    def need_page(extra_h=12):
        """Add a new page if the remaining space is less than extra_h mm."""
        if pdf.get_y() + extra_h > PAGE_BOTTOM:
            pdf.add_page()
            return True
        return False

    def section_label(text, color=C_MUTED):
        """Small uppercase grey section label."""
        pdf.set_x(MARGIN)
        tc(*color)
        pdf.set_font("Helvetica", 'B', 7)
        pdf.cell(CONTENT_W, 4.5, text, new_x="LMARGIN", new_y="NEXT")

    def h_rule(color=C_RULE, lw=0.3):
        dc(*color)
        pdf.set_line_width(lw)
        pdf.line(MARGIN, pdf.get_y(), MARGIN + CONTENT_W, pdf.get_y())
        pdf.ln(2)

    # ─────────────────────────────────────────────
    # PAGE 1 HEADER BANNER
    # ─────────────────────────────────────────────
    fc(*C_HEADER_BG)
    pdf.rect(0, 0, PAGE_W, 26, 'F')
    pdf.set_y(5)
    tc(*C_HEADER_TXT)
    pdf.set_font("Helvetica", 'B', 15)
    pdf.cell(PAGE_W, 8, _safe(f"SmartStudy AI  |  {code}"), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", '', 8.5)
    pdf.cell(PAGE_W, 6, _safe(subject_name), align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(30)
    tc(*C_BODY_TXT)

    # ─────────────────────────────────────────────
    # OVERVIEW BOX  (draw bg FIRST, write text on top)
    # ─────────────────────────────────────────────
    ov       = plan_data.get('overview', {})
    budget   = _safe(ov.get('budget', ''))
    risk     = _safe(ov.get('risk', ''))
    strategy = _safe(ov.get('strategy', ''))

    if budget or risk or strategy:
        box_top = pdf.get_y()

        # ── Draw background & left accent bar ──
        fc(*C_GREEN_BG); dc(*C_GREEN)
        pdf.set_line_width(0.5)
        # We don't know height yet; draw a generous rect and clip with white later.
        # Approach: write content, record bottom, then draw box retroactively.
        # fpdf2 doesn't support retroactive rects well, so estimate height.
        est_h = 8 + (6 if budget else 0) + (10 if risk else 0) + (16 if strategy else 0)
        pdf.rect(MARGIN, box_top, CONTENT_W, est_h, 'FD')
        # Solid green left stripe
        fc(*C_GREEN)
        pdf.rect(MARGIN, box_top, 3, est_h, 'F')

        # ── Content inside box ──
        pdf.set_xy(MARGIN + 5, box_top + 2)
        tc(*C_GREEN)
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(CONTENT_W - 5, 6, "Your Study Strategy", new_x="LMARGIN", new_y="NEXT")

        if budget:
            pdf.set_x(MARGIN + 5)
            tc(*C_MUTED); pdf.set_font("Helvetica", 'B', 7.5)
            pdf.cell(28, 5, "TIME BUDGET", new_x="RIGHT", new_y="TOP")
            tc(*C_BODY_TXT); pdf.set_font("Helvetica", '', 9)
            pdf.cell(CONTENT_W - 33, 5, budget, new_x="LMARGIN", new_y="NEXT")

        if risk:
            pdf.set_x(MARGIN + 5)
            tc(*C_MUTED); pdf.set_font("Helvetica", 'B', 7.5)
            pdf.cell(28, 5, "RISK STATUS", new_x="RIGHT", new_y="TOP")
            tc(*C_BODY_TXT); pdf.set_font("Helvetica", '', 9)
            pdf.multi_cell(CONTENT_W - 33, 5, risk,
                           new_x="LMARGIN", new_y="NEXT")

        if strategy:
            pdf.set_x(MARGIN + 5)
            tc(*C_MUTED); pdf.set_font("Helvetica", 'B', 7.5)
            pdf.cell(CONTENT_W - 5, 5, "STRATEGY", new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(MARGIN + 5)
            tc(*C_BODY_TXT); pdf.set_font("Helvetica", '', 9)
            pdf.multi_cell(CONTENT_W - 5, 5, strategy,
                           new_x="LMARGIN", new_y="NEXT")

        pdf.ln(3)

    # ─────────────────────────────────────────────
    # SECTION HEADING
    # ─────────────────────────────────────────────
    pdf.set_x(MARGIN)
    tc(*C_ACCENT)
    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(CONTENT_W, 7, "Day-by-Day Study Schedule",
             new_x="LMARGIN", new_y="NEXT")
    h_rule(C_ACCENT, 0.5)

    # ─────────────────────────────────────────────
    # PHASES
    # ─────────────────────────────────────────────
    for i, phase in enumerate(plan_data.get('phases', [])):

        # Need at least ~30mm for the phase header + first section label
        need_page(30)

        phase_top = pdf.get_y()

        # Phase header bar
        fc(*C_PHASE_BG); dc(*C_PHASE_BORD)
        pdf.set_line_width(0.35)
        pdf.rect(MARGIN, phase_top, CONTENT_W, 8.5, 'FD')
        # Left accent stripe
        fc(*C_PHASE_BORD)
        pdf.rect(MARGIN, phase_top, 3, 8.5, 'F')

        # Phase title
        pdf.set_xy(MARGIN + 5, phase_top + 1.5)
        tc(*C_LABEL_TXT); pdf.set_font("Helvetica", 'B', 9.5)
        title_str = _safe(f"Phase {i+1}:  {phase.get('name','')}")
        pdf.cell(CONTENT_W - 55, 5.5, title_str)

        # Day badge — right side
        tc(*C_MUTED); pdf.set_font("Helvetica", 'I', 8)
        day_str = _safe(phase.get('day', ''))
        pdf.cell(50, 5.5, day_str, align='R',
                 new_x="LMARGIN", new_y="NEXT")

        pdf.ln(2)

        # ── Explain ─────────────────────────────
        explain = _safe(phase.get('explain', ''))
        if explain:
            need_page(15)
            section_label("WHAT THIS TOPIC IS ABOUT")
            pdf.set_x(MARGIN)
            tc(*C_BODY_TXT); pdf.set_font("Helvetica", '', 9)
            pdf.multi_cell(CONTENT_W, 5.2, explain,
                           new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1.5)

        # ── Must Know Concepts ──────────────────
        concepts = [_safe(c) for c in phase.get('concepts', []) if c]
        if concepts:
            need_page(15)
            section_label("MUST KNOW FOR EXAM")
            tag_x = MARGIN
            tag_y = pdf.get_y()
            row_height = 6.5
            for c in concepts:
                pdf.set_font("Helvetica", 'B', 8)
                tag_w = min(pdf.get_string_width(c) + 7, CONTENT_W)
                if tag_x + tag_w > MARGIN + CONTENT_W:
                    tag_x = MARGIN
                    tag_y += row_height + 1
                # Page break check for concept tags
                if tag_y + row_height > PAGE_BOTTOM:
                    pdf.add_page()
                    tag_x = MARGIN
                    tag_y = pdf.get_y()
                fc(*C_CONCEPT_BG); dc(*C_CONCEPT_BG)
                pdf.set_line_width(0.1)
                pdf.rect(tag_x, tag_y, tag_w, row_height, 'F')
                tc(*C_CONCEPT_TXT)
                pdf.set_xy(tag_x + 2, tag_y + 1)
                pdf.cell(tag_w - 4, row_height - 2, c)
                tag_x += tag_w + 2
            pdf.set_y(tag_y + row_height + 2)

        # ── Tasks ───────────────────────────────
        tasks = phase.get('tasks', [])
        if tasks:
            section_label("ACTION STEPS")

            # Separate named tasks (Watch/Code/etc) from self-test questions
            named_tasks  = []
            self_tests   = []
            in_self_test = False

            for t in tasks:
                t_clean = _safe(t)
                if not t_clean:
                    continue
                parts = t_clean.split(':', 1)
                lbl = parts[0].strip().lower() if len(parts) == 2 else ''
                if lbl == 'self-test' or lbl == 'selftest':
                    in_self_test = True
                    # the body of this row is the self-test instruction
                    body = parts[1].strip() if len(parts) == 2 else ''
                    if body:
                        self_tests.append(('self-test', body))
                elif in_self_test:
                    # continuation self-test questions have no colon label
                    self_tests.append(('q', t_clean))
                else:
                    named_tasks.append(t_clean)

            # Draw named task rows (two-column: label | body)
            for idx, t in enumerate(named_tasks):
                parts = t.split(':', 1)
                if len(parts) == 2 and len(parts[0]) <= 14:
                    lbl  = parts[0].strip().upper()
                    body = parts[1].strip()
                else:
                    lbl  = ''
                    body = t

                pdf.set_font("Helvetica", '', 8.5)
                # Accurately estimate how many lines body needs
                char_per_line = int(TEXT_COL / (pdf.get_string_width('m') + 0.01)) or 1
                lines_needed  = max(1, (len(body) // char_per_line) + 1)
                row_h = lines_needed * 5 + 3

                # Page break: check if full row fits
                need_page(row_h + 2)
                row_y = pdf.get_y()

                bg = C_TASK_BG_A if idx % 2 == 0 else C_TASK_BG_B
                fc(*bg); dc(*C_TASK_BORD)
                pdf.set_line_width(0.15)
                pdf.rect(MARGIN, row_y, CONTENT_W, row_h, 'FD')

                # Label
                pdf.set_xy(MARGIN + 2, row_y + 1.5)
                tc(*C_LABEL_TXT); pdf.set_font("Helvetica", 'B', 7.5)
                pdf.cell(LABEL_COL - 2, row_h - 3, lbl)

                # Body
                pdf.set_xy(MARGIN + LABEL_COL, row_y + 1.5)
                tc(*C_BODY_TXT); pdf.set_font("Helvetica", '', 8.5)
                pdf.multi_cell(TEXT_COL - 2, 5, body,
                               new_x="LMARGIN", new_y="NEXT")
                pdf.set_y(row_y + row_h + 0.5)

            # Draw self-test questions as a simple bulleted list
            if self_tests:
                pdf.ln(1)
                need_page(12)
                section_label("SELF-TEST QUESTIONS")
                for kind, text in self_tests:
                    if kind == 'self-test':
                        # instruction line
                        need_page(10)
                        pdf.set_x(MARGIN)
                        tc(*C_MUTED); pdf.set_font("Helvetica", 'I', 8.5)
                        pdf.multi_cell(CONTENT_W, 5, text,
                                       new_x="LMARGIN", new_y="NEXT")
                    else:
                        # question bullet
                        fc(*C_TASK_BG_A); dc(*C_RULE)
                        pdf.set_font("Helvetica", '', 8.5)
                        char_per_line = int(CONTENT_W / (pdf.get_string_width('m') + 0.01)) or 1
                        lines_needed  = max(1, (len(text) // char_per_line) + 1)
                        row_h = lines_needed * 5 + 2
                        # Page break: check if full row fits
                        need_page(row_h + 2)
                        row_y = pdf.get_y()
                        pdf.set_line_width(0.1)
                        pdf.rect(MARGIN, row_y, CONTENT_W, row_h, 'FD')
                        pdf.set_xy(MARGIN + 3, row_y + 1)
                        tc(*C_ACCENT)
                        pdf.cell(5, 5, "Q")
                        tc(*C_BODY_TXT)
                        pdf.multi_cell(CONTENT_W - 8, 5, text,
                                       new_x="LMARGIN", new_y="NEXT")
                        pdf.set_y(row_y + row_h + 0.5)

        pdf.ln(5)

    # ─────────────────────────────────────────────
    # EXAM TIPS SECTION
    # ─────────────────────────────────────────────
    tips = plan_data.get('tips', {})
    if any([tips.get('score'), tips.get('mistake'), tips.get('night')]):
        need_page(30)
        pdf.ln(2)

        tips_top = pdf.get_y()
        fc(*C_TIPS_BG); dc(*C_TIPS_BORD)
        pdf.set_line_width(0.5)
        pdf.rect(MARGIN, tips_top, CONTENT_W, 8, 'FD')
        fc(*C_TIPS_BORD)
        pdf.rect(MARGIN, tips_top, 3, 8, 'F')

        pdf.set_xy(MARGIN + 5, tips_top + 1.5)
        tc(*C_TIPS_LBL); pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(CONTENT_W, 5, "Exam Survival Tips",
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

        for key, label_text in [('score', 'SCORE TIP'), ('mistake', 'COMMON MISTAKE')]:
            val = _safe(tips.get(key, ''))
            if val:
                need_page(15)
                pdf.set_x(MARGIN)
                tc(*C_TIPS_LBL); pdf.set_font("Helvetica", 'B', 7.5)
                pdf.cell(CONTENT_W, 5, label_text, new_x="LMARGIN", new_y="NEXT")
                pdf.set_x(MARGIN)
                tc(*C_BODY_TXT); pdf.set_font("Helvetica", '', 9)
                pdf.multi_cell(CONTENT_W, 5, val, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(1.5)

        night = tips.get('night', [])
        if night:
            need_page(12)
            pdf.set_x(MARGIN)
            tc(*C_TIPS_LBL); pdf.set_font("Helvetica", 'B', 7.5)
            pdf.cell(CONTENT_W, 5, "NIGHT BEFORE", new_x="LMARGIN", new_y="NEXT")
            tc(*C_BODY_TXT); pdf.set_font("Helvetica", '', 9)
            for n in night:
                n_clean = _safe(n)
                if n_clean:
                    need_page(10)
                    pdf.set_x(MARGIN + 3)
                    pdf.cell(6, 5, "-")
                    pdf.multi_cell(CONTENT_W - 9, 5, n_clean,
                                   new_x="LMARGIN", new_y="NEXT")

    return pdf.output()




# Streamlit Page Setup
st.set_page_config(page_title="SmartStudy AI - KDU", layout="wide", initial_sidebar_state="expanded")

# ─── GLOBAL CSS INJECTION ───
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* Root */
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
.stApp { background: #1a1a2e; }
#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: #1a1a2e !important; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #16162a !important;
    border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
}
section[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: 0.82em !important; letter-spacing: 0.8px;
    color: #e2e8f0 !important; text-transform: uppercase; font-weight: 700;
}
section[data-testid="stSidebar"] hr {
    border: none; border-top: 1px solid rgba(255, 255, 255, 0.08); margin: 16px 0;
}
section[data-testid="stSidebar"] label {
    color: #94a3b8 !important; font-weight: 500 !important;
    font-size: 0.82em !important; letter-spacing: 0.3px;
}
section[data-testid="stSidebar"] .stButton > button {
    background: #e8622c !important;
    color: #ffffff !important; border: none !important;
    border-radius: 10px !important; padding: 14px 20px !important;
    font-weight: 700 !important; font-size: 0.95em !important;
    letter-spacing: 0.5px;
    transition: all 0.2s ease !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #d4551f !important;
    transform: translateY(-1px) !important;
}

/* Progress Bar */
.stProgress > div > div > div {
    background: #2563eb !important;
    border-radius: 8px;
}

/* Download Button */
.stDownloadButton > button {
    background: #16a34a !important;
    color: #ffffff !important; border: none !important;
    border-radius: 10px !important; padding: 14px 24px !important;
    font-weight: 700 !important; font-size: 1em !important;
    transition: all 0.2s ease !important;
}
.stDownloadButton > button:hover {
    background: #15803d !important;
    transform: translateY(-1px) !important;
}

/* Chat */
[data-testid="stChatMessage"] {
    background: rgba(255, 255, 255, 0.04) !important;
    border-radius: 12px !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    padding: 16px !important; margin-bottom: 10px;
}
[data-testid="stChatInput"] > div {
    border-radius: 12px !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    background: rgba(22, 22, 42, 0.9) !important;
    transition: border-color 0.2s ease;
}
[data-testid="stChatInput"] > div:focus-within {
    border-color: #2563eb !important;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
}

/* Alerts */
[data-testid="stAlert"] [role="alert"] {
    border-radius: 10px !important;
}

/* Custom Success Banner */
.success-banner {
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-left: 4px solid #16a34a; border-radius: 10px;
    padding: 16px 22px; margin-bottom: 24px;
    display: flex; align-items: center; gap: 10px;
}
.success-banner .sb-check { font-size: 1.2em; }
.success-banner .sb-text { color: #166534; font-weight: 600; font-size: 0.95em; letter-spacing: 0.3px; }

/* Custom Warning Banner */
.warning-banner {
    background: #fef2f2;
    border: 1px solid #fecaca;
    border-left: 4px solid #dc2626; border-radius: 10px;
    padding: 16px 22px; margin-bottom: 24px;
    display: flex; align-items: center; gap: 12px;
}
.warning-banner .wb-icon { font-size: 1.4em; }
.warning-banner .wb-text { color: #991b1b; font-weight: 600; font-size: 0.95em; letter-spacing: 0.3px; line-height: 1.4; }

/* Resource Cards */
.resource-card {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 10px;
    padding: 22px;
    transition: all 0.2s ease; height: 100%;
}
.resource-card:hover {
    border-color: #2563eb;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.08);
}
.resource-card .rc-icon { font-size: 1.6em; margin-bottom: 10px; }
.resource-card .rc-title {
    color: #2563eb; font-weight: 700; font-size: 0.8em;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;
}
.resource-card .rc-body { color: #94a3b8; font-size: 0.88em; line-height: 1.6; }
.resource-card .rc-body a { color: #2563eb; text-decoration: none; }
.resource-card .rc-body a:hover { color: #1d4ed8; text-decoration: underline; }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #16162a; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.1); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }

hr { border: none; border-top: 1px solid rgba(255, 255, 255, 0.08); margin: 24px 0; }

/* Animations */
@keyframes fadeInUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
</style>
""", unsafe_allow_html=True)


# ─── HEADER ───
st.markdown("""
<div style="padding: 8px 0 24px 0;">
    <h1 style="margin: 0; line-height: 1.15; font-size: 2.4em;">
        <span style="
            color: #f1f5f9;
            font-family: 'Inter', sans-serif;
            font-weight: 800;
            letter-spacing: -0.5px;
        ">SmartStudy AI</span>
    </h1>
    <p style="
        color: #64748b; font-size: 0.95em; margin: 6px 0 0 0;
        font-weight: 500; letter-spacing: 1.5px; text-transform: uppercase;
    ">KDU Academic Advisory System</p>
</div>
""", unsafe_allow_html=True)

# Initialize Session State
if "generated_plan" not in st.session_state:
    st.session_state.generated_plan = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_subject" not in st.session_state:
    st.session_state.current_subject = ""

# --- SIDEBAR ---
st.sidebar.markdown("""
<div style="text-align: center; padding: 4px 0 18px 0;">
    <div style="
        font-size: 1.3em; font-weight: 800;
        color: #f1f5f9;
        letter-spacing: -0.3px; margin-bottom: 6px;
    ">SmartStudy AI</div>
    <div style="
        display: inline-block; background: rgba(37, 99, 235, 0.15);
        color: #60a5fa; padding: 3px 12px; border-radius: 12px;
        font-size: 0.65em; font-weight: 600; letter-spacing: 0.8px;
    ">KDU EDITION v2.0</div>
</div>
""", unsafe_allow_html=True)
st.sidebar.header("Target & Timeline")
target_subject = st.sidebar.selectbox("Select Target Subject", list(SUBJECT_SYLLABUS.keys()))
exam_days = st.sidebar.number_input("Exam Days Remaining", min_value=1, max_value=100, value=14)

st.sidebar.markdown("---")
st.sidebar.header("Study Capacity & Strategy")
daily_hours = st.sidebar.slider("Daily Study Capacity (Hours/Day)", min_value=1, max_value=10, value=3)
confidence = st.sidebar.select_slider(
    "Current Level of Understanding",
    options=["Complete Beginner", "Know the Basics", "Intermediate", "Advanced Revision"]
)
study_style = st.sidebar.selectbox(
    "Primary Study Preference",
    ["Past Paper & Exam Pattern Drills", "Theory, Concepts & Diagrams", "Hands-on Coding & Practical Labs"]
)

# --- PLAN GENERATION ---
if st.sidebar.button("Generate Personalized Study Plan", use_container_width=True):
    warnings_list = check_academic_rules(exam_days, daily_hours)
    if warnings_list:
        for w in warnings_list:
            st.markdown(f'<div class="warning-banner"><span class="wb-icon">🔥</span><span class="wb-text">{w.replace("🚨 BURNOUT ALERT: ", "")}</span></div>', unsafe_allow_html=True)

    module_syllabus = SUBJECT_SYLLABUS.get(target_subject, ["Core Concepts", "Practical Tasks"])
    total_hours = exam_days * daily_hours
    n_topics = len(module_syllabus)
    hours_per_topic = round(total_hours / max(n_topics, 1), 1)

    beginner_note = (
        "This student is a COMPLETE BEGINNER. Use a simple real-world analogy. Define every technical term. Explain why this matters in real software."
    ) if confidence == "Complete Beginner" else (
        "This student has some background. Use correct technical terms but briefly define the key ones."
    )

    def ask_model(system_msg, user_msg, tokens=800):
        """Single focused model call with extended timeout for first-load."""
        client = OllamaClient(host='http://localhost:11434', timeout=300)  # 5-min timeout
        resp = client.chat(
            model='smartstudy_ai',
            messages=[
                {'role': 'system', 'content': system_msg},
                {'role': 'user', 'content': user_msg}
            ],
            options={
                'num_predict': tokens,
                'temperature': 0.4,
                'top_p': 0.90,
                'repeat_penalty': 1.1
            }
        )
        raw_output = resp['message']['content'].strip()
        # PERMANENT FIX: Sanitize ALL model output at the source
        # This ensures HTML can NEVER reach the parser or renderer
        return sanitize_llm_output(raw_output)

    plan_data = {
        'overview': {'risk': '', 'budget': f"{daily_hours} hours/day x {exam_days} days = {total_hours} hours total", 'strategy': ''},
        'phases': [],
        'tips': {'score': '', 'mistake': '', 'night': []}
    }

    total_steps = n_topics + 2
    progress_bar = st.progress(0, text="Starting generation...")

    try:
        # STEP 1: Overview
        progress_bar.progress(1 / total_steps, text="📊 Generating strategy overview...")
        overview_raw = ask_model(
            f"""You are a KDU Academic Advisor. The student is studying {target_subject}.
They are a {confidence} student with {exam_days} days left and {daily_hours} hours/day ({total_hours} hours total).
Syllabus: {', '.join(module_syllabus)}
Write ONLY these two lines, nothing else:
Risk: [one honest, encouraging sentence about their situation]
Strategy: [2-3 sentences: which topic to start with and why, what to skip if pressed for time]""",
            "Write the overview.", tokens=300
        )
        for line in overview_raw.split('\n'):
            line = line.strip()
            ll = line.lower()
            if ll.startswith('risk:'):
                plan_data['overview']['risk'] = line.split(':', 1)[-1].strip()
            elif ll.startswith('strategy:'):
                plan_data['overview']['strategy'] = line.split(':', 1)[-1].strip()
            elif plan_data['overview']['strategy'] and not ll.startswith('risk:'):
                plan_data['overview']['strategy'] += ' ' + line

        # STEP 2: One call per topic
        # Calculate proper start/end day ranges for each topic
        # FIX: Clamp so day labels never exceed exam_days
        days_per_topic = max(1, exam_days // n_topics)
        remainder_days = exam_days % n_topics  # distribute leftover days to early phases
        current_start = 1
        for i, topic in enumerate(module_syllabus):
            # Give one extra day to the first `remainder_days` phases
            this_topic_days = days_per_topic + (1 if i < remainder_days else 0)
            end_day = min(current_start + this_topic_days - 1, exam_days)

            # FIX: Ensure start day never exceeds exam_days
            if current_start > exam_days:
                day_label = f"Day {exam_days}"
            elif current_start == end_day:
                day_label = f"Day {current_start}"
            else:
                day_label = f"Days {current_start}–{end_day}"

            step = i + 2
            progress_bar.progress(step / total_steps, text=f"📚 Generating Phase {i+1}/{n_topics}: {topic[:50]}...")

            phase_raw = ask_model(
                f"""You are a KDU Academic Advisor. Write a study section for ONE topic only.
Subject: {target_subject}
Topic to cover: {topic}
Time allocated: {day_label}, {hours_per_topic} hours total ({daily_hours} hours/day)
{beginner_note}

IMPORTANT: Output plain text ONLY. Do NOT use any HTML tags like <div>, <span>, <p>, etc. Use plain text formatting only.

Reply in EXACTLY this format, no extra text:
Explain: [Write 4-5 sentences. Open with a real-world analogy. Explain what it is and how it works. Give one concrete example. End with why this is exam-important.]
Key concepts: [List exactly 4 must-know exam sub-topics, separated by commas. Example: "Concept A, Concept B, Concept C, Concept D"]
Tasks:
- Watch: [search for a video about this topic] on YouTube
- Code: [specific coding exercise — name exact classes/methods to write]
- Practice: [specific platform and section, e.g. HackerRank OOP Basics]
- Summarise: [specific notes task, e.g. draw a diagram comparing X and Y]
- Self-test: write 5 exam-style questions on {topic}""",
                f"Write the study section for: {topic}", tokens=900
            )

            # Sanitize raw HTML from LLM output (also done inside ask_model, but belt-and-suspenders)
            phase_raw = sanitize_llm_output(phase_raw)

            phase = {
                'name': topic,
                'day': f"{day_label} — {hours_per_topic} hours",
                'explain': '',
                'concepts': [],
                'tasks': []
            }
            current_field = None
            # Lines that indicate we're in the tasks section (even without "Tasks:" header)
            task_prefixes = ('watch:', 'code:', 'practice:', 'summarise:', 'summarize:', 'self-test:', 'selftest:')
            # Lines to skip (section headers from sanitized HTML, not actual content)
            skip_patterns = ('action steps', '✅ action steps')
            
            for line in phase_raw.split('\n'):
                line = line.strip()
                if not line:
                    continue
                ll = line.lower()
                ll_stripped = ll.lstrip('-* ').strip()
                
                # Skip section header labels (from sanitized HTML)
                if ll_stripped in skip_patterns:
                    current_field = 'tasks'  # but do set the field context
                    continue
                    
                if ll.startswith('explain:'):
                    phase['explain'] = line.split(':', 1)[-1].strip()
                    current_field = 'explain'
                elif ll.startswith('key concepts:') or ll.startswith('key concept:'):
                    val = line.split(':', 1)[-1].strip()
                    # FIX: Use smart splitter that handles concatenated concepts
                    phase['concepts'] = split_concepts(val)
                    current_field = 'concepts'
                elif ll.startswith('tasks:'):
                    current_field = 'tasks'
                elif any(ll_stripped.startswith(p) for p in task_prefixes):
                    # Auto-detect task lines even without explicit "Tasks:" header
                    current_field = 'tasks'
                    task = line.lstrip('-*0123456789. ').strip()
                    task = task.lstrip('✅ ').strip()
                    if task:
                        phase['tasks'].append(task)
                elif current_field == 'explain' and not any(ll.startswith(k) for k in ['key', 'tasks', '-', '*', '✅']):
                    phase['explain'] += ' ' + line
                elif current_field == 'tasks' and (
                    line.startswith('-') or line.startswith('*') or
                    line.startswith('✅') or
                    (len(line) > 2 and line[0].isdigit())
                ):
                    task = line.lstrip('-*0123456789. ').strip()
                    # Also strip leading ✅ from self-test questions
                    task = task.lstrip('✅ ').strip()
                    if task:
                        phase['tasks'].append(task)
            plan_data['phases'].append(phase)
            current_start = end_day + 1  # next topic starts the day after this one ends

        # STEP 3: Tips
        progress_bar.progress((total_steps - 1) / total_steps, text="💡 Generating exam tips...")
        tips_raw_response = ask_model(
            f"""You are a KDU Academic Advisor. Write exam tips for {target_subject}.
Reply in EXACTLY this format:
Score tip: [2 sentences of specific exam technique for this exact subject]
Common mistake: [2 sentences on the most common error students make in this exam]
Night before:
- [specific item to re-read from lecture notes]
- [specific thing to practice or test yourself on]
- [logistics tip for exam morning]""",
            "Write the exam tips.", tokens=350
        )
        # FIX: Sanitize tips output too
        tips_raw = sanitize_llm_output(tips_raw_response)
        current_field = None
        for line in tips_raw.split('\n'):
            line = line.strip()
            if not line:
                continue
            ll = line.lower()
            if ll.startswith('score tip:'):
                plan_data['tips']['score'] = line.split(':', 1)[-1].strip()
                current_field = 'score'
            elif ll.startswith('common mistake:'):
                plan_data['tips']['mistake'] = line.split(':', 1)[-1].strip()
                current_field = 'mistake'
            elif ll.startswith('night before:') or ll.startswith('night:'):
                current_field = 'night'
            elif current_field in ('score', 'mistake') and not line.startswith('-'):
                plan_data['tips'][current_field] += ' ' + line
            elif current_field == 'night' and (line.startswith('-') or line.startswith('*')):
                plan_data['tips']['night'].append(line.lstrip('-* ').strip())

        progress_bar.progress(1.0, text="✅ Plan generated!")
        progress_bar.empty()

        st.session_state.generated_plan = plan_data
        st.session_state.current_subject = target_subject
        st.session_state.chat_history = []

    except Exception as e:
        progress_bar.empty()
        st.error(f"Generation failed: {str(e)}")

# --- HELPER: Render plan dict as cards ---
def render_plan_as_cards(plan_data, subject):
    """Render the structured plan dict as styled UI cards."""
    st.markdown("""
    <style>
    .overview-card {
        background: linear-gradient(135deg, rgba(26, 26, 46, 0.8) 0%, rgba(22, 33, 62, 0.8) 100%);
        border-left: 4px solid #4ade80;
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 24px;
        backdrop-filter: blur(16px);
        box-shadow: 0 4px 24px rgba(74, 222, 128, 0.06), 0 1px 2px rgba(0,0,0,0.2);
        border: 1px solid rgba(74, 222, 128, 0.1);
        animation: fadeInUp 0.6s ease-out;
    }
    .overview-card h3 { color: #4ade80; margin-top: 0; font-size: 1.15em; font-weight: 700; }
    .overview-card p { color: #e2e8f0; margin: 10px 0; font-size: 0.95em; line-height: 1.7; }
    .overview-card .label {
        color: #94a3b8; font-size: 0.72em; text-transform: uppercase;
        letter-spacing: 1.5px; display: block; margin-bottom: 4px; font-weight: 600;
    }
    .phase-card {
        background: linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(26, 26, 46, 0.7) 100%);
        border-left: 4px solid #818cf8;
        border-radius: 16px;
        padding: 24px 28px;
        margin-bottom: 18px;
        backdrop-filter: blur(16px);
        box-shadow: 0 4px 24px rgba(99, 102, 241, 0.06), 0 1px 2px rgba(0,0,0,0.15);
        border: 1px solid rgba(129, 140, 248, 0.1);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        animation: fadeInUp 0.5s ease-out both;
    }
    .phase-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 32px rgba(99, 102, 241, 0.12), 0 2px 4px rgba(0,0,0,0.2);
        border-color: rgba(129, 140, 248, 0.25);
    }
    .phase-card h3 { color: #a5b4fc; margin-top: 0; margin-bottom: 10px; font-size: 1.08em; font-weight: 700; }
    .phase-card .when-badge {
        display: inline-block;
        background: linear-gradient(135deg, #312e81, #3730a3);
        color: #c7d2fe;
        padding: 5px 16px;
        border-radius: 20px;
        font-size: 0.78em;
        margin-bottom: 16px;
        font-weight: 600;
        letter-spacing: 0.3px;
        border: 1px solid rgba(129, 140, 248, 0.15);
    }
    .phase-card .section-label {
        color: #64748b;
        font-size: 0.72em;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin: 16px 0 8px;
        font-weight: 600;
    }
    .phase-card .explain-text { color: #cbd5e1; font-size: 0.93em; line-height: 1.75; }
    .phase-card .concept-tag {
        display: inline-block;
        background: rgba(30, 58, 95, 0.6);
        color: #7dd3fc;
        padding: 5px 14px;
        border-radius: 20px;
        font-size: 0.8em;
        margin: 4px 5px 4px 0;
        font-weight: 500;
        border: 1px solid rgba(125, 211, 252, 0.12);
        transition: all 0.2s ease;
    }
    .phase-card .concept-tag:hover {
        background: rgba(30, 58, 95, 0.85);
        border-color: rgba(125, 211, 252, 0.3);
        box-shadow: 0 0 12px rgba(125, 211, 252, 0.1);
    }
    .phase-card .task-item {
        color: #e2e8f0;
        font-size: 0.9em;
        padding: 10px 12px;
        border-bottom: 1px solid rgba(30, 41, 59, 0.5);
        line-height: 1.6;
        border-radius: 8px;
        margin: 2px 0;
        transition: background 0.2s ease;
    }
    .phase-card .task-item:hover { background: rgba(99, 102, 241, 0.04); }
    .phase-card .task-item:last-child { border-bottom: none; }
    .phase-card .task-label {
        color: #818cf8; font-weight: 700; font-size: 0.78em;
        text-transform: uppercase; margin-right: 6px; letter-spacing: 0.5px;
    }
    .tips-card {
        background: linear-gradient(135deg, rgba(28, 25, 23, 0.8) 0%, rgba(41, 37, 36, 0.8) 100%);
        border-left: 4px solid #fb923c;
        border-radius: 16px;
        padding: 24px 28px;
        margin-top: 12px;
        backdrop-filter: blur(16px);
        box-shadow: 0 4px 24px rgba(251, 146, 60, 0.06), 0 1px 2px rgba(0,0,0,0.15);
        border: 1px solid rgba(251, 146, 60, 0.1);
        animation: fadeInUp 0.7s ease-out;
    }
    .tips-card h3 { color: #fb923c; margin-top: 0; font-size: 1.08em; font-weight: 700; }
    .tips-card p { color: #e2e8f0; font-size: 0.93em; margin: 10px 0; line-height: 1.7; }
    .tips-card ul { color: #e2e8f0; font-size: 0.9em; padding-left: 20px; margin: 6px 0; }
    .tips-card li { margin: 6px 0; line-height: 1.5; }
    </style>
    """, unsafe_allow_html=True)

    ov = plan_data.get('overview', {})
    risk_html   = f'<p><span class="label">📊 Risk Status</span>{ov.get("risk", "")}</p>' if ov.get('risk') else ''
    budget_html = f'<p><span class="label">⏳ Time Budget</span>{ov.get("budget", "")}</p>' if ov.get('budget') else ''
    strat_html  = f'<p><span class="label">🎯 Strategy</span>{ov.get("strategy", "")}</p>' if ov.get('strategy') else ''
    st.markdown(f'<div class="overview-card"><h3>📊 Your Study Strategy</h3>{risk_html}{budget_html}{strat_html}</div>', unsafe_allow_html=True)

    phases = plan_data.get('phases', [])
    if phases:
        st.markdown("### 📅 Day-by-Day Study Schedule")
        for i, phase in enumerate(phases):
            day_badge    = f'<span class="when-badge">⏱️ {phase["day"]}</span>' if phase.get('day') else ''

            # === RENDER-TIME SANITIZATION ===
            # Get raw data from stored phase
            raw_explain_str = phase.get('explain', '')
            raw_concepts = list(phase.get('concepts', []))  # copy to avoid mutating state
            raw_tasks = list(phase.get('tasks', []))
            
            # Check if explain field has embedded HTML (LLM mixed content)
            has_html_in_explain = bool(re.search(r'<\s*(div|span|p|br)\b', raw_explain_str, re.IGNORECASE))
            
            if has_html_in_explain or (not raw_tasks and '<' in raw_explain_str):
                # Re-sanitize the entire explain blob to extract structure
                full_sanitized = sanitize_llm_output(raw_explain_str)
                # Re-parse to separate explain text from tasks
                recovered_explain = []
                recovered_tasks = []
                task_prefixes = ('watch:', 'code:', 'practice:', 'summarise:', 'summarize:', 'self-test:', 'selftest:')
                skip_headers = ('action steps', '✅ action steps')
                in_tasks = False
                
                for line in full_sanitized.split('\n'):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    sl = stripped.lower().lstrip('-* ').strip()
                    
                    if sl in skip_headers:
                        in_tasks = True
                        continue
                    elif any(sl.startswith(p) for p in task_prefixes):
                        in_tasks = True
                        task = stripped.lstrip('-*0123456789. ').lstrip('✅ ').strip()
                        if task:
                            recovered_tasks.append(task)
                    elif in_tasks and (stripped.startswith('-') or stripped.startswith('✅')):
                        task = stripped.lstrip('-*0123456789. ').lstrip('✅ ').strip()
                        if task:
                            recovered_tasks.append(task)
                    elif not in_tasks:
                        recovered_explain.append(stripped)
                
                raw_explain_str = ' '.join(recovered_explain)
                if recovered_tasks:
                    raw_tasks = recovered_tasks
            
            # Final sanitize on explain text
            raw_explain = sanitize_llm_output(raw_explain_str)
            # SAFETY NET: escape any surviving HTML angle brackets in explain text
            raw_explain = raw_explain.replace('<', '&lt;').replace('>', '&gt;')
            explain_html = f'<div class="section-label">📖 What This Topic Is About</div><div class="explain-text">{raw_explain}</div>' if raw_explain else ''

            # Re-split concepts at render-time in case they were stored concatenated
            if raw_concepts:
                if len(raw_concepts) == 1 and len(raw_concepts[0]) > 50:
                    raw_concepts = split_concepts(raw_concepts[0])
                expanded = []
                for c in raw_concepts:
                    c = sanitize_llm_output(c)
                    c = c.replace('<', '&lt;').replace('>', '&gt;')
                    if len(c) > 50:
                        expanded.extend(split_concepts(c))
                    elif c:
                        expanded.append(c)
                raw_concepts = expanded
            concepts_html = ''
            if raw_concepts:
                tags = ''.join([f'<span class="concept-tag">{c}</span>' for c in raw_concepts])
                concepts_html = f'<div class="section-label">🎯 Must Know for Exam</div><div>{tags}</div>'

            # Render tasks
            tasks_html = ''
            if raw_tasks:
                items = []
                for t in raw_tasks:
                    t = sanitize_llm_output(t)
                    if not t:
                        continue
                    t = t.lstrip('✅ ').strip()
                    if not t:
                        continue
                    # SAFETY NET: escape stray HTML in task text
                    t = t.replace('<', '&lt;').replace('>', '&gt;')
                    parts = t.split(':', 1)
                    if len(parts) == 2 and len(parts[0]) <= 12:
                        items.append(f'<div class="task-item"><span class="task-label">{parts[0]}:</span>{parts[1].strip()}</div>')
                    else:
                        items.append(f'<div class="task-item">✅ {t}</div>')
                if items:
                    tasks_html = f'<div class="section-label">✅ Action Steps</div>{"".join(items)}'

            # Fallback if phase is completely empty
            if not raw_explain and not raw_concepts and not raw_tasks:
                explain_html = '<div class="explain-text" style="color:#94a3b8; font-style:italic;">⚠️ Content for this topic could not be generated. Please click "Generate Personalized Study Plan" again.</div>'

            st.markdown(f"""
            <div class="phase-card" style="animation-delay: {i * 0.08}s;">
                <h3>Phase {i+1}: {phase['name']}</h3>
                {day_badge}
                {explain_html}
                {concepts_html}
                {tasks_html}
            </div>
            """, unsafe_allow_html=True)

    tips = plan_data.get('tips', {})
    if any([tips.get('score'), tips.get('mistake'), tips.get('night')]):
        score_html   = f'<p>🏆 <strong>Score Tip:</strong> {tips["score"]}</p>' if tips.get('score') else ''
        mistake_html = f'<p>⚠️ <strong>Common Mistake:</strong> {tips["mistake"]}</p>' if tips.get('mistake') else ''
        night_items  = ''.join([f'<li>{n}</li>' for n in tips.get('night', [])])
        night_html   = f'<p>📝 <strong>Night Before:</strong><ul>{night_items}</ul></p>' if night_items else ''
        st.markdown(f'<div class="tips-card"><h3>💡 Exam Survival Tips</h3>{score_html}{mistake_html}{night_html}</div>', unsafe_allow_html=True)


# --- DISPLAY UI ---
if st.session_state.generated_plan:
    st.markdown('<div class="success-banner"><span class="sb-check">✅</span><span class="sb-text">Study Roadmap Generated Successfully!</span></div>', unsafe_allow_html=True)

    # 1. Render beautiful card UI
    render_plan_as_cards(st.session_state.generated_plan, st.session_state.current_subject)

    # 2. Display Curated Resources
    st.markdown("---")
    st.markdown('<h3 style="color: #e2e8f0; margin-bottom: 20px;">📚 Recommended Resources</h3>', unsafe_allow_html=True)
    resources = SUBJECT_RESOURCES.get(st.session_state.current_subject, {
        "youtube": "Search on YouTube: freeCodeCamp, Bro Code, CrashCourse",
        "docs": "KDU Lecture Slides & official textbooks",
    })
    module_code = st.session_state.current_subject.split(':')[0].upper()
    # Convert any markdown links to HTML for resource cards
    _yt_html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', resources['youtube'])
    _doc_html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', resources['docs'])
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="resource-card"><div class="rc-icon">🎥</div><div class="rc-title">Video Lectures</div><div class="rc-body">{_yt_html}</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="resource-card"><div class="rc-icon">📖</div><div class="rc-title">Documentation</div><div class="rc-body">{_doc_html}</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="resource-card"><div class="rc-icon">📝</div><div class="rc-title">Past Papers</div><div class="rc-body"><a href="http://library.kdu.ac.lk/" target="_blank">Search {module_code} in KDU Library</a></div></div>', unsafe_allow_html=True)

    # FIX: Resource disclaimer — LLMs may hallucinate video titles/channel names
    st.caption("⚠️ _Note: Video titles and channel names suggested in the study plan are AI-generated recommendations. "
               "Please search for similar topics on YouTube — exact titles may vary._")

    # 3. PDF Download — pass plan_data dict directly to the new structured PDF builder
    st.markdown("---")
    plan_data = st.session_state.generated_plan
    pdf_bytes = create_pdf(plan_data, st.session_state.current_subject)
    st.download_button(
        label="📥 Download Study Plan as PDF",
        data=bytes(pdf_bytes),
        file_name=f"{st.session_state.current_subject.split(':')[0]}_StudyPlan.pdf",
        mime="application/pdf",
        use_container_width=True
    )

    # 4. Interactive Chat
    st.markdown("---")
    st.subheader("💬 Ask Your KDU Advisor a Follow-up Question")
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Dynamic Chat Placeholder logic for ALL 24 KDU Modules
    chat_hints = {
        "IT11012: Information Technology Concepts": "E.g., What is the difference between system software and application software?",
        "IT11022: Fundamentals of Computer Programming": "E.g., Can you explain what a 'for loop' is with a simple example?",
        "IT11042: Fundamentals of Computer Systems": "E.g., How do I convert a decimal number to binary?",
        "IT12023: Object Oriented Programming": "E.g., What is the difference between a class and an object?",
        "IT12033: Fundamentals of Database Management Systems": "E.g., What is a Primary Key?",
        "IT12042: Computer Systems Architecture": "E.g., Can you explain the instruction execution cycle?",
        "IT12062: Computer Network Systems I": "E.g., What is the difference between TCP and UDP?",
        "IT12072: Web Technologies": "E.g., How do I link a CSS file to my HTML document?",
        "IT21013: Rapid Application Development": "E.g., What are the main phases of Rapid Application Development?",
        "IT21022: System Analysis and Design": "E.g., Can you give an example of an actor in a use case diagram?",
        "IT21043: Advanced Database Management Systems": "E.g., Explain the ACID properties in database transactions.",
        "IT22013: Data Structures and Algorithms": "E.g., What is the time complexity of a binary search?",
        "IT22022: Software Engineering": "E.g., What is the difference between Agile and Waterfall methodologies?",
        "IT22032: Operating Systems": "E.g., What causes a deadlock in an operating system?",
        "IT31042: Mobile Computing": "E.g., Can you explain the Android Activity Lifecycle?",
        "IT31062: Information and Data Security": "E.g., How does asymmetric cryptography work?",
        "IT31093: Essentials of Artificial Intelligence": "E.g., Explain how the A* search algorithm works.",
        "IT32012: Distributed Systems": "E.g., What is a Remote Procedure Call (RPC)?",
        "IT32033: Cyber Security": "E.g., Can you explain what a SQL injection vulnerability is?",
        "IT32043: Cloud Computing and Virtualization": "E.g., What is the difference between IaaS, PaaS, and SaaS?",
        "IT32073: Machine Learning": "E.g., Explain the difference between supervised and unsupervised learning.",
        "IT41013: Data Mining and Data Warehousing": "E.g., What is the difference between OLAP and OLTP?",
        "IT41032: Advanced Computer Network Systems II": "E.g., How does the OSPF routing protocol work?",
        "IT41043: Database Administration": "E.g., What are the main responsibilities of a DBA during a database recovery?"
    }
    
    # Get the specific hint, or use a default one if the subject isn't in the dictionary
    hint_text = chat_hints.get(st.session_state.current_subject, "E.g., Can you explain this concept in more detail?")
    
    user_query = st.chat_input(hint_text)
    if user_query:
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        chat_system_instruction = """You are a helpful KDU Academic Tutor.
CRITICAL RULES:
1. YOU MUST NOT output "Predicted Performance Category" or default formats.
2. ONLY answer the specific question asked by the student.
3. Be direct, conversational, and helpful."""

        # Build a text summary of the plan for chat context
        plan_data = st.session_state.generated_plan
        plan_summary = f"Subject: {st.session_state.current_subject}\n"
        for i, ph in enumerate(plan_data.get('phases', [])):
            plan_summary += f"Phase {i+1} ({ph['day']}): {ph['name']} - {ph.get('explain','')[:200]}...\n"
        advisor_chat_prompt = f"{plan_summary}\n\nStudent's Question: {user_query}"

        with st.chat_message("assistant"):
            with st.spinner("Advisor is thinking..."):
                try:
                    # Use chat-specific prompt — NOT the plan generator prompt
                    chat_client = OllamaClient(host='http://localhost:11434', timeout=300)
                    follow_up_resp = chat_client.chat(
                        model='smartstudy_ai',
                        messages=[
                            {'role': 'system', 'content': chat_system_instruction},
                            {'role': 'user', 'content': advisor_chat_prompt}
                        ],
                        options={
                            'num_predict': 800,
                            'temperature': 0.5,
                            'repeat_penalty': 1.2
                        }
                    )
                    answer = follow_up_resp['message']['content']
                    st.markdown(answer)
                    st.session_state.chat_history.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Chat error: {str(e)}")
