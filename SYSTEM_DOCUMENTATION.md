# PaPrep System Breakdown & Technical Documentation
**Version:** 2.5 (Production Release)  
**Target Platform:** Pediatric Healthcare & Parenting Empowerment Web Ecosystem  
**Target Audience:** Filipino Families (Ages 0–21) & Registered Healthcare Clinics  
**Core Technologies:** Python Flask 3.0, SQLAlchemy 2.0 ORM, PostgreSQL (Supabase) / SQLite, Flask-SocketIO, Google Gemini AI (RAG), Leaflet.js, Bootstrap 5, PyOTP

---

## 1. System Overview & Core Mission
PaPrep is a specialized digital pediatric healthcare and parenting empowerment web platform tailored for Filipino families raising children from infancy through adolescence (0–21 years). It unifies clinical symptom tracking, age-adapted health checklists, evidence-based learning, interactive clinic geolocation, real-time clinical telehealth messaging, peer community discussion, and AI-assisted pediatric triage into a single secure web application.

### Key Value Pillars
* **Daily Health & Nutrition Tracking:** Systematic logging of feeding routines, developmental milestones, and age-adapted checklists.
* **Pediatric Common Ailments Tracker:** Symptom logging and triage for Fever, Cough & Colds, and Diarrhea with age-stratified emergency alerts.
* **Evidence-Based Learning Modules:** Multi-category education (Parenting, Nutrition, Safety) featuring slide decks, downloadable PDFs, and 70%-mastery quizzes.
* **Clinic Discovery & Teleservices:** Interactive Leaflet.js locator, patient-clinic registration, and bi-directional real-time chat with clinic providers.
* **Grounded Multimodal AI Pediatric Assistant:** Gemini AI integrated with the official PaPrep Red Book pediatric reference document for localized, safe guidance with hard-coded emergency interceptors.
* **Dedicated Clinic Management Portal:** Segregated staff administration suite featuring PyOTP Time-based One-Time Password (TOTP) two-factor authentication, patient roster inspection, weekly schedules, announcements, and newsletters.

---

## 2. 5-Layer Architectural Framework

| Layer | Architecture Tier | Components & Technologies | Responsibilities |
| :--- | :--- | :--- | :--- |
| **Layer 1** | **User / Actor Tier** | Parents, Clinic Staff, System Admins, PaPrep AI Bot | Role-based identity segregation, permission enforcement, and user workflows. |
| **Layer 2** | **Presentation Tier** | Jinja2 Templates, Bootstrap 5 UI, Custom CSS, Vanilla JS, Leaflet.js, Socket.IO Client | Responsive UI rendering, interactive maps, form validation, dynamic modals, and WebSocket event dispatching. |
| **Layer 3** | **Application / Logic Tier** | Flask 3.0 App Factory, 9 Blueprints (`auth`, `main`, `children`, `symptoms`, `modules`, `clinics`, `chat`, `clinic_portal`, `forum`) | Route orchestration, session management, business rule enforcement, and template context injection. |
| **Layer 4** | **Integration & Services Tier** | Google Gemini AI (File API + RAG), Flask-SocketIO (WebSocket rooms), PyOTP/QRCode, REST APIs | AI triage query processing, real-time bi-directional message broadcasting, 2FA token generation, and RESTful endpoints. |
| **Layer 5** | **Data & Persistence Tier** | SQLAlchemy ORM 2.0, PostgreSQL (Supabase Production) / SQLite (Dev Fallback), Inline Schema Migrations | Object-relational mapping across 24 database models, ACID transaction handling, and relational integrity. |

---

## 3. User Roles & Permission Matrix

| Role | Authentication Mechanism | Primary Capabilities | Access Restrictions |
| :--- | :--- | :--- | :--- |
| **Parent (User)** | Flask-Login (`User` model, PBKDF2 hash, 7-day session) | Manage child profiles; log fever, cough, and diarrhea; check daily health lists; read modules and take quizzes; search clinics; message clinics; post in forum; query AI assistant. | Restricted to parent routes; blocked from Clinic Portal and admin routes. Mandatory child creation on initial login. |
| **Clinic Staff** | Dedicated Flask Session (`clinic_account_id`) + Optional PyOTP TOTP 2FA | Manage clinic profile, coordinates, operating hours; inspect patient rosters & health logs; exchange live messages; publish newsletters & announcements; author modules. | Blocked from parent-only views. Protected by `@clinic_login_required`. |
| **System Admin** | Parent account with `is_admin=True` | System-wide module authoring, forum moderation (pin, hide, resolve reports), global announcement oversight. | Full administrative oversight over forum and global modules. |
| **PaPrep AI Bot** | Internal Automated Engine (Socket.IO + REST `/chat/bot`) | Emergency keyword interception; quick route shortcuts; grounded advice via Gemini + Red Book RAG. | Automated agent; cannot modify system state or database records without user action. |

