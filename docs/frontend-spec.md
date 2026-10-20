# Frontend content spec

What every screen must contain. This is content only: no code, no colours. Owner tags come from the team task files. Pages tagged "unassigned" need someone to take them.

## The app in one paragraph

A web app for an academic assistant with two roles: **faculty** and **student**. Faculty upload slides, review AI-generated quiz questions, publish quizzes, and see CO (Course Outcome) attainment for the whole class. Students log in with USN and PIN, attempt quizzes (max 2 attempts), see their own CO scores, and get study help from the course material. An assistant chat is available to both roles. The look should be clean, calm and academic: light background, lots of white space, tables and charts that are easy to read in a screen recording. Desktop first, usable on a tablet.

## Global (applies to every screen)

**App shell** (Danwin)
- Left sidebar with the pages for the logged-in role (lists below).
- Top bar: subject selector (dropdown), role badge (Faculty or Student), user name or USN, logout.
- A floating "Ask the assistant" button that opens the chat panel from any page.
- Pages are routed by role. A student can never open a faculty page.

**Every page needs three states**
- Loading (skeleton or spinner)
- Empty (a sentence saying what is missing and a button to fix it, e.g. "No modules yet. Upload slides")
- Error (what failed and a retry button)

**Shared pieces**
- Toast messages for saved, approved, published, error.
- Tables: sortable headers, sticky header row, sensible column widths.
- Status chips with consistent labels: Draft, Approved, Rejected, Published, Closed, Processing, Done, Failed.
- CO chips ("CO1" to "CO6") used everywhere a CO is mentioned, so they look the same on every page.
- Confirmation dialog before anything destructive.

## Login (Danwin)

- App name and one-line description.
- Toggle or tabs: Student / Faculty.
- Student form: USN, PIN, Login button.
- Faculty form: email or username, password, Login button.
- Clear error message for wrong credentials.
- After login, route to the role's home page.

## Faculty pages

Sidebar: Home, Subjects and COs, Modules, Roster, Questions (review), Quizzes, CO Sheet, Dashboard, Calendar, Cost.

### Home (unassigned)
- Greeting and selected subject.
- Cards: modules uploaded, questions awaiting review, quizzes published, class CO attainment summary.
- Weak COs alert (COs below target) with a button to open the dashboard.
- Upcoming events (next 5).
- Shortcut buttons: Upload slides, Review questions, Create quiz.

### Subject and CO setup (Aparna)
- Form to create a subject: code, name, semester, target attainment %, default threshold %.
- Table of CO1 to CO6: description, threshold %, target %, each editable.
- Save button, and a list of existing subjects.

### Modules, upload and coverage (Aparna)
- List of modules with number, title, status chip (Processing, Done, Failed), chunk count.
- Upload button: PPT file picker, module number and title fields.
- Progress state while slides are parsed and tagged, with a message if some chunks stayed untagged (the upload still succeeds).
- **Coverage view:** one row or bar per CO showing how many slide chunks are mapped to it. A clear warning on any CO with zero chunks.
- Click a module to see its chunks: slide number, text preview, CO chips.

### Roster upload (Aparna)
- CSV file picker and a link to a sample CSV format.
- Preview table of parsed rows before confirming, with problem rows (duplicate USN, bad format) marked and explained.
- Confirm button, then a result summary: added, duplicates, rejected.
- Table of enrolled students: USN, name, section.

### Question review (Danwin)
- Filters: module, CO, status, source (AI or faculty).
- List of questions grouped by CO. Each card shows: question text, four options with the correct one marked, explanation, source badge (AI or Faculty), status chip, difficulty.
- Edit mode for text, options, correct answer and explanation.
- Approve and Reject buttons on each card, plus "Approve all visible".
- A Generate button (module, CO, difficulty, count) that adds new drafts to the list.
- Counts at the top: Draft, Approved, Rejected.

### Manual question form (Aparna)
- Fields: module, CO, question text, four options, correct option, explanation, marks, difficulty.
- Save as approved or save as draft.

### Quiz builder (Aparna)
- Quiz title, module, open time, close time.
- Picker of approved questions only, with filter by CO and a live count per CO and total marks.
- Selected questions list with drag to reorder and remove.
- Publish button. If the picker contains anything unapproved, show why it is blocked.
- List of existing quizzes with status chip (Draft, Published, Closed) and attempt count.

### CO sheet (Aparna)
- Toggle: Module / Semester. Module dropdown when Module is selected. Optional section filter.
- Table: one row per student (USN, name), one column per CO (percentage), and a Total column. Sorted by USN.
- Cells below the CO threshold highlighted.
- A summary row at the bottom: average per CO.
- **Export to Excel** button.
- Click a student row to see that student's quiz history.

