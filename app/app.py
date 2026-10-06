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
st.set_page_config(page_title="SmartStudy AI - KDU Academic Advisor", layout="wide", initial_sidebar_state="expanded")

# ─── GLOBAL CSS INJECTION ───
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Inter:wght@300;400;500;600;700&display=swap');

/* Root & Theme Setup */
:root {
    --bg-primary: #0c0a17;
    --bg-card: rgba(21, 18, 38, 0.7);
    --bg-card-hover: rgba(27, 23, 48, 0.85);
    --border-subtle: rgba(255, 255, 255, 0.08);
    --border-accent: rgba(99, 102, 241, 0.25);
    --accent-indigo: #6366f1;
    --accent-violet: #8b5cf6;
    --accent-cyan: #38bdf8;
    --accent-emerald: #22c55e;
    --accent-amber: #f59e0b;
    --text-primary: #f8fafc;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;
}

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

.stApp {
    background: radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
                radial-gradient(circle at 85% 85%, rgba(139, 92, 246, 0.06) 0%, transparent 40%),
                #0c0a17 !important;
    color: var(--text-primary);
}

#MainMenu, footer { visibility: hidden; }
[data-testid="stHeader"] { background: transparent !important; }

/* ─── SIDEBAR MODERNIZATION ─── */
section[data-testid="stSidebar"] {
    background: #110e22 !important;
    border-right: 1px solid var(--border-subtle) !important;
}

section[data-testid="stSidebar"] .stMarkdown h2, 
section[data-testid="stSidebar"] h2 {
    font-size: 0.80em !important;
    letter-spacing: 1.2px !important;
    color: var(--text-secondary) !important;
    text-transform: uppercase !important;
    font-weight: 700 !important;
    margin-top: 10px !important;
}

section[data-testid="stSidebar"] hr {
    border: none;
    border-top: 1px solid var(--border-subtle);
    margin: 16px 0;
}

section[data-testid="stSidebar"] label {
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.82em !important;
    letter-spacing: 0.3px;
}

/* Sidebar Primary Action Button */
section[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 12px !important;
    padding: 14px 20px !important;
    font-weight: 700 !important;
    font-size: 0.95em !important;
    letter-spacing: 0.4px;
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.35) !important;
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 26px rgba(99, 102, 241, 0.5) !important;
}

/* ─── TABS STYLING ─── */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: rgba(255, 255, 255, 0.03);
    padding: 6px;
    border-radius: 14px;
    border: 1px solid var(--border-subtle);
    margin-bottom: 24px;
}

.stTabs [data-baseweb="tab"] {
    height: 44px;
    border-radius: 10px;
    color: var(--text-secondary);
    font-weight: 600;
    font-size: 0.9em;
    padding: 8px 18px;
    border: none !important;
    background: transparent;
    transition: all 0.2s ease;
}

.stTabs [data-baseweb="tab"]:hover {
    color: #ffffff;
    background: rgba(255, 255, 255, 0.04);
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%) !important;
    color: #ffffff !important;
    box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35) !important;
}

/* ─── PROGRESS BAR ─── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #6366f1 0%, #8b5cf6 50%, #38bdf8 100%) !important;
    border-radius: 8px;
}

/* ─── DOWNLOAD BUTTON ─── */
.stDownloadButton > button {
    background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255, 255, 255, 0.15) !important;
    border-radius: 12px !important;
    padding: 14px 24px !important;
    font-weight: 700 !important;
    font-size: 0.98em !important;
    box-shadow: 0 4px 16px rgba(16, 185, 129, 0.25) !important;
    transition: all 0.25s ease !important;
}
.stDownloadButton > button:hover {
    background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 24px rgba(16, 185, 129, 0.4) !important;
}

/* ─── DARK-MODE ALERT BANNERS ─── */
.success-banner {
    background: rgba(34, 197, 94, 0.10) !important;
    border: 1px solid rgba(34, 197, 94, 0.25) !important;
    border-left: 4px solid #22c55e !important;
    border-radius: 12px;
    padding: 16px 22px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    backdrop-filter: blur(10px);
}
.success-banner .sb-check { font-size: 1.3em; }
.success-banner .sb-text { color: #86efac; font-weight: 600; font-size: 0.95em; letter-spacing: 0.3px; }

.warning-banner {
    background: rgba(239, 68, 68, 0.12) !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
    border-left: 4px solid #ef4444 !important;
    border-radius: 12px;
    padding: 16px 22px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    backdrop-filter: blur(10px);
}
.warning-banner .wb-icon { font-size: 1.3em; }
.warning-banner .wb-text { color: #fca5a5; font-weight: 600; font-size: 0.93em; line-height: 1.5; }

/* ─── KPI & METRIC SUMMARY CARDS ─── */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 14px;
    margin-bottom: 24px;
}
.metric-pill {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 14px 18px;
    backdrop-filter: blur(12px);
    transition: all 0.2s ease;
}
.metric-pill:hover {
    border-color: var(--border-accent);
    background: rgba(255, 255, 255, 0.05);
}
.metric-pill .mp-label {
    color: var(--text-muted);
    font-size: 0.72em;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    margin-bottom: 4px;
}
.metric-pill .mp-val {
    color: var(--text-primary);
    font-size: 1.05em;
    font-weight: 700;
}

/* ─── ROADMAP PROGRESS TRACKER ─── */
.progress-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 20px;
    backdrop-filter: blur(12px);
}
.progress-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
}
.progress-card-title {
    color: var(--text-primary);
    font-weight: 700;
    font-size: 0.95em;
}
.progress-card-stat {
    color: var(--accent-cyan);
    font-weight: 700;
    font-size: 0.9em;
}

