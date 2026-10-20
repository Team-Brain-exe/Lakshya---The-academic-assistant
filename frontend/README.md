# Lakshya Campus Compass

Design a complete, high-fidelity, multi-page desktop web application UI in Figma for **LAKSHYA — The Academic Assistant**, a smart academic platform for college students and faculty.

## 1. VISUAL DIRECTION

Use the attached reference images as the primary visual inspiration. Blend the aesthetic of a vintage luxury social media profile with a retro editorial scrapbook and modern Gen Z digital magazine.

The design should feel artistic, nostalgic, feminine, warm, curated, and distinctive, like a beautifully designed Pinterest moodboard turned into a functional academic web application.

**Colour palette:**
- Deep wine burgundy: #78172D
- Dark oxblood: #4D0715
- Warm beige: #E7D6B5
- Soft ivory: #F8F3E5
- Muted dusty blue: #A9BED0
- Taupe background: #A6947B
- Dark espresso text: #35251F

Use burgundy for navigation, buttons, important cards, badges, and section backgrounds. Use ivory and beige for primary content surfaces. Introduce dusty blue through striped backgrounds, secondary cards, and subtle decorative elements.

## 2. DESIGN LANGUAGE

Incorporate these elements throughout the interface:
- Vintage editorial magazine layouts and sophisticated typography.
- Burgundy and cream alternating panels.
- Subtle vertical blue-and-cream striped backgrounds.
- Torn-paper edges separating major sections.
- Scrapbook-inspired paper cards, pinned notes, postage-stamp shapes, and rounded image frames.
- Fine burgundy outlines, delicate borders, soft shadows, and layered surfaces.
- Elegant serif headings paired with clean sans-serif body text.
- Small decorative stars, paperclips, subtle labels, and vintage-inspired icons.
- Rounded pill buttons, status chips, and compact navigation elements.
- Generous whitespace and carefully aligned layouts.

Use elegant serif typography similar to Playfair Display or Cormorant Garamond for large headings, paired with Inter or DM Sans for interface text. Use a subtle monospace font for technical metadata, USNs, timestamps, and academic statistics.

The result must look intentionally art-directed, not like a generic SaaS dashboard or a default AI-generated admin template.

## 3. APPLICATION SHELL

Create a consistent desktop-first application layout with a refined left sidebar, top navigation bar, central workspace, and contextual floating assistant button.

**Sidebar:**
- LAKSHYA wordmark with a small vintage star or academic emblem.
- Role-specific navigation with elegant line icons.
- Clear active-page state using burgundy backgrounds and ivory text.
- Small section labels and thin separators.
- A compact profile card at the bottom.

**Top navigation:**
- Current subject selector.
- Semester or module context where relevant.
- Faculty or Student role badge.
- User name or USN.
- Notification icon and logout option.

**Assistant access:**
- A floating burgundy “Ask Lakshya” button.
- Clicking it opens a slide-in assistant panel from the right.
- Style the panel like an editorial paper notebook with chat bubbles, suggested prompts, and subtle decorative details.

Use the same design system across all screens, but vary the composition of cards and sections so every page does not look identical.

## 4. CREATE THESE SCREENS

### A. LOGIN PAGE
Create a visually striking split-screen login page.

One side features a burgundy-and-ivory striped editorial composition, the LAKSHYA wordmark, a sophisticated serif headline reading “Your academic journey, thoughtfully organised.” and small scrapbook-inspired academic illustrations.

The other side contains a clean cream login card with Student and Faculty tabs.

Student fields: USN and PIN.

Faculty fields: email or username and password.

Include a burgundy Login button, form validation states, error messages, and a subtle footer. Make the first impression memorable and premium.

### B. FACULTY DASHBOARD
Create an editorial dashboard with a warm beige background, cream content cards, burgundy headings, and a clear visual hierarchy.

Include:
- Personalised greeting and subject selector.
- Four statistic cards: Modules Uploaded, Questions Awaiting Review, Published Quizzes, and Class CO Attainment.
- A Weak Course Outcomes section with burgundy warning accents.
- An upcoming events list.
- Prominent shortcuts for Upload Slides, Review Questions, and Create Quiz.
- A clean chart showing course outcome attainment.
- Recent activity and upcoming quiz deadlines.

Make the dashboard look like a beautifully organised academic journal rather than a conventional corporate analytics dashboard.

### C. MODULE UPLOAD AND CO COVERAGE
Design a slide-upload workspace with a large drag-and-drop upload area styled like a cream paper sheet with a fine burgundy border.

Include:
- PPT file upload.
- Module number and module title fields.
- Upload and processing progress.
- Module list with Processing, Done, and Failed status chips.
- Slide chunk count.
- Course Outcome coverage visualisation using horizontal bars.
- Clear warning cards for course outcomes with zero mapped slide chunks.
- A module detail view displaying slide numbers, text previews, and CO tags.

Use subtle torn-paper separators and restrained scrapbook details without compromising usability.

### D. QUESTION REVIEW
Create a question moderation workspace with a clear, scannable list of AI-generated and faculty-created questions.

Include:
- Filters for module, CO, status, source, and difficulty.
- Summary counters for Draft, Approved, and Rejected questions.
- Question cards containing the question, four answer options, correct answer indicator, explanation, source badge, and difficulty.
- Edit, Approve, and Reject actions.
- An Approve All Visible action.
- A Generate Questions panel with module, CO, difficulty, and question count controls.