---

## 4. Subsystems & Blueprint Breakdown

### 4.1 Authentication Subsystem (`/auth`)
* **Endpoints:** `/auth/login`, `/auth/signup`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password/<token>`, `/auth/profile`
* **Logic:** Secure user registration and login using Werkzeug PBKDF2-SHA256 password hashing. Upon login, evaluates whether the user has at least one child profile; if count is 0, forces immediate redirection to `/children/create`. Manages 30-minute SHA-256 hashed password reset tokens.

### 4.2 Main Dashboard & Notification Subsystem (`/`)
* **Endpoints:** `/`, `/dashboard`, `/api/notifications/mark-read`, `/api/recommendations`, `/api/newsletters/<id>/like`, `/api/newsletters/<id>/comment`
* **Logic:** Resolves active child context from `session['active_child_id']`. Aggregates 7-day checklist history, active clinic announcements, unread clinic messages, and age-matched educational resources and newsletters. Provides dismissal API persisting keys into `notification_reads`.

### 4.3 Child Profile Management (`/children`)
* **Endpoints:** `/children/create`, `/children/<id>/edit`, `/children/<id>/delete`, `/children/api/set-active`
* **Logic:** Maintains child profiles including DOB, gender, special needs designation, and avatar color theme. Dynamically computes `age_months`, `age_display` (e.g., '2 yr 4 mo'), and categorical `age_bracket` (`0-12m`, `1-2y`, `2-3y`, `3-5y`, `6-12y`, `13-21y`). Active child switcher instantaneously updates session state across all routes.

### 4.4 Common Ailments Tracker & Health Checklist (`/symptoms`)
* **Endpoints:** `/fever-tracker`, `/api/fever/readings`, `/cough-cold-tracker`, `/diarrhea-tracker`, `/health-checklist`
* **Logic:** Tabbed tracking for common childhood ailments with algorithmic pediatric severity assignment (emergency, high, monitor, general). Evaluates infant age thresholds: any infant under 3 months with temperature $\ge 38.0^\circ	ext{C}$ triggers an immediate **Critical Emergency Alert**. Health checklist renders age-bracketed criteria and persists checked items in JSON format.

### 4.5 Learning Modules & Quizzes (`/modules`)
* **Endpoints:** `/modules/`, `/modules/<id>`, `/modules/<id>/pdf`, `/modules/<id>/presentation`, `/modules/<id>/download`, `/modules/<id>/progress`, `/modules/<id>/quiz`, `/modules/given/<given_id>/slide/<n>`
* **Logic:** Serves structured guides across parenting, nutrition, and child safety. Supports interactive slide projection, streamed binary PDF downloads, and interactive multiple-choice quizzes with a **70% passing threshold** to mark progress as completed.

### 4.6 Clinic Locator & Patient Registration (`/clinics`)
* **Endpoints:** `/clinics/`, `/clinics/<id>`, `/clinics/<id>/register`, `/clinics/<id>/unregister`
* **Logic:** Renders interactive Leaflet.js map with clinic markers and municipal search filters. Establishes `ClinicRegistration` links between children and verified medical clinics, granting clinic staff access to review patient symptom history and enabling direct chat.

### 4.7 Real-Time Telemedicine Messaging (`/chat`)
* **Endpoints:** `/chat/upload`, `/chat/upload_reply`, `/chat/send`, `/chat/history/<clinic_id>`, `/chat/inbox`, `/chat/reply`, `/chat/bot`, WebSockets (`join`, `send_message`, `clinic_reply`, `typing`, `mark_read`, `bot_query`)
* **Logic:** Bi-directional real-time chat between parents and clinics over isolated Socket.IO rooms (`chat_{clinic_id}_{user_id}`). Supports image and document uploads (PNG, JPG, PDF) with thumbnail generation.

### 4.8 Grounded AI Pediatric Assistant (`/chat/bot`)
* **Endpoints:** POST `/chat/bot`, WebSocket event `bot_query`
* **Logic:** Multi-stage intent parsing:
  1. *Emergency Interceptor:* Deterministic hard-stop catching high-risk tokens ("emergency", "convulsion", "unconscious", "not breathing") with immediate hotline instructions.
  2. *Feature Routing:* Direct shortcut buttons jumping to specific app features (Fever Tracker, Clinic Map).
  3. *Grounded RAG:* PaPrep Red Book PDF document retrieved via Gemini File API and passed as multimodal grounding context.

### 4.9 Clinic Healthcare Staff Portal (`/clinic`)
* **Endpoints:** `/clinic/login`, `/clinic/signup`, `/clinic/signup/2fa`, `/clinic/2fa/verify`, `/clinic/2fa/setup`, `/clinic/2fa/enable`, `/clinic/2fa/disable`, `/clinic/dashboard`, `/clinic/profile`, `/clinic/patients`, `/clinic/patients/<child_id>`, `/clinic/modules`, `/clinic/announcements`, `/clinic/newsletters`
* **Logic:** Dedicated management interface for clinical providers guarded by `@clinic_login_required` and PyOTP TOTP 2FA. Controls patient rosters, health logs inspection, weekly scheduling, announcements, and newsletter broadcasts with media attachments.

### 4.10 Parent Community Forum (`/forum`)
* **Endpoints:** `/forum/`, `/forum/new`, `/forum/<id>`, `/forum/<id>/reply`, `/forum/<id>/report`, `/forum/admin/...`
* **Logic:** Peer support bulletin board categorized by topic. Supports post creation, threaded replies, pinning, content moderation flagging, and administrative review.

---

## 5. Relational Database Schema (24 Core Models)

| Table Name | Primary Key | Foreign Keys & Relationships | Purpose |
| :--- | :--- | :--- | :--- |
| `users` | `id` | Unique(`email`) | Parent credentials, profile, admin flag, relationship to `child_profiles`. |
| `clinic_accounts` | `id` | Unique(`email`) | Clinic staff credentials, TOTP secret, 2FA enabled flag. |
| `clinics` | `id` | `clinic_account_id` $	o$ `clinic_accounts.id` | Clinic profile: name, address, city, latitude, longitude, phone, hours. |
| `child_profiles` | `id` | `user_id` $	o$ `users.id` (Cascade delete) | Child demographics: name, date of birth, gender, special needs, avatar color. |
| `health_checklists` | `id` | `child_id` $	o$ `child_profiles.id` | Daily health checklists: date, checked items (JSON), completion timestamp. |
| `fever_readings` | `id` | `child_id` $	o$ `child_profiles.id` | Temperature records: value, unit, Celsius converted value, method, timestamp. |
| `respiratory_episodes`| `id` | `child_id` $	o$ `child_profiles.id` | Cough/cold records: severity, duration, wheezing, breathing difficulty. |
| `diarrhea_episodes` | `id` | `child_id` $	o$ `child_profiles.id` | Stool records: frequency per day, consistency, blood present, dehydration signs. |
| `learning_modules` | `id` | `clinic_account_id` $	o$ `clinic_accounts.id` (nullable) | Educational guides: title, category, description, content, PDF binary data. |
| `module_progress` | `id` | Unique(`user_id`, `module_id`) | Tracking module completion status, quiz score, attempts, timestamps. |
| `module_quiz_questions` | `id` | `module_id` $	o$ `learning_modules.id` | Multiple-choice quiz questions, options A-D, correct option, explanation. |
| `parent_child_resources` | `id`| `clinic_account_id` $	o$ `clinic_accounts.id` | Curated parenting external resources, links, thumbnails, target age bracket. |
| `clinic_registrations` | `id` | Unique(`clinic_id`, `user_id`) | Link table connecting registered parents/children with medical clinics. |
| `clinic_messages` | `id` | `clinic_id`, `user_id` | Chat messages: sender ('user'/'clinic'), text, attachment URL, read status. |
| `clinic_announcements`| `id` | `clinic_id` $	o$ `clinics.id` | Clinic broadcasts: title, body, active flag, expiration date. |
| `clinic_schedules` | `id` | `clinic_id` $	o$ `clinics.id` | Operating hours per day of week (0-6), open time, close time, closed flag. |
| `time_slots` | `id` | `clinic_id` $	o$ `clinics.id` | Appointment slots: date, start time, end time, total slots, booked count. |
| `newsletters` | `id` | `clinic_id` $	o$ `clinics.id` | Clinic newsletters: title, body, age targeting min/max, publication status. |
| `newsletter_media` | `id` | `newsletter_id` $	o$ `newsletters.id` | Image and media attachments associated with newsletters. |
| `newsletter_likes` | `id` | Unique(`user_id`, `newsletter_id`) | Parent likes and reaction counts on clinic newsletters. |
| `newsletter_comments` | `id` | `user_id`, `newsletter_id` | Parent comments and feedback threads on newsletters. |
| `forum_posts` | `id` | `user_id` $	o$ `users.id` | Community discussions: title, body, category, pinned/hidden flags. |
| `forum_replies` | `id` | `post_id`, `user_id` | Threaded replies to community discussions. |
| `forum_reports` | `id` | `reporter_id`, `post_id`, `reply_id` | Content moderation reports with reason, resolution status, and notes. |
| `notification_reads` | `id` | Unique(`user_id`, `notification_key`) | Dismissed notification log per parent. |

---

## 6. Algorithmic Logic Specifications

### Algorithm 1: Dual Authentication & TOTP 2FA Verification
```python
# Parent Login
if user and verify_password(user.password_hash, password):
    login_user(user, remember=True)
    if len(user.children) == 0:
        return redirect('/children/create')  # Mandatory onboarding
    return redirect('/dashboard')