### Dashboard (Aparna)
- Top tiles: students enrolled, attempts made, average score, number of COs meeting target.
- Bar chart: average score per CO, with a line marking the target.
- Score distribution chart (how many students fall in each score band).
- Table of COs: attainment %, target %, met or not, students above and below threshold.
- Weak COs highlighted at the top.
- Clicking a CO opens a drill-down: which modules, which questions (with how many got them wrong) and which students sit behind the number.
- Button on a weak CO: "Create remedial quiz", which opens the assistant with a prefilled request.

### Calendar (Danwin)
- Month and week views, switch at the top.
- Events coloured by type: quiz, assignment, exam, teaching, custom.
- Click an event for details. Faculty can add, edit, move and delete events.
- Published quizzes appear automatically.

### Cost page (Danwin)
- Table or bar chart: tokens used per step (tagging, generation, agent, Q&A, study plan, flashcards).
- A before-and-after table: "one AI call per student" versus "AI once per module", with the numbers measured from the usage log.
- Totals: AI calls made and total tokens.

## Student pages

Sidebar: Home, Quizzes, My Progress, Study Plan, Flashcards, Ask the Course, Calendar.

### Home (partly Danwin, otherwise unassigned)
- Greeting with name and USN.
- Cards: quizzes available now, next deadline, weakest CO.
- Upcoming deadlines list (from the calendar).
- A small CO progress preview.

### Quiz list (unassigned)
- Cards for each quiz: title, module, open and close time, status (Not started, In progress, Completed, Closed), attempts used out of 2, best score so far.
- Start or Retry button. Disabled when the quiz is closed or both attempts are used, with the reason shown.

### Attempt screen (Aparna)
- Header: quiz title, attempt number ("Attempt 1 of 2"), question counter, time left until the quiz closes.
- One question at a time or a scrolling list, with four options.
- Question palette showing answered and unanswered questions.
- Answers are saved as the student goes and survive a page refresh.
- Never show correct answers or CO tags during the attempt.
- Submit button with a confirmation dialog that lists how many questions are unanswered.

### Result screen (Aparna)
- Total score and percentage.
- Score for each CO, as chips or small bars.
- Attempts left, with a Retry button if one remains.
- Button to review answers.

### Quiz review (Aparna)
- Every question the student got wrong: their answer, the correct answer, the CO chip, and the explanation.
- Filter: all, wrong only, by CO.

### My progress (Aparna)
- Bar or radar chart: the student's score in each CO.
- Table of COs: score, threshold, status (On track, Needs work).
- List of past attempts with date and score.
- Button: "Build my study plan".

### Study plan (Danwin)
- The weak COs identified for this student.
- For each weak CO: recommended slides (module and slide number, with a text preview), flashcards, and practice questions.
- Generated date and a Regenerate button.

### Flashcards (Danwin)
- Filter by module and CO.
- Card that flips between question and answer, with Previous and Next buttons and a progress counter.
- Optional "mark as known" toggle.

### Ask the course (Danwin)
- Text box for a question about the course material.
- Answer shown with **slide citations** (module and slide number) as clickable chips that show the slide text.
- When nothing relevant is found, a clear message: the answer is not in the course material.
- Recent questions list.

### Calendar (Danwin)
- Same month and week views as faculty, read only. Shows only this student's subjects.

## Assistant chat panel (Danwin, both roles)

- Slides in from the right on any page, or sits in its own page.
- Message list with the user's messages and the assistant's replies.
- Loading indicator while the assistant works.
- **Tool chips** under a reply that show which tool ran, e.g. "Called find_weak_COs".
- **Confirmation card** when the assistant proposes scheduling or moving an event: shows title, date and time, subject, with Approve and Cancel buttons. Nothing is saved until approved.
- **Quiz draft card** when the assistant generates questions: shows count and CO, with a "Review questions" link to the review screen.
- Suggested prompts, different per role:
  - Faculty: "Which COs are weak in this class?", "Make a remedial quiz for CO3", "Export the CO sheet"
  - Student: "What should I revise this week?", "Explain a concept from the slides"
- Clear chat button.

## Priority for the demo video

Build and polish these first, in this order, because they are what the video shows:

1. Login
2. Module upload with coverage
3. Question review and approve
4. Quiz builder and publish
5. Student attempt and result
6. CO sheet and dashboard
7. Assistant chat with tool chips and confirmation card
8. Study plan and Ask the course
9. Calendar and cost page

Everything else can be simpler if time runs short.