Make this page information-dense but readable. Use consistent CO1–CO6 chips and understated status labels.

### E. QUIZ BUILDER
Design a quiz creation page with:
- Quiz title and module selection.
- Opening and closing date/time.
- A searchable question bank containing approved questions only.
- Filters by course outcome.
- Selected question list with drag-and-drop reordering and remove actions.
- Live total marks and per-CO question counts.
- A clear Publish Quiz button.
- Existing quizzes with Draft, Published, and Closed status chips.

Use a paper-planner aesthetic, with burgundy action buttons and cream cards.

### F. STUDENT HOME
Create a warmer, student-friendly dashboard with:
- Personalised greeting and USN.
- Quiz availability cards.
- Next deadline.
- Weakest course outcome.
- Upcoming academic deadlines.
- A compact CO progress visualisation.
- Quick-access cards for Quizzes, My Progress, Study Plan, Flashcards, Ask the Course, and Calendar.

Include small decorative details inspired by a vintage student planner, but keep the interface professional and easy to navigate.

### G. QUIZ ATTEMPT AND RESULT
Create two screens.

Quiz attempt:
- Quiz title and attempt number.
- Time remaining until quiz closure.
- Question counter and progress bar.
- Four selectable answer options.
- Question navigation palette showing answered and unanswered questions.
- Save-progress feedback.
- Submit Quiz button with a confirmation dialog showing unanswered questions.

Never display correct answers or CO tags during an active attempt.

Quiz result:
- Total score and percentage.
- Individual CO performance using compact bars or chips.
- Attempts remaining out of a maximum of two.
- Review Answers and Retry buttons when permitted.

### H. STUDENT PROGRESS AND STUDY PLAN
Create a personalised academic progress screen with:
- CO1–CO6 performance chart.
- Score, threshold, and status for each CO.
- Past quiz attempts.
- On Track and Needs Work labels.
- Build My Study Plan button.

The study plan should resemble a curated revision journal, with recommended modules, slide references, flashcards, practice questions, and a Regenerate Plan button.

### I. ASK THE COURSE AND AI ASSISTANT
Create a beautiful conversational interface that remains practical for real academic use.

Include:
- Chat history.
- Suggested prompts.
- User and assistant messages.
- Loading states.
- Slide citations displayed as clickable chips containing module and slide numbers.
- Expandable slide excerpts.
- Tool activity chips under assistant responses.
- Quiz draft cards with a Review Questions action.
- Confirmation cards for proposed calendar changes with Approve and Cancel actions.

Use subtle burgundy and dusty-blue message bubbles, a cream paper background, and a clean message composer.

### J. CO SHEET AND ANALYTICS
Create a faculty analytics workspace with:
- Module and Semester toggle.
- Optional section filter.
- Student table with USN, name, CO1–CO6 percentages, and total.
- Highlighted below-threshold scores.
- Average attainment row.
- Export to Excel action.
- Interactive bar chart for average score by CO with target markers.
- Score distribution chart.
- Weak CO summaries and detailed drill-downs.

Prioritise chart legibility, aligned tables, and professional academic reporting.

### K. CALENDAR AND FLASHCARDS
Calendar:
- Month and week views.
- Events for quizzes, assignments, exams, teaching, and custom activities.
- Elegant category colours.
- Event detail panels and faculty event-management actions.

Flashcards:
- Filter by module and CO.
- Large flip cards with question and answer states.
- Previous and Next buttons.
- Progress counter and optional Mark as Known toggle.

## 5. INTERACTION AND COMPONENT STATES

Design reusable components and variants for:
- Primary, secondary, and ghost buttons.
- Inputs, dropdowns, tabs, and search fields.
- CO1–CO6 tags.
- Draft, Approved, Rejected, Published, Closed, Processing, Done, and Failed status chips.
- Cards, sortable tables, progress bars, charts, modals, toast notifications, and confirmation dialogs.
- Loading skeletons, empty states, and error states with retry actions.

Create interactive prototypes for the most important flows: login, faculty module upload, question approval, quiz creation and publishing, student quiz attempt, result viewing, and opening the AI assistant.

## 6. LAYOUT AND RESPONSIVENESS

Design primarily for a 1440px desktop viewport, with layouts that remain usable on tablet screens.

Use a consistent spacing system, accessible contrast, readable text sizes, aligned grids, and reusable Auto Layout components. Use a 12-column content grid where appropriate.

Avoid excessive decoration behind tables, forms, charts, and quiz questions. Keep the editorial aesthetic concentrated in page headers, backgrounds, navigation, cards, and decorative separators.

## 7. FINAL QUALITY BAR

The application should look like a premium, vintage-inspired academic product designed by a skilled UI/UX designer.

Preserve the distinctive burgundy, beige, ivory, dusty-blue, striped, and scrapbook aesthetic of the references. Make the visuals cohesive across every page, while ensuring the interface remains intuitive, responsive, accessible, and genuinely usable.

Do not use generic purple AI gradients, neon colours, glassmorphism, overly rounded generic SaaS cards, or a sterile all-white dashboard. Do not sacrifice functional clarity for decoration.

Prioritise the login, faculty dashboard, module upload, question review, quiz builder, student quiz attempt/result, and CO analytics screens first. Deliver a cohesive Figma design system with reusable components, desktop screen layouts, and connected prototype flows.

This project was built with [Lovable](https://lovable.dev).

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/db4c50b7-8444-4424-9cc0-28e40c2d78a2).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