/* ─── WELCOME HERO & CARDS ─── */
.welcome-hero {
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.12) 0%, rgba(139, 92, 246, 0.08) 50%, rgba(56, 189, 248, 0.04) 100%);
    border: 1px solid rgba(99, 102, 241, 0.25);
    border-radius: 20px;
    padding: 36px 36px 32px 36px;
    margin-bottom: 28px;
    backdrop-filter: blur(16px);
    box-shadow: 0 10px 40px -10px rgba(99, 102, 241, 0.15);
}
.welcome-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(99, 102, 241, 0.2);
    border: 1px solid rgba(99, 102, 241, 0.35);
    color: #a5b4fc;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.75em;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    margin-bottom: 14px;
}
.welcome-title {
    font-size: 2.1em;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #ffffff;
    margin: 0 0 10px 0;
    line-height: 1.2;
}
.welcome-desc {
    color: var(--text-secondary);
    font-size: 1.02em;
    line-height: 1.6;
    max-width: 780px;
    margin: 0;
}

.feature-box {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 24px;
    height: 100%;
    backdrop-filter: blur(14px);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.feature-box:hover {
    transform: translateY(-3px);
    border-color: var(--border-accent);
    box-shadow: 0 12px 30px -10px rgba(99, 102, 241, 0.2);
}
.feature-box .fb-icon {
    font-size: 1.8em;
    margin-bottom: 12px;
}
.feature-box .fb-title {
    color: #ffffff;
    font-size: 1.05em;
    font-weight: 700;
    margin-bottom: 8px;
}
.feature-box .fb-desc {
    color: var(--text-secondary);
    font-size: 0.88em;
    line-height: 1.6;
    margin: 0;
}

/* ─── STEP CARDS ─── */
.step-card {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 18px 20px;
    margin-bottom: 12px;
    display: flex;
    align-items: flex-start;
    gap: 16px;
}
.step-num {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: #ffffff;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 0.9em;
    flex-shrink: 0;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.35);
}
.step-content .step-title {
    color: #ffffff;
    font-weight: 700;
    font-size: 0.95em;
    margin-bottom: 4px;
}
.step-content .step-desc {
    color: var(--text-secondary);
    font-size: 0.85em;
    line-height: 1.5;
}