# Clinic Staff Login with TOTP
if clinic_account and verify_password(clinic_account.password_hash, password):
    if clinic_account.totp_enabled:
        if not totp_code:
            session['pre_auth_clinic_id'] = clinic_account.id
            return redirect('/clinic/2fa/verify')
        totp = pyotp.TOTP(clinic_account.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            return "Invalid 2FA code", 401
    session['clinic_account_id'] = clinic_account.id
    return redirect('/clinic/dashboard')
```

### Algorithm 2: Pediatric Fever Triage & Critical Infant Interceptor
```python
def evaluate_fever_severity(age_months, temperature_celsius, duration_days):
    # Rule 1: High-risk infant under 3 months
    if age_months < 3 and temperature_celsius >= 38.0:
        return {
            "severity": "emergency",
            "badge": "CRITICAL EMERGENCY",
            "message": "Any fever in an infant under 3 months requires immediate emergency medical care.",
            "actions": ["Proceed to the nearest Emergency Room immediately", "Do not administer medications without medical consultation"]
        }
    # Rule 2: High grade fever or prolonged duration
    elif temperature_celsius >= 39.0 or duration_days >= 3:
        return {
            "severity": "high",
            "badge": "URGENT MEDICAL EVALUATION",
            "message": "High or persistent fever detected. Pediatrician assessment required.",
            "actions": ["Schedule same-day clinic consultation", "Monitor hydration and urine output"]
        }
    return {
        "severity": "monitor",
        "badge": "MONITOR CAREFULLY",
        "message": "Fever present. Offer fluids frequently and monitor temperature curve.",
        "actions": ["Keep child comfortable in light clothing", "Consult clinic if fever persists beyond 48 hours"]
    }
```

### Algorithm 3: Learning Module Assessment & 70% Mastery Engine
```python
def evaluate_module_quiz(user_id, module_id, answers):
    questions = ModuleQuizQuestion.query.filter_by(module_id=module_id).all()
    correct = sum(1 for q in questions if answers.get(str(q.id)) == q.correct)
    score = round((correct / len(questions)) * 100) if questions else 0
    passed = score >= 70
    
    progress = ModuleProgress.query.filter_by(user_id=user_id, module_id=module_id).first()
    if not progress:
        progress = ModuleProgress(user_id=user_id, module_id=module_id, quiz_attempts=1)
        db.session.add(progress)
    else:
        progress.quiz_attempts += 1
    
    progress.quiz_score = max(progress.quiz_score or 0, score)
    if passed:
        progress.status = 'completed'
        progress.completed_at = datetime.utcnow()
    db.session.commit()
    return {"score": score, "passed": passed, "attempts": progress.quiz_attempts}
```

---

## 7. Security, Session & Operational Standards
* **CSRF Protection:** Flask-WTF protects all mutating POST, PUT, and DELETE operations.
* **Cryptographic Security:** Passwords hashed with PBKDF2-SHA256 via Werkzeug.
* **Time-Based 2FA:** PyOTP HMAC-SHA1 tokens with configurable tolerance windows and QR code setup.
* **Timezone Consistency:** All child age calculations and daily health timestamps are strictly normalized to Asia/Manila (PHT) timezone.
* **Session Boundaries:** Complete isolation between parent cookie sessions (`_user_id`) and clinical staff sessions (`clinic_account_id`).
* **Attachment Constraints:** Strict filetype allowlisting (PNG, JPG, PDF) with a 50MB file size ceiling.