/* ─── ROADMAP CARDS ─── */
.overview-card {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(21, 18, 38, 0.8) 100%);
    border-left: 4px solid #10b981;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 24px;
    backdrop-filter: blur(16px);
    box-shadow: 0 4px 24px rgba(16, 185, 129, 0.06);
    border: 1px solid rgba(16, 185, 129, 0.15);
}
.overview-card h3 { color: #34d399; margin-top: 0; font-size: 1.15em; font-weight: 700; }
.overview-card p { color: #e2e8f0; margin: 10px 0; font-size: 0.95em; line-height: 1.7; }
.overview-card .label {
    color: #94a3b8; font-size: 0.72em; text-transform: uppercase;
    letter-spacing: 1.5px; display: block; margin-bottom: 4px; font-weight: 600;
}

.phase-card {
    background: linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(21, 18, 38, 0.75) 100%);
    border-left: 4px solid #818cf8;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 20px;
    backdrop-filter: blur(16px);
    box-shadow: 0 4px 24px rgba(99, 102, 241, 0.06);
    border: 1px solid rgba(129, 140, 248, 0.12);
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.phase-card:hover {
    border-color: rgba(129, 140, 248, 0.3);
    box-shadow: 0 10px 32px -10px rgba(99, 102, 241, 0.25);
}
.phase-card h3 { color: #c7d2fe; margin-top: 0; margin-bottom: 10px; font-size: 1.12em; font-weight: 700; }
.phase-card .when-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(99, 102, 241, 0.18);
    color: #a5b4fc;
    padding: 5px 16px;
    border-radius: 20px;
    font-size: 0.78em;
    margin-bottom: 16px;
    font-weight: 600;
    letter-spacing: 0.3px;
    border: 1px solid rgba(129, 140, 248, 0.2);
}
.phase-card .section-label {
    color: var(--text-secondary);
    font-size: 0.74em;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 18px 0 8px;
    font-weight: 700;
}
.phase-card .explain-text { color: #cbd5e1; font-size: 0.93em; line-height: 1.75; }
.phase-card .concept-tag {
    display: inline-block;
    background: rgba(56, 189, 248, 0.12);
    color: #7dd3fc;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.8em;
    margin: 4px 6px 4px 0;
    font-weight: 500;
    border: 1px solid rgba(125, 211, 252, 0.18);
    transition: all 0.2s ease;
}
.phase-card .concept-tag:hover {
    background: rgba(56, 189, 248, 0.22);
    border-color: rgba(125, 211, 252, 0.4);
    box-shadow: 0 0 12px rgba(125, 211, 252, 0.15);
}

.phase-card .task-item {
    color: #e2e8f0;
    font-size: 0.9em;
    padding: 10px 14px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    line-height: 1.6;
    border-radius: 8px;
    margin: 2px 0;
    background: rgba(255, 255, 255, 0.02);
    transition: background 0.2s ease;
}
.phase-card .task-item:hover { background: rgba(99, 102, 241, 0.06); }
.phase-card .task-item:last-child { border-bottom: none; }
.phase-card .task-label {
    color: #818cf8; font-weight: 700; font-size: 0.78em;
    text-transform: uppercase; margin-right: 6px; letter-spacing: 0.5px;
}

/* ─── TIPS & RESOURCE CARDS ─── */
.tips-card {
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(21, 18, 38, 0.8) 100%);
    border-left: 4px solid #f59e0b;
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 20px;
    backdrop-filter: blur(16px);
    box-shadow: 0 4px 24px rgba(245, 158, 11, 0.06);
    border: 1px solid rgba(245, 158, 11, 0.15);
}
.tips-card h3 { color: #fbbf24; margin-top: 0; font-size: 1.15em; font-weight: 700; }
.tips-card p { color: #e2e8f0; font-size: 0.93em; margin: 10px 0; line-height: 1.7; }
.tips-card ul { color: #e2e8f0; font-size: 0.9em; padding-left: 20px; margin: 8px 0; }
.tips-card li { margin: 6px 0; line-height: 1.5; }

.resource-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 22px;
    transition: all 0.25s ease;
    height: 100%;
    backdrop-filter: blur(12px);
}
.resource-card:hover {
    border-color: var(--accent-indigo);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px -6px rgba(99, 102, 241, 0.25);
}
.resource-card .rc-icon { font-size: 1.8em; margin-bottom: 12px; }
.resource-card .rc-title {
    color: #818cf8; font-weight: 700; font-size: 0.85em;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px;
}
.resource-card .rc-body { color: var(--text-secondary); font-size: 0.9em; line-height: 1.6; }
.resource-card .rc-body a { color: var(--accent-cyan); text-decoration: none; font-weight: 600; }
.resource-card .rc-body a:hover { text-decoration: underline; color: #bae6fd; }

/* ─── CHAT STYLING ─── */
[data-testid="stChatMessage"] {
    background: rgba(21, 18, 38, 0.6) !important;
    border-radius: 14px !important;
    border: 1px solid var(--border-subtle) !important;
    padding: 16px 20px !important;
    margin-bottom: 12px;
    backdrop-filter: blur(10px);
}
[data-testid="stChatInput"] > div {
    border-radius: 14px !important;
    border: 1px solid var(--border-subtle) !important;
    background: rgba(17, 14, 34, 0.9) !important;
    backdrop-filter: blur(16px);
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="stChatInput"] > div:focus-within {
    border-color: var(--accent-indigo) !important;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2) !important;
}

/* Quick prompt chips */
.chat-chip-btn > button {
    background: rgba(255, 255, 255, 0.04) !important;
    border: 1px solid var(--border-subtle) !important;
    color: var(--text-secondary) !important;
    border-radius: 20px !important;
    font-size: 0.82em !important;
    padding: 6px 14px !important;
    transition: all 0.2s ease !important;
}
.chat-chip-btn > button:hover {
    background: rgba(99, 102, 241, 0.15) !important;
    border-color: rgba(99, 102, 241, 0.4) !important;
    color: #ffffff !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0c0a17; }
::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.12); border-radius: 10px; }
::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.25); }

hr { border: none; border-top: 1px solid var(--border-subtle); margin: 24px 0; }
</style>
""", unsafe_allow_html=True)


# ─── HEADER BANNER ───
st.markdown("""
<div style="padding: 10px 0 20px 0; display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.06); margin-bottom: 24px;">
    <div>
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
            <span style="font-size: 1.8em;">🎯</span>
            <h1 style="margin: 0; line-height: 1.1; font-size: 2.2em; font-weight: 800; letter-spacing: -0.5px; color: #f8fafc;">
                SmartStudy <span style="background: linear-gradient(135deg, #818cf8 0%, #38bdf8 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">AI</span>
            </h1>
        </div>
        <p style="color: #94a3b8; font-size: 0.9em; margin: 0; font-weight: 500; letter-spacing: 0.8px;">
            KDU Academic Advisory System • BSc (Hons) Information Technology
        </p>
    </div>
    <div style="display: flex; gap: 8px;">
        <span style="background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); color: #a5b4fc; padding: 4px 12px; border-radius: 20px; font-size: 0.75em; font-weight: 700;">
            Ollama Powered
        </span>
        <span style="background: rgba(34, 197, 94, 0.12); border: 1px solid rgba(34, 197, 94, 0.3); color: #86efac; padding: 4px 12px; border-radius: 20px; font-size: 0.75em; font-weight: 700;">
            KDU v2.0
        </span>
    </div>
</div>
""", unsafe_allow_html=True)


# ─── HELPER: Semester Mapping for KDU BSc IT ───
def get_semester_for_subject(sub_key):
    code = sub_key.split(':')[0].strip().upper()
    if code.startswith('IT11'): return 'Year 1 • Semester 1'
    if code.startswith('IT12'): return 'Year 1 • Semester 2'
    if code.startswith('IT21'): return 'Year 2 • Semester 1'
    if code.startswith('IT22'): return 'Year 2 • Semester 2'
    if code.startswith('IT31'): return 'Year 3 • Semester 1'
    if code.startswith('IT32'): return 'Year 3 • Semester 2'
    if code.startswith('IT41'): return 'Year 4 • Semester 1'
    return 'Other Modules'

SEMESTERS_LIST = [
    "All Semesters (24 Modules)",
    "Year 1 • Semester 1",
    "Year 1 • Semester 2",
    "Year 2 • Semester 1",
    "Year 2 • Semester 2",
    "Year 3 • Semester 1",
    "Year 3 • Semester 2",
    "Year 4 • Semester 1"
]


# Initialize Session State
if "generated_plan" not in st.session_state:
    st.session_state.generated_plan = ""
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "current_subject" not in st.session_state:
    st.session_state.current_subject = ""
if "exam_days" not in st.session_state:
    st.session_state.exam_days = 14
if "daily_hours" not in st.session_state:
    st.session_state.daily_hours = 3
if "confidence" not in st.session_state:
    st.session_state.confidence = "Know the Basics"
if "completed_tasks" not in st.session_state:
    st.session_state.completed_tasks = set()
if "target_subject_select" not in st.session_state:
    st.session_state.target_subject_select = list(SUBJECT_SYLLABUS.keys())[0]
if "selected_semester" not in st.session_state:
    st.session_state.selected_semester = "All Semesters (24 Modules)"
if "quick_prompt" not in st.session_state:
    st.session_state.quick_prompt = ""


# --- SIDEBAR: Curriculum Navigation & Settings ---
st.sidebar.markdown("""
<div style="text-align: center; padding: 4px 0 16px 0;">
    <div style="font-size: 1.25em; font-weight: 800; color: #f1f5f9; letter-spacing: -0.3px;">
        🎓 Advisor Control Panel
    </div>
    <div style="color: #64748b; font-size: 0.78em; margin-top: 2px;">
        Configure your timeline & curriculum
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("1. Curriculum & Target")

# Semester Filter to reduce cognitive load
chosen_semester = st.sidebar.selectbox(
    "Filter by Academic Semester",
    SEMESTERS_LIST,
    index=SEMESTERS_LIST.index(st.session_state.selected_semester) if st.session_state.selected_semester in SEMESTERS_LIST else 0,
    help="Select your semester to quickly filter subjects, or view all modules."
)
st.session_state.selected_semester = chosen_semester

# Filter subject list based on chosen semester
if chosen_semester == "All Semesters (24 Modules)":
    filtered_subjects = list(SUBJECT_SYLLABUS.keys())
else:
    filtered_subjects = [s for s in SUBJECT_SYLLABUS.keys() if get_semester_for_subject(s) == chosen_semester]
    if not filtered_subjects:
        filtered_subjects = list(SUBJECT_SYLLABUS.keys())

# Ensure selected subject exists in filtered list
curr_selected = st.session_state.target_subject_select
if curr_selected not in filtered_subjects:
    curr_selected = filtered_subjects[0]

target_subject = st.sidebar.selectbox(
    "Target Subject",
    filtered_subjects,
    index=filtered_subjects.index(curr_selected),
    help="Select the specific KDU BSc IT module you are preparing for."
)
st.session_state.target_subject_select = target_subject

exam_days = st.sidebar.number_input(
    "Exam Days Remaining", 
    min_value=1, 
    max_value=100, 
    value=st.session_state.exam_days,
    help="How many calendar days remain before your examination?"
)

st.sidebar.markdown("---")
st.sidebar.header("2. Capacity & Preferences")

daily_hours = st.sidebar.slider(
    "Daily Study Capacity (Hours/Day)", 
    min_value=1, 
    max_value=10, 
    value=st.session_state.daily_hours,
    help="Realistic hours per day you can dedicate solely to this subject."
)

confidence = st.sidebar.select_slider(
    "Current Level of Understanding",
    options=["Complete Beginner", "Know the Basics", "Intermediate", "Advanced Revision"],
    value=st.session_state.confidence if st.session_state.confidence in ["Complete Beginner", "Know the Basics", "Intermediate", "Advanced Revision"] else "Know the Basics"
)

study_style = st.sidebar.selectbox(
    "Primary Study Preference",
    ["Past Paper & Exam Pattern Drills", "Theory, Concepts & Diagrams", "Hands-on Coding & Practical Labs"]
)

st.sidebar.markdown("---")


# --- PLAN GENERATION ACTION ---
generate_clicked = st.sidebar.button("✨ Generate Personalized Study Plan", use_container_width=True)

if generate_clicked:
    st.session_state.exam_days = exam_days
    st.session_state.daily_hours = daily_hours
    st.session_state.confidence = confidence
    st.session_state.completed_tasks = set()

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
        client = OllamaClient(host='http://localhost:11434', timeout=300)
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
        return sanitize_llm_output(raw_output)

    plan_data = {
        'overview': {'risk': '', 'budget': f"{daily_hours} hours/day x {exam_days} days = {total_hours} hours total", 'strategy': ''},
        'phases': [],
        'tips': {'score': '', 'mistake': '', 'night': []}
    }

    total_steps = n_topics + 2
    progress_bar = st.progress(0, text="Initializing roadmap generation...")

    try:
        # STEP 1: Overview
        progress_bar.progress(1 / total_steps, text="📊 Analyzing timeline & strategy overview...")
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

        # STEP 2: Topic breakdown
        days_per_topic = max(1, exam_days // n_topics)
        remainder_days = exam_days % n_topics
        current_start = 1
        for i, topic in enumerate(module_syllabus):
            this_topic_days = days_per_topic + (1 if i < remainder_days else 0)
            end_day = min(current_start + this_topic_days - 1, exam_days)

            if current_start > exam_days:
                day_label = f"Day {exam_days}"
            elif current_start == end_day:
                day_label = f"Day {current_start}"
            else:
                day_label = f"Days {current_start}–{end_day}"

            step = i + 2
            progress_bar.progress(step / total_steps, text=f"📚 Synthesizing Phase {i+1}/{n_topics}: {topic[:45]}...")

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

            phase_raw = sanitize_llm_output(phase_raw)

            phase = {
                'name': topic,
                'day': f"{day_label} — {hours_per_topic} hours",
                'explain': '',
                'concepts': [],
                'tasks': []
            }
            current_field = None
            task_prefixes = ('watch:', 'code:', 'practice:', 'summarise:', 'summarize:', 'self-test:', 'selftest:')
            skip_patterns = ('action steps', '✅ action steps')

            for line in phase_raw.split('\n'):
                line = line.strip()
                if not line:
                    continue
                ll = line.lower()
                ll_stripped = ll.lstrip('-* ').strip()

                if ll_stripped in skip_patterns:
                    current_field = 'tasks'
                    continue

                if ll.startswith('explain:'):
                    phase['explain'] = line.split(':', 1)[-1].strip()
                    current_field = 'explain'
                elif ll.startswith('key concepts:') or ll.startswith('key concept:'):
                    val = line.split(':', 1)[-1].strip()
                    phase['concepts'] = split_concepts(val)
                    current_field = 'concepts'
                elif ll.startswith('tasks:'):
                    current_field = 'tasks'
                elif any(ll_stripped.startswith(p) for p in task_prefixes):
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
                    task = task.lstrip('✅ ').strip()
                    if task:
                        phase['tasks'].append(task)
            plan_data['phases'].append(phase)
            current_start = end_day + 1

        # STEP 3: Tips
        progress_bar.progress((total_steps - 1) / total_steps, text="💡 Compiling KDU exam survival techniques...")
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

        progress_bar.progress(1.0, text="✅ Roadmap generated successfully!")
        progress_bar.empty()

        st.session_state.generated_plan = plan_data
        st.session_state.current_subject = target_subject
        st.session_state.chat_history = []
        st.rerun()

    except Exception as e:
        progress_bar.empty()
        st.error(f"Generation failed: {str(e)}")


# ─── MAIN CANVAS RENDERING ───
if st.session_state.generated_plan:
    # ── STATE 1: PLAN GENERATED (TABBED DASHBOARD) ──
    st.markdown('<div class="success-banner"><span class="sb-check">🎉</span><span class="sb-text">Personalized Study Roadmap Generated Successfully!</span></div>', unsafe_allow_html=True)

    # Metric KPI Highlights
    ov = st.session_state.generated_plan.get('overview', {})
    total_study_hours = st.session_state.exam_days * st.session_state.daily_hours
    
    st.markdown(f"""
    <div class="metrics-grid">
        <div class="metric-pill">
            <div class="mp-label">Target Module</div>
            <div class="mp-val">{st.session_state.current_subject.split(':')[0]}</div>
        </div>
        <div class="metric-pill">
            <div class="mp-label">Exam Timeline</div>
            <div class="mp-val">⏳ {st.session_state.exam_days} Days Left</div>
        </div>
        <div class="metric-pill">
            <div class="mp-label">Time Budget</div>
            <div class="mp-val">⏱️ {st.session_state.daily_hours}h/day ({total_study_hours}h total)</div>
        </div>
        <div class="metric-pill">
            <div class="mp-label">Target Readiness</div>
            <div class="mp-val">📈 {st.session_state.confidence}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Four Organized Tabs
    tab_roadmap, tab_tips, tab_resources, tab_advisor = st.tabs([
        "📅 Study Roadmap & Tasks",
        "💡 Exam Strategy & Tips",
        "📚 Curated Resources & Past Papers",
        "💬 Ask Academic Advisor"
    ])

    # ── TAB 1: ROADMAP & TASKS ──
    with tab_roadmap:
        # Overview Card
        risk_html   = f'<p><span class="label">📊 Academic Situation Assessment</span>{ov.get("risk", "")}</p>' if ov.get('risk') else ''
        budget_html = f'<p><span class="label">⏳ Total Allocation</span>{ov.get("budget", "")}</p>' if ov.get('budget') else ''
        strat_html  = f'<p><span class="label">🎯 Recommended Strategy</span>{ov.get("strategy", "")}</p>' if ov.get('strategy') else ''
        st.markdown(f'<div class="overview-card"><h3>🎯 Academic Strategy Overview</h3>{risk_html}{budget_html}{strat_html}</div>', unsafe_allow_html=True)

        phases = st.session_state.generated_plan.get('phases', [])
        
        # Calculate task completion stats
        all_task_ids = []
        for p_idx, p in enumerate(phases):
            for t_idx, _ in enumerate(p.get('tasks', [])):
                all_task_ids.append(f"task_{p_idx}_{t_idx}")
        
        total_tasks_count = len(all_task_ids)
        completed_count = len([tid for tid in all_task_ids if tid in st.session_state.completed_tasks])
        completion_pct = int((completed_count / max(total_tasks_count, 1)) * 100)

        # Interactive Progress Banner
        st.markdown(f"""
        <div class="progress-card">
            <div class="progress-card-header">
                <span class="progress-card-title">🏆 Your Roadmap Completion</span>
                <span class="progress-card-stat">{completed_count} of {total_tasks_count} Action Steps Completed ({completion_pct}%)</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(completion_pct / 100.0)
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Render Phases
        for i, phase in enumerate(phases):
            day_badge = f'<span class="when-badge">⏱️ {phase["day"]}</span>' if phase.get('day') else ''

            # Sanitization of explain
            raw_explain_str = phase.get('explain', '')
            raw_explain = sanitize_llm_output(raw_explain_str).replace('<', '&lt;').replace('>', '&gt;')
            explain_html = f'<div class="section-label">📖 What This Topic Is About</div><div class="explain-text">{raw_explain}</div>' if raw_explain else ''

            # Concepts
            raw_concepts = phase.get('concepts', [])
            concepts_html = ''
            if raw_concepts:
                tags = ''.join([f'<span class="concept-tag">{sanitize_llm_output(c).replace("<", "&lt;").replace(">", "&gt;")}</span>' for c in raw_concepts if c])
                concepts_html = f'<div class="section-label">🎯 Must Know for Exam</div><div>{tags}</div>'

            # Phase Container
            st.markdown(f"""
            <div class="phase-card">
                <h3>Phase {i+1}: {phase['name']}</h3>
                {day_badge}
                {explain_html}
                {concepts_html}
                <div class="section-label" style="margin-top: 20px;">✅ Action Steps (Check off as you complete)</div>
            </div>
            """, unsafe_allow_html=True)

            # Interactive Checkbox Tasks inside phase
            tasks = phase.get('tasks', [])
            if tasks:
                task_cols = st.columns(1)
                for t_idx, t in enumerate(tasks):
                    clean_t = sanitize_llm_output(t).lstrip('✅ ').strip()
                    task_key = f"chk_{i}_{t_idx}"
                    task_id = f"task_{i}_{t_idx}"
                    
                    is_done = st.checkbox(
                        clean_t, 
                        key=task_key, 
                        value=(task_id in st.session_state.completed_tasks)
                    )
                    if is_done:
                        st.session_state.completed_tasks.add(task_id)
                    else:
                        st.session_state.completed_tasks.discard(task_id)

    # ── TAB 2: EXAM STRATEGY & TIPS ──
    with tab_tips:
        tips = st.session_state.generated_plan.get('tips', {})
        if any([tips.get('score'), tips.get('mistake'), tips.get('night')]):
            score_html   = f'<p>🏆 <strong>High-Scoring Technique:</strong> {tips["score"]}</p>' if tips.get('score') else ''
            mistake_html = f'<p>⚠️ <strong>Most Frequent Student Mistake:</strong> {tips["mistake"]}</p>' if tips.get('mistake') else ''
            night_items  = ''.join([f'<li>{n}</li>' for n in tips.get('night', [])])
            night_html   = f'<p>📝 <strong>Night Before Preparation:</strong><ul>{night_items}</ul></p>' if night_items else ''
            st.markdown(f'<div class="tips-card"><h3>💡 KDU Exam Survival Guide</h3>{score_html}{mistake_html}{night_html}</div>', unsafe_allow_html=True)
        else:
            st.info("No specific exam tips were generated for this run.")

    # ── TAB 3: RESOURCES & PAST PAPERS ──
    with tab_resources:
        st.markdown('<h3 style="color: #f8fafc; margin-bottom: 8px;">📚 Curated References & Library Resources</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: #94a3b8; font-size: 0.9em; margin-bottom: 20px;">Direct access to lecture materials, recommended video series, and KDU past paper archives.</p>', unsafe_allow_html=True)

        resources = SUBJECT_RESOURCES.get(st.session_state.current_subject, {
            "youtube": "Search on YouTube: freeCodeCamp, Bro Code, CrashCourse",
            "docs": "KDU Lecture Slides & official textbooks",
        })
        module_code = st.session_state.current_subject.split(':')[0].upper()
        _yt_html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', resources['youtube'])
        _doc_html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" target="_blank">\1</a>', resources['docs'])

        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f'<div class="resource-card"><div class="rc-icon">🎥</div><div class="rc-title">Video Lectures</div><div class="rc-body">{_yt_html}</div></div>', unsafe_allow_html=True)
        with col2:
            st.markdown(f'<div class="resource-card"><div class="rc-icon">📖</div><div class="rc-title">Reference Docs</div><div class="rc-body">{_doc_html}</div></div>', unsafe_allow_html=True)
        with col3:
            st.markdown(f'<div class="resource-card"><div class="rc-icon">📝</div><div class="rc-title">KDU Past Papers</div><div class="rc-body"><a href="http://library.kdu.ac.lk/" target="_blank">Search {module_code} in KDU Library ↗</a></div></div>', unsafe_allow_html=True)

        st.caption("⚠️ _Note: Video titles suggested in the study plan are AI-generated recommendations. Search for matching topics on YouTube._")

        st.markdown("---")
        st.markdown('<h4 style="color: #f8fafc; margin-bottom: 12px;">📥 Export Study Kit</h4>', unsafe_allow_html=True)
        plan_data = st.session_state.generated_plan
        pdf_bytes = create_pdf(plan_data, st.session_state.current_subject)
        st.download_button(
            label="📄 Download Complete Study Plan (PDF)",
            data=bytes(pdf_bytes),
            file_name=f"{st.session_state.current_subject.split(':')[0]}_StudyPlan.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    # ── TAB 4: ASK ACADEMIC ADVISOR ──
    with tab_advisor:
        st.markdown('<h3 style="color: #f8fafc; margin-bottom: 6px;">💬 Ask Your KDU Academic Advisor</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: #94a3b8; font-size: 0.9em; margin-bottom: 16px;">Have questions about the topics or need practical examples? Ask below or pick a suggested prompt.</p>', unsafe_allow_html=True)

        # Quick Suggested Prompts
        st.markdown("<div style='color: #64748b; font-size: 0.78em; font-weight: 700; text-transform: uppercase; margin-bottom: 8px;'>💡 Quick Prompts</div>", unsafe_allow_html=True)
        qp1, qp2, qp3, qp4 = st.columns(4)
        
        selected_prompt = None
        with qp1:
            if st.button("🔍 Explain in simpler terms", key="qp_simple", use_container_width=True):
                selected_prompt = f"Can you explain the core concepts of {st.session_state.current_subject} in simpler terms with real-world analogies?"
        with qp2:
            if st.button("📝 5-Question Practice Quiz", key="qp_quiz", use_container_width=True):
                selected_prompt = f"Give me a 5-question exam-style practice quiz for {st.session_state.current_subject} with answers."
        with qp3:
            if st.button("💻 Practical Code / Lab Example", key="qp_code", use_container_width=True):
                selected_prompt = f"Provide a practical code snippet or implementation example relevant to {st.session_state.current_subject}."
        with qp4:
            if st.button("⚠️ Common Exam Traps", key="qp_traps", use_container_width=True):
                selected_prompt = f"What are the most dangerous exam traps and tricky questions examiners set for {st.session_state.current_subject}?"

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

        # Render existing messages
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

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
        hint_text = chat_hints.get(st.session_state.current_subject, "Ask any academic or exam question...")

        user_query = st.chat_input(hint_text)
        prompt_to_run = selected_prompt or user_query

        if prompt_to_run:
            st.session_state.chat_history.append({"role": "user", "content": prompt_to_run})
            with st.chat_message("user"):
                st.markdown(prompt_to_run)

            chat_system_instruction = """You are a helpful KDU Academic Tutor.
CRITICAL RULES:
1. YOU MUST NOT output "Predicted Performance Category" or default formats.
2. ONLY answer the specific question asked by the student.
3. Be direct, conversational, and helpful."""

            plan_summary = f"Subject: {st.session_state.current_subject}\n"
            for i, ph in enumerate(st.session_state.generated_plan.get('phases', [])):
                plan_summary += f"Phase {i+1} ({ph['day']}): {ph['name']} - {ph.get('explain','')[:200]}...\n"
            advisor_chat_prompt = f"{plan_summary}\n\nStudent's Question: {prompt_to_run}"

            with st.chat_message("assistant"):
                with st.spinner("Advisor is preparing a detailed response..."):
                    try:
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

else:
    # ── STATE 2: EMPTY STATE (WELCOME & GETTING STARTED DASHBOARD) ──
    st.markdown("""
    <div class="welcome-hero">
        <div class="welcome-badge">✨ KDU Academic Advisory AI v2.0</div>
        <h2 class="welcome-title">Your AI-Powered Exam Preparation Partner</h2>
        <p class="welcome-desc">
            Designed specifically for General Sir John Kotelawala Defence University (KDU) BSc (Hons) IT students.
            Generate customized day-by-day study roadmaps, pinpoint high-yield exam concepts, and prepare strategically for your semester finals.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 3 Key Feature Highlights
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        st.markdown("""
        <div class="feature-box">
            <div class="fb-icon">🎓</div>
            <div class="fb-title">24 KDU IT Modules</div>
            <p class="fb-desc">
                Complete official syllabus coverage spanning Year 1 to Year 4, including Algorithms, Networking, Databases, AI, and Software Engineering.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with fc2:
        st.markdown("""
        <div class="feature-box">
            <div class="fb-icon">⏱️</div>
            <div class="fb-title">Adaptive Timeline</div>
            <p class="fb-desc">
                Custom time-budgeting that balances theory, coding labs, and self-testing across your exact days remaining and daily hours.
            </p>
        </div>
        """, unsafe_allow_html=True)
    with fc3:
        st.markdown("""
        <div class="feature-box">
            <div class="fb-icon">📑</div>
            <div class="fb-title">Comprehensive Study Pack</div>
            <p class="fb-desc">
                Download printable PDF roadmaps, review common exam traps, and chat live with an AI tutor fine-tuned for KDU coursework.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)

    # Visual 3-Step Guide & Popular Modules Grid
    col_steps, col_popular = st.columns([1, 1], gap="large")

    with col_steps:
        st.markdown('<h3 style="color: #f8fafc; font-size: 1.2em; font-weight: 700; margin-bottom: 14px;">🚀 How to Get Started</h3>', unsafe_allow_html=True)
        st.markdown("""
        <div class="step-card">
            <div class="step-num">1</div>
            <div class="step-content">
                <div class="step-title">Select Semester & Module</div>
                <div class="step-desc">Use the sidebar filters to pick your exact course code (e.g. IT12023 OOP or IT22013 DSA).</div>
            </div>
        </div>
        <div class="step-card">
            <div class="step-num">2</div>
            <div class="step-content">
                <div class="step-title">Set Your Study Capacity</div>
                <div class="step-desc">Specify days left and daily hours. The academic guardrail will ensure your schedule avoids burnout.</div>
            </div>
        </div>
        <div class="step-card">
            <div class="step-num">3</div>
            <div class="step-content">
                <div class="step-title">Generate & Track</div>
                <div class="step-desc">Click "Generate Study Plan" to receive day-by-day action steps, must-know concepts, and past paper links.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_popular:
        st.markdown('<h3 style="color: #f8fafc; font-size: 1.2em; font-weight: 700; margin-bottom: 14px;">⚡ Quick-Select High-Yield Modules</h3>', unsafe_allow_html=True)
        st.markdown('<p style="color: #94a3b8; font-size: 0.85em; margin-bottom: 12px;">Click a card below to quickly set your target module:</p>', unsafe_allow_html=True)
        
        pop1, pop2 = st.columns(2)
        with pop1:
            if st.button("💻 IT12023\nOOP", use_container_width=True):
                st.session_state.selected_semester = "Year 1 • Semester 2"
                st.session_state.target_subject_select = "IT12023: Object Oriented Programming"
                st.rerun()
            if st.button("🌐 IT12062\nNetworks I", use_container_width=True):
                st.session_state.selected_semester = "Year 1 • Semester 2"
                st.session_state.target_subject_select = "IT12062: Computer Network Systems I"
                st.rerun()
        with pop2:
            if st.button("🌲 IT22013\nDSA", use_container_width=True):
                st.session_state.selected_semester = "Year 2 • Semester 2"
                st.session_state.target_subject_select = "IT22013: Data Structures and Algorithms"
                st.rerun()
            if st.button("⚙️ IT22032\nOperating Systems", use_container_width=True):
                st.session_state.selected_semester = "Year 2 • Semester 2"
                st.session_state.target_subject_select = "IT22032: Operating Systems"
                st.rerun()

        st.markdown("""
        <div style="background: rgba(99, 102, 241, 0.08); border: 1px dashed rgba(99, 102, 241, 0.3); border-radius: 12px; padding: 14px; margin-top: 14px;">
            <span style="color: #a5b4fc; font-weight: 600; font-size: 0.82em;">💡 Pro Tip:</span>
            <span style="color: #cbd5e1; font-size: 0.82em;"> Once generated, you can download a full printable PDF study kit or ask the AI Tutor questions about any difficult topic.</span>
        </div>
        """, unsafe_allow_html=True)

