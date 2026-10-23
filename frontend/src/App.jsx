import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, ArrowRight, ArrowUpRight, BookOpen, CalendarDays, Check,
  CheckCircle2, ChevronDown, CircleDollarSign, Clock3, FileQuestion, GraduationCap,
  LayoutDashboard, LoaderCircle, LogOut, Menu, MessageCircle, MessageSquareText,
  NotebookTabs, PanelRightClose, Plus, RefreshCw, Search, Send, Sparkles,
  Trash2, X, XCircle
} from 'lucide-react';
import { api, ApiError } from './api.js';
import { advanceCalendarPeriod } from './calendar.js';
import { normalizeProposalStatus, proposalStatusLabel } from './proposals.js';
import { questionMatchesCourseOutcome } from './questions.js';

const NAV = {
  faculty: [
    { id: 'home', label: 'Home', icon: LayoutDashboard },
    { id: 'questions', label: 'Question review', icon: FileQuestion },
    { id: 'calendar', label: 'Calendar', icon: CalendarDays },
    { id: 'cost', label: 'AI usage & cost', icon: CircleDollarSign }
  ],
  student: [
    { id: 'home', label: 'Home', icon: LayoutDashboard },
    { id: 'study-plan', label: 'Study plan', icon: NotebookTabs },
    { id: 'flashcards', label: 'Flashcards', icon: BookOpen },
    { id: 'ask-course', label: 'Ask the Course', icon: MessageSquareText },
    { id: 'calendar', label: 'Calendar', icon: CalendarDays }
  ]
};
const PAGE_TITLES = {
  home: 'Home', questions: 'Question review', calendar: 'Calendar', cost: 'AI usage & cost',
  'study-plan': 'Your study plan', flashcards: 'Flashcards', 'ask-course': 'Ask the Course'
};
const errorText = (error) => error instanceof Error ? error.message : 'Something went wrong. Please try again.';
const dateKey = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
const niceDate = (value, options = { month: 'long', day: 'numeric', year: 'numeric' }) => {
  if (!value) return 'Time not provided';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleDateString(undefined, options);
};
const dateRange = (date, view) => {
  if (view === 'week') {
    const start = new Date(date); start.setDate(date.getDate() - ((date.getDay() + 6) % 7)); start.setHours(0, 0, 0, 0);
    const end = new Date(start); end.setDate(end.getDate() + 7);
    return [start, end];
  }
  const start = new Date(date.getFullYear(), date.getMonth(), 1); start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  const end = new Date(start); end.setDate(end.getDate() + 42);
  return [start, end];
};

function Field({ label, children, className = '' }) {
  return <label className={`field ${className}`}><span>{label}</span>{children}</label>;
}
function Button({ variant = 'secondary', children, className = '', ...props }) {
  return <button className={`button button-${variant} ${className}`} {...props}>{children}</button>;
}
function StatusPanel({ kind = 'empty', title, children, action, onAction, compact = false }) {
  const Icon = kind === 'error' ? XCircle : kind === 'loading' ? LoaderCircle : BookOpen;
  return <div className={`status-panel status-${kind} ${compact ? 'status-compact' : ''}`}>
    <span className="status-icon"><Icon size={compact ? 17 : 20} className={kind === 'loading' ? 'spin' : ''} /></span>
    <div className="status-copy"><strong>{title}</strong>{children && <p>{children}</p>}</div>
    {action && <Button onClick={onAction} variant={kind === 'error' ? 'secondary' : 'primary'}>{action}</Button>}
  </div>;
}
function Toast({ toast, onClose }) {
  useEffect(() => {
    if (!toast) return undefined;
    const timer = setTimeout(onClose, 4200);
    return () => clearTimeout(timer);
  }, [toast, onClose]);
  if (!toast) return null;
  return <div className={`toast toast-${toast.type || 'success'}`} role="status">
    {toast.type === 'error' ? <XCircle size={18} /> : <CheckCircle2 size={18} />}
    <span>{toast.message}</span><button aria-label="Dismiss notification" onClick={onClose}><X size={16} /></button>
  </div>;
}

function Login({ onLogin }) {
  const [role, setRole] = useState('student');
  const [fields, setFields] = useState({ usn: '', pin: '', email: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const credentials = role === 'student'
        ? { usn: fields.usn.trim().toUpperCase(), pin: fields.pin }
        : { email: fields.email.trim(), password: fields.password };
      const result = await api.login(credentials);
      if (result?.role !== role || !result?.access_token) throw new Error('The server returned an incomplete or mismatched session. Please contact your administrator.');
      const user = await api.me(result.access_token);
      if (user?.role !== role) throw new Error('The authenticated profile does not match the selected account type.');
      onLogin({ token: result.access_token, role: result.role, user });
    } catch (err) { setError(errorText(err)); }
    finally { setBusy(false); }
  };
  const chooseRole = (nextRole) => { setRole(nextRole); setError(''); };
  const handleRoleTabKeyDown = (event) => {
    const roles = ['student', 'faculty'];
    const index = roles.indexOf(role);
    const next = event.key === 'ArrowRight' ? roles[(index + 1) % roles.length]
      : event.key === 'ArrowLeft' ? roles[(index + roles.length - 1) % roles.length]
      : event.key === 'Home' ? roles[0]
      : event.key === 'End' ? roles[roles.length - 1]
      : null;
    if (next) { event.preventDefault(); chooseRole(next); event.currentTarget.querySelector(`[data-role="${next}"]`)?.focus(); }
  };
  return <main className="login-page">
    <div className="login-shell">
      <section className="login-story">
        <div className="brand brand-large"><span className="brand-mark"><GraduationCap size={23} /></span><span>Scholar</span></div>
        <div className="story-copy"><span className="eyebrow">A calmer way to learn</span><h1>Make space for<br /><em>understanding.</em></h1>
          <p>Your course materials, progress, and study support—together in one thoughtful place.</p>
        </div>
        <div className="login-quote"><span className="quote-mark">“</span><p>Grounded in your course. Built around your progress.</p><span className="quote-caption">ACADEMIC ASSISTANT</span></div>
        <div className="login-decoration decoration-one" /><div className="login-decoration decoration-two" />
      </section>
      <section className="login-card-wrap">
        <form className="login-card" onSubmit={submit}>
          <div className="mobile-brand brand"><span className="brand-mark"><GraduationCap size={21} /></span><span>Scholar</span></div>
          <span className="eyebrow">WELCOME BACK</span><h2>Sign in to continue</h2><p className="muted">Choose your account type to get started.</p>
          <div className="role-tabs" role="tablist" aria-label="Account type" onKeyDown={handleRoleTabKeyDown}>
            <button id="student-tab" type="button" role="tab" data-role="student" aria-selected={role === 'student'} aria-controls="login-fields" tabIndex={role === 'student' ? 0 : -1} className={role === 'student' ? 'active' : ''} onClick={() => chooseRole('student')}>Student</button>
            <button id="faculty-tab" type="button" role="tab" data-role="faculty" aria-selected={role === 'faculty'} aria-controls="login-fields" tabIndex={role === 'faculty' ? 0 : -1} className={role === 'faculty' ? 'active' : ''} onClick={() => chooseRole('faculty')}>Faculty</button>
          </div>
          <div id="login-fields" role="tabpanel" aria-labelledby={`${role}-tab`} className="login-fields">
            {role === 'student' ? <>
              <Field label="University seat number (USN)"><input autoComplete="username" placeholder="Enter your USN" value={fields.usn} onChange={(e) => setFields({ ...fields, usn: e.target.value })} required /></Field>
              <Field label="6-digit PIN"><input inputMode="numeric" autoComplete="current-password" maxLength={6} placeholder="Enter your PIN" value={fields.pin} onChange={(e) => setFields({ ...fields, pin: e.target.value.replace(/\D/g, '').slice(0, 6) })} required /></Field>
            </> : <>
              <Field label="Email or username"><input autoComplete="username" type="text" placeholder="you@university.edu" value={fields.email} onChange={(e) => setFields({ ...fields, email: e.target.value })} required /></Field>
              <Field label="Password"><input autoComplete="current-password" type="password" placeholder="Enter your password" value={fields.password} onChange={(e) => setFields({ ...fields, password: e.target.value })} required /></Field>
            </>}
          </div>
          {error && <div className="inline-error" role="alert"><XCircle size={17} />{error}</div>}
          <Button variant="primary" className="login-submit" type="submit" disabled={busy}>{busy ? <><LoaderCircle size={17} className="spin" /> Signing in…</> : <>Sign in <ArrowRight size={17} /></>}</Button>
          <p className="login-footnote">Your sign-in is verified securely by your institution.</p>
        </form>
      </section>
    </div>
    <footer className="login-footer">Scholar Academic Assistant <span>·</span> A place to learn with intention</footer>
  </main>;
}

function HomePage({ session, subject, navigate }) {
  const student = session.role === 'student';
  const links = student
    ? [{ id: 'study-plan', icon: NotebookTabs, title: 'Study with direction', text: 'Review your personal plan and focus on the outcomes that need attention.' }, { id: 'flashcards', icon: BookOpen, title: 'Practice at your pace', text: 'Turn course material into a focused review session.' }, { id: 'ask-course', icon: MessageSquareText, title: 'Ask the Course', text: 'Get answers grounded in your course slides, with citations.' }]
    : [{ id: 'questions', icon: FileQuestion, title: 'Review question drafts', text: 'Inspect AI-generated questions and decide what is ready to approve.' }, { id: 'calendar', icon: CalendarDays, title: 'Plan the term', text: 'See course events and manage your teaching calendar.' }, { id: 'cost', icon: CircleDollarSign, title: 'Understand AI usage', text: 'Explore reported token use from the usage log.' }];
  const [upcoming, setUpcoming] = useState([]); const [deadlineState, setDeadlineState] = useState('idle'); const [deadlineError, setDeadlineError] = useState('');
  const [progress, setProgress] = useState(null); const [progressState, setProgressState] = useState('idle'); const [progressError, setProgressError] = useState('');
  const loadStudentSnapshot = useCallback(() => {
    if (!student || !subject?.id) { setUpcoming([]); setDeadlineState('empty'); setProgress(null); setProgressState('empty'); return; }
    let active = true;
    setDeadlineState('loading'); setProgressState('loading'); setDeadlineError(''); setProgressError('');
    const now = new Date(); const future = new Date(now); future.setDate(future.getDate() + 45);
    api.events(session.token, subject.id, now.toISOString(), future.toISOString()).then((rows) => {
      if (!active) return;
      const upcomingRows = (Array.isArray(rows) ? rows : []).filter((event) => event.starts_at && new Date(event.starts_at) >= now).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at)).slice(0, 5);
      setUpcoming(upcomingRows); setDeadlineState(upcomingRows.length ? 'ready' : 'empty');
    }).catch((err) => { if (active) { setDeadlineError(errorText(err)); setDeadlineState('error'); } });
    api.progress(session.token, subject.id).then((result) => {
      if (!active) return;
      setProgress(result); setProgressState(Array.isArray(result?.co_scores) && result.co_scores.length ? 'ready' : 'empty');
    }).catch((err) => { if (active) { setProgressError(errorText(err)); setProgressState('error'); } });
    return () => { active = false; };
  }, [student, session.token, subject?.id]);
  useEffect(() => loadStudentSnapshot(), [loadStudentSnapshot]);
  const studentScores = progress?.co_scores || [];
  return <div className="page-content home-content">
    <section className="welcome-banner"><div className="welcome-copy"><span className="eyebrow">{student ? 'YOUR LEARNING SPACE' : 'FACULTY WORKSPACE'}</span>
      <h1>{student ? 'Welcome back' : 'Welcome back'}{session.user?.name ? `, ${session.user.name.split(' ')[0]}` : ''}.</h1>
      <p>{subject ? `Continue your work in ${subject.code ? `${subject.code} · ` : ''}${subject.name}.` : 'Choose a subject to begin exploring your course workspace.'}</p>
      <Button variant="primary" onClick={() => navigate(student ? 'study-plan' : 'questions')}>{student ? 'Open study plan' : 'Review questions'} <ArrowRight size={16} /></Button>
    </div><div className="welcome-illustration" aria-hidden="true"><div className="orbit orbit-a" /><div className="orbit orbit-b" /><div className="book-illustration"><BookOpen size={52} strokeWidth={1.4} /></div><span className="sparkle sparkle-a">✳</span><span className="sparkle sparkle-b">✦</span><span className="illustration-label">LEARN · REFLECT · GROW</span></div></section>
    {student && <section className="student-snapshot-grid">
      <article className="snapshot-card deadline-snapshot"><div className="snapshot-card-head"><div><span className="eyebrow">NEXT 45 DAYS</span><h2>Upcoming deadlines</h2></div><button className="text-link" onClick={() => navigate('calendar')}>Open calendar <ArrowUpRight size={14} /></button></div>
        {deadlineState === 'loading' && <div className="snapshot-state"><LoaderCircle size={16} className="spin" /> Loading course events…</div>}
        {deadlineState === 'error' && <div className="snapshot-state snapshot-error"><span>{deadlineError}</span><button onClick={loadStudentSnapshot}>Retry</button></div>}
        {deadlineState === 'empty' && <div className="snapshot-state">No upcoming events were returned for this course.</div>}
        {deadlineState === 'ready' && <div className="deadline-list">{upcoming.map((event) => <div className="deadline-row" key={event.id}><span className={`deadline-type event-${event.type || 'custom'}`} /><div><strong>{event.title}</strong><small>{niceDate(event.starts_at, { month: 'short', day: 'numeric' })} · {new Date(event.starts_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</small></div><span className="source-chip">{event.type || 'event'}</span></div>)}</div>}
      </article>
      <article className="snapshot-card progress-snapshot"><div className="snapshot-card-head"><div><span className="eyebrow">COURSE OUTCOMES</span><h2>Your progress</h2></div><button className="text-link" onClick={() => navigate('study-plan')}>Study plan <ArrowUpRight size={14} /></button></div>
        {progressState === 'loading' && <div className="snapshot-state"><LoaderCircle size={16} className="spin" /> Loading your progress…</div>}
        {progressState === 'error' && <div className="snapshot-state snapshot-error"><span>{progressError}</span><button onClick={loadStudentSnapshot}>Retry</button></div>}
        {progressState === 'empty' && <div className="snapshot-state">No CO scores have been returned for this course yet.</div>}
        {progressState === 'ready' && <div className="progress-preview-list">{studentScores.slice(0, 4).map((score, index) => { const pct = score.percentage == null ? null : Number(score.percentage); const shown = Number.isFinite(pct) ? Math.max(0, Math.min(100, pct)) : null; const number = score.co_number ?? score.number ?? index + 1; return <div className="progress-preview-row" key={score.co_id || number}><span className="co-chip">CO{String(number).replace(/^CO/i, '')}</span><div className="progress-track"><i style={{ width: shown == null ? '0%' : `${shown}%` }} /></div><strong>{shown == null ? 'No score' : `${shown.toFixed(0)}%`}</strong></div>; })}</div>}
      </article>
    </section>}
    <div className="section-heading"><div><span className="eyebrow">A GOOD PLACE TO START</span><h2>{student ? 'Your learning tools' : 'Your teaching tools'}</h2></div><span className="muted small-text">{subject ? subject.code || subject.name : 'No subject selected'}</span></div>
    <div className="home-tool-grid">{links.map(({ id, icon: Icon, title, text }) => <button key={id} className="home-tool-card" onClick={() => navigate(id)}><span className="tool-card-icon"><Icon size={20} /></span><span className="tool-card-title">{title}</span><span className="tool-card-text">{text}</span><span className="tool-card-link">Open <ArrowUpRight size={14} /></span></button>)}</div>
    {!subject && <div className="context-note"><span className="note-dot" /><p>Select a course from the top bar. Course content and progress will appear here when the service is connected.</p></div>}
  </div>;
}

function QuestionCard({ question, onAction, onSave, busy, coLabel }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ stem: question.stem || '', options: Array.isArray(question.options) ? [...question.options] : ['', '', '', ''], correct_option: question.correct_option ?? 0, explanation: question.explanation || '' });
  useEffect(() => {
    setDraft({ stem: question.stem || '', options: Array.isArray(question.options) ? [...question.options] : ['', '', '', ''], correct_option: question.correct_option ?? 0, explanation: question.explanation || '' });
  }, [question]);
  const save = async () => { const saved = await onSave(question.id, draft); if (saved) setEditing(false); };
  return <article className="question-card">
    <div className="question-card-head"><div className="question-tags"><span className="co-chip">{question.co_number ? `CO${String(question.co_number).replace(/^CO/i, '')}` : (coLabel || 'Course outcome')}</span><span className={`status-chip status-${question.status || 'draft'}`}>{question.status || 'draft'}</span><span className="source-chip">{question.source || 'Unknown source'}</span>{question.difficulty && <span className="source-chip">{question.difficulty}</span>}</div><span className="question-mark">{question.marks ?? '—'} marks</span></div>
    {editing ? <div className="question-edit"><textarea aria-label="Question text" value={draft.stem} onChange={(e) => setDraft({ ...draft, stem: e.target.value })} rows={3} />
      <div className="option-edit-list">{draft.options.map((option, index) => <label key={index} className={`option-edit ${draft.correct_option === index ? 'option-correct' : ''}`}><input type="radio" name={`correct-${question.id}`} checked={draft.correct_option === index} onChange={() => setDraft({ ...draft, correct_option: index })} /><span>{String.fromCharCode(65 + index)}</span><input aria-label={`Option ${String.fromCharCode(65 + index)}`} value={option} onChange={(e) => setDraft({ ...draft, options: draft.options.map((item, i) => i === index ? e.target.value : item) })} /></label>)}</div>
      <textarea aria-label="Explanation" placeholder="Explanation" value={draft.explanation} onChange={(e) => setDraft({ ...draft, explanation: e.target.value })} rows={2} />
      <div className="question-actions"><Button onClick={() => setEditing(false)}>Cancel edit</Button><Button variant="primary" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save changes'}</Button></div>
    </div> : <>
      <h3 className="question-stem">{question.stem || 'Question text unavailable'}</h3>
      <div className="question-options">{(question.options || []).map((option, index) => <div className={`question-option ${question.correct_option === index ? 'is-correct' : ''}`} key={index}><span>{String.fromCharCode(65 + index)}</span><p>{option}</p>{question.correct_option === index && <span className="correct-label"><Check size={13} /> Correct</span>}</div>)}</div>
      {question.explanation && <p className="question-explanation"><strong>Explanation</strong> {question.explanation}</p>}
      <div className="question-actions"><Button onClick={() => setEditing(true)}>Edit</Button>{question.status !== 'approved' && <Button variant="success" disabled={busy} onClick={() => onAction(question.id, 'approve')}><Check size={15} /> Approve</Button>}{question.status !== 'rejected' && <Button variant="danger-ghost" disabled={busy} onClick={() => onAction(question.id, 'reject')}><X size={15} /> Reject</Button>}</div>
    </>}
  </article>;
}

function QuestionReview({ session, subjectId, notify, onGenerate }) {
  const [subjectInfo, setSubjectInfo] = useState(null); const [subjectStatus, setSubjectStatus] = useState('loading'); const [subjectError, setSubjectError] = useState('');
  const [generationOpen, setGenerationOpen] = useState(false); const [generation, setGeneration] = useState({ moduleId: '', co: '', difficulty: 'medium', count: '5' });
  const [moduleId, setModuleId] = useState(''); const [filters, setFilters] = useState({ co_id: '', status: '', source: '' });
  const [questions, setQuestions] = useState([]); const [status, setStatus] = useState('idle'); const [error, setError] = useState(''); const [busyId, setBusyId] = useState('');
  const loadSubject = useCallback(async () => {
    if (!subjectId) { setSubjectStatus('empty'); return; }
    setSubjectStatus('loading'); setSubjectError('');
    try { const data = await api.subject(session.token, subjectId); setSubjectInfo(data); setSubjectStatus('ready'); setModuleId((current) => current || data.modules?.[0]?.id || ''); }
    catch (err) { setSubjectError(errorText(err)); setSubjectStatus('error'); }
  }, [session.token, subjectId]);
  useEffect(() => { setModuleId(''); setSubjectInfo(null); loadSubject(); }, [loadSubject]);
  const loadQuestions = useCallback(async () => {
    if (!moduleId) { setQuestions([]); setStatus('empty'); return; }
    setStatus('loading'); setError('');
    const selectedCo = subjectInfo?.cos?.find((co) => String(co.number) === String(filters.co_id));
    const apiFilters = { status: filters.status, source: filters.source, ...(selectedCo?.id ? { co_id: selectedCo.id } : {}) };
    try { const rows = await api.questions(session.token, moduleId, apiFilters); setQuestions(Array.isArray(rows) ? rows : []); setStatus('ready'); }
    catch (err) { setError(errorText(err)); setStatus('error'); }
  }, [session.token, moduleId, filters, subjectInfo]);
  const modules = subjectInfo?.modules || []; const cos = subjectInfo?.cos || [];
  const coLabelFor = (question) => {
    const co = cos.find((item) => String(item.id) === String(question.co_id) || String(item.number) === String(question.co_number));
    return co ? `CO${co.number}` : 'Course outcome';
  };
  useEffect(() => { if (subjectStatus === 'ready') loadQuestions(); }, [loadQuestions, subjectStatus]);
  const action = async (id, actionName) => {
    setBusyId(id);
    try { const updated = await api.questionAction(session.token, id, actionName); setQuestions((rows) => rows.map((row) => row.id === id ? { ...row, ...updated } : row)); notify(`${actionName === 'approve' ? 'Question approved' : 'Question rejected'}.`); }
    catch (err) { notify(errorText(err), 'error'); }
    finally { setBusyId(''); }
  };
  const save = async (id, fields) => {
    setBusyId(id);
    try { const updated = await api.updateQuestion(session.token, id, fields); setQuestions((rows) => rows.map((row) => row.id === id ? { ...row, ...updated } : row)); notify('Question changes saved.'); return true; }
    catch (err) { notify(errorText(err), 'error'); return false; }
    finally { setBusyId(''); }
  };
  const visible = useMemo(() => questions.filter((q) => questionMatchesCourseOutcome(q, filters.co_id, cos) && (!filters.status || q.status === filters.status) && (!filters.source || String(q.source).toLowerCase() === filters.source.toLowerCase())), [questions, filters, cos]);
  const counts = useMemo(() => ({ draft: questions.filter((q) => q.status === 'draft').length, approved: questions.filter((q) => q.status === 'approved').length, rejected: questions.filter((q) => q.status === 'rejected').length }), [questions]);
  const approveVisible = async () => { for (const item of visible.filter((q) => q.status !== 'approved')) await action(item.id, 'approve'); };
  const startGeneration = (event) => {
    event.preventDefault();
    const module = modules.find((item) => item.id === generation.moduleId);
    const co = cos.find((item) => String(item.number) === String(generation.co));
    if (!module || !co) return;
    onGenerate(`Generate ${generation.count} ${generation.difficulty} draft questions for ${module.number ? `Module ${module.number} — ` : ''}${module.title} (module_id: ${module.id}), aligned to CO${co.number} (co_id: ${co.id}). Use these exact IDs and save the questions as drafts for faculty review only.`);
    setGenerationOpen(false);
  };
  const groupedQuestions = useMemo(() => {
    const groups = new Map();
    for (const question of visible) {
      const key = question.co_number || question.co_id || 'unassigned';
      if (!groups.has(key)) groups.set(key, { key, label: coLabelFor(question), questions: [] });
      groups.get(key).questions.push(question);
    }
    return [...groups.values()];
  }, [visible, cos]);
  return <div className="page-content">
    <PageTitle eyebrow="FACULTY · QUESTION QUALITY" title="Question review" description="Review every draft before it reaches a student. AI-generated questions always need your approval." />
    <div className="metric-strip"><div><strong>{counts.draft}</strong><span>Draft</span></div><div><strong>{counts.approved}</strong><span>Approved</span></div><div><strong>{counts.rejected}</strong><span>Rejected</span></div><span className="metric-caption">Counts reflect the questions loaded for this module.</span></div>
    <section className="filter-bar">
      <Field label="Module"><select value={moduleId} onChange={(e) => setModuleId(e.target.value)} disabled={subjectStatus !== 'ready' || modules.length === 0}><option value="">Choose a module</option>{modules.map((m) => <option key={m.id} value={m.id}>{m.number ? `Module ${m.number} · ` : ''}{m.title}</option>)}</select></Field>
      <Field label="Course outcome"><select value={filters.co_id} onChange={(e) => setFilters({ ...filters, co_id: e.target.value })}><option value="">All outcomes</option>{cos.map((co) => <option key={co.id || co.number} value={co.number}>{`CO${co.number}`}</option>)}</select></Field>
      <Field label="Status"><select value={filters.status} onChange={(e) => setFilters({ ...filters, status: e.target.value })}><option value="">All statuses</option><option value="draft">Draft</option><option value="approved">Approved</option><option value="rejected">Rejected</option></select></Field>
      <Field label="Source"><select value={filters.source} onChange={(e) => setFilters({ ...filters, source: e.target.value })}><option value="">All sources</option><option value="AI">AI</option><option value="faculty">Faculty</option></select></Field>
    </section>
    {subjectStatus === 'loading' && <StatusPanel kind="loading" title="Loading course modules…" />}
    {subjectStatus === 'error' && <StatusPanel kind="error" title="Couldn't load this course" action="Retry" onAction={loadSubject}>{subjectError}</StatusPanel>}
    {subjectStatus === 'empty' && <StatusPanel title="Choose a subject" action="Refresh" onAction={loadSubject}>Select a course from the subject menu to review its questions.</StatusPanel>}
    {subjectStatus === 'ready' && modules.length === 0 && <StatusPanel title="No modules available" action="Retry" onAction={loadSubject}>This subject has no modules yet. A module is needed before questions can be reviewed.</StatusPanel>}
    {subjectStatus === 'ready' && modules.length > 0 && !moduleId && <StatusPanel title="Choose a module" action="Refresh modules" onAction={loadSubject}>Select a module above to load its question drafts.</StatusPanel>}
    {subjectStatus === 'ready' && moduleId && status === 'loading' && <StatusPanel kind="loading" title="Loading questions…" />}
    {status === 'error' && <StatusPanel kind="error" title="Couldn't load questions" action="Retry" onAction={loadQuestions}>{error}</StatusPanel>}
    {status === 'ready' && <>
      <div className="content-toolbar"><div><h2>Questions <span className="count-pill">{visible.length}</span></h2><p className="muted">Grouped by course outcome · Review and approve each draft.</p></div><div className="toolbar-actions"><Button onClick={() => { setGeneration({ ...generation, moduleId, co: cos[0]?.number ? String(cos[0].number) : '' }); setGenerationOpen(true); }} disabled={!moduleId || !cos.length}><Sparkles size={15} /> Generate drafts</Button><Button variant="primary" onClick={approveVisible} disabled={!visible.some((q) => q.status === 'draft') || Boolean(busyId)}><Check size={15} /> Approve all visible drafts</Button></div></div>
      {visible.length === 0 ? <StatusPanel title="No questions match these filters" action="Clear filters" onAction={() => setFilters({ co_id: '', status: '', source: '' })}>Try another status or choose a different module. Questions are only shown when returned by the course service.</StatusPanel> : <div className="question-groups">{groupedQuestions.map((group) => <section key={group.key} className="question-group"><div className="question-group-heading"><span className="co-chip">{group.label}</span><span>{group.questions.length} {group.questions.length === 1 ? 'question' : 'questions'}</span></div><div className="question-list">{group.questions.map((question) => <QuestionCard key={question.id} question={question} coLabel={group.label} onAction={action} onSave={save} busy={busyId === question.id} />)}</div></section>)}</div>}
    </>}
    {generationOpen && <div className="modal-backdrop" onClick={() => setGenerationOpen(false)}><form role="dialog" aria-modal="true" aria-labelledby="generation-title" className="event-editor generation-editor" onSubmit={startGeneration} onClick={(e) => e.stopPropagation()}><button type="button" className="modal-close" onClick={() => setGenerationOpen(false)} aria-label="Close draft generation"><X size={19} /></button><span className="eyebrow">FACULTY REVIEW WORKFLOW</span><h2 id="generation-title">Generate question drafts</h2><p className="muted small-text">The assistant will create review-only drafts. Nothing is approved or published automatically.</p><Field label="Module"><select required value={generation.moduleId} onChange={(e) => setGeneration({ ...generation, moduleId: e.target.value })}>{modules.map((module) => <option key={module.id} value={module.id}>{module.number ? `Module ${module.number} · ` : ''}{module.title}</option>)}</select></Field><Field label="Course outcome"><select required value={generation.co} onChange={(e) => setGeneration({ ...generation, co: e.target.value })}><option value="">Choose an outcome</option>{cos.map((co) => <option key={co.id} value={co.number}>CO{co.number} · {co.description || 'Course outcome'}</option>)}</select></Field><Field label="Difficulty"><select value={generation.difficulty} onChange={(e) => setGeneration({ ...generation, difficulty: e.target.value })}>{['easy', 'medium', 'hard'].map((value) => <option key={value} value={value}>{value[0].toUpperCase() + value.slice(1)}</option>)}</select></Field><Field label="Number of drafts"><input type="number" min="1" max="20" required value={generation.count} onChange={(e) => setGeneration({ ...generation, count: e.target.value })} /></Field><div className="question-actions"><Button type="button" onClick={() => setGenerationOpen(false)}>Cancel</Button><Button variant="primary" type="submit"><MessageCircle size={15} /> Continue in assistant</Button></div></form></div>}
  </div>;
}

function StudyPlan({ session, subjectId, notify }) {
  const [plan, setPlan] = useState(null); const [state, setState] = useState('idle'); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!subjectId) { setState('empty'); return; }
    setState('loading'); setError('');
    try { const data = await api.studyPlan(session.token, subjectId); setPlan(data); setState(data ? 'ready' : 'empty'); }
    catch (err) { if (err instanceof ApiError && err.status === 404) { setPlan(null); setState('empty'); } else { setError(errorText(err)); setState('error'); } }
  }, [session.token, subjectId]);
  useEffect(() => { load(); }, [load]);
  const regenerate = async () => {
    if (!subjectId) return;
    setBusy(true); setError('');
    try { const result = await api.buildStudyPlan(session.token, subjectId); setPlan(result); setState(result ? 'ready' : 'empty'); notify('Study plan generated.'); }
    catch (err) { setError(errorText(err)); setState('error'); }
    finally { setBusy(false); }
  };
  const weak = plan?.weak_cos || plan?.weak_outcomes || plan?.weak_course_outcomes || [];
  const updatedAt = plan?.generated_at || plan?.created_at || plan?.generated_on;
  return <div className="page-content">
    <PageTitle eyebrow="STUDENT · PERSONALIZED REVIEW" title="Your study plan" description="A focused path through the course material, based on the outcomes that need more practice." right={<Button onClick={regenerate} disabled={busy || !subjectId}><RefreshCw size={15} className={busy ? 'spin' : ''} /> {busy ? 'Building…' : 'Regenerate plan'}</Button>} />
    {!subjectId && <StatusPanel title="Choose a subject to begin" action="Retry" onAction={load}>Your plan is linked to a course. Select one from the subject menu above.</StatusPanel>}
    {state === 'loading' && <StatusPanel kind="loading" title="Checking for your study plan…" />}
    {state === 'error' && <StatusPanel kind="error" title="Study plan unavailable" action="Retry" onAction={load}>{error}</StatusPanel>}
    {state === 'empty' && subjectId && <div className="empty-feature"><div className="empty-art"><NotebookTabs size={34} /></div><span className="eyebrow">YOUR NEXT STEP</span><h2>No study plan yet</h2><p>Build a plan from your course progress and review recommendations. The plan will appear here once the course service is available.</p><Button variant="primary" onClick={regenerate} disabled={busy}>{busy ? <><LoaderCircle size={16} className="spin" /> Building your plan…</> : <><Sparkles size={16} /> Build my study plan</>}</Button></div>}
    {state === 'ready' && plan && <>
      <div className="plan-summary"><div><span className="eyebrow">PLAN GENERATED</span><h2>{updatedAt ? niceDate(updatedAt) : 'Your latest plan'}</h2></div><div className="plan-summary-side"><strong>{weak.length || plan.items?.length || '—'}</strong><span>focus areas</span></div></div>
      {weak.length > 0 ? <div className="plan-outcomes">{weak.map((outcome, index) => {
        const number = outcome.co_number || outcome.number || outcome.co || index + 1;
        const slides = outcome.slides || outcome.recommended_slides || [];
        const cards = outcome.flashcards || [];
        const practice = outcome.practice_questions || outcome.questions || [];
        return <article className="plan-outcome" key={outcome.id || number}><div className="plan-outcome-header"><span className="co-chip">CO{String(number).replace(/^CO/i, '')}</span><h3>{outcome.description || outcome.title || outcome.name || 'Review this course outcome'}</h3></div>
          {outcome.reason && <p className="muted">{outcome.reason}</p>}
          <div className="plan-recommendations">
            <Recommendation title="Recommended slides" count={slides.length}>{slides.length ? slides.map((slide, i) => <div className="recommendation-row" key={slide.id || `${slide.module_id}-${slide.slide_number}-${i}`}><BookOpen size={15} /><span><strong>{slide.module_title || slide.module || `Module ${slide.module_number || ''}`}, slide {slide.slide_number ?? '—'}</strong><small>{slide.text_preview || slide.text || 'Slide preview not provided by the course service.'}</small></span></div>) : <p className="muted small-text">No slide recommendations were included in this plan.</p>}</Recommendation>
            <Recommendation title="Flashcards" count={cards.length}>{cards.length ? cards.map((card, i) => <div className="recommendation-row" key={card.id || i}><BookOpen size={15} /><span><strong>{card.front || card.question || 'Flashcard'}</strong><small>{card.back || card.answer || ''}</small></span></div>) : <p className="muted small-text">No flashcards were included in this plan.</p>}</Recommendation>
            <Recommendation title="Practice questions" count={practice.length}>{practice.length ? practice.map((q, i) => <div className="recommendation-row" key={q.id || i}><FileQuestion size={15} /><span><strong>{q.stem || q.question || 'Practice question'}</strong><small>{q.difficulty || ''}</small></span></div>) : <p className="muted small-text">No practice questions were included in this plan.</p>}</Recommendation>
          </div>
        </article>;
      })}</div> : <StatusPanel title="Your plan is ready" action="Regenerate" onAction={regenerate}>The service returned a plan, but did not include weak course outcomes in its response.</StatusPanel>}
    </>}
  </div>;
}
function Recommendation({ title, count, children }) { return <section className="recommendation"><div className="recommendation-head"><strong>{title}</strong><span>{count}</span></div>{children}</section>; }

function Flashcards({ session, subjectId }) {
  const [modules, setModules] = useState([]); const [courseOutcomes, setCourseOutcomes] = useState([]); const [moduleId, setModuleId] = useState(''); const [cards, setCards] = useState([]); const [state, setState] = useState('idle'); const [error, setError] = useState('');
  const [index, setIndex] = useState(0); const [flipped, setFlipped] = useState(false); const [coFilter, setCoFilter] = useState(''); const [known, setKnown] = useState({});
  const loadModules = useCallback(async () => {
    if (!subjectId) { setState('empty'); return; }
    setState('loading'); setError('');
    try { const data = await api.subject(session.token, subjectId); const list = data.modules || []; setModules(list); setCourseOutcomes(data.cos || []); setModuleId((old) => old || list[0]?.id || ''); setState(list.length ? 'ready' : 'no-modules'); }
    catch (err) { setError(errorText(err)); setState('error'); }
  }, [session.token, subjectId]);
  useEffect(() => { setModules([]); setModuleId(''); loadModules(); }, [loadModules]);
  const loadCards = useCallback(async () => {
    if (!moduleId) return;
    setState('loading'); setError('');
    try { const data = await api.flashcards(session.token, moduleId); setCards(Array.isArray(data) ? data : []); setIndex(0); setFlipped(false); setState('ready'); }
    catch (err) { setError(errorText(err)); setState('error'); }
  }, [session.token, moduleId]);
  useEffect(() => { if (moduleId) loadCards(); }, [loadCards, moduleId]);
  const visible = useMemo(() => cards.filter((card) => !coFilter || String(card.co_id) === coFilter), [cards, coFilter]);
  useEffect(() => { setIndex(0); setFlipped(false); }, [coFilter]);
  const card = visible[index];
  const toggleKnown = () => {
    if (!card?.id) return;
    const next = { ...known, [card.id]: !known[card.id] }; setKnown(next);
  };
  const cos = [...new Set(cards.map((item) => item.co_id).filter(Boolean))];
  const coLabelForId = (id) => { const item = courseOutcomes.find((co) => String(co.id) === String(id)); return item ? `CO${item.number}` : 'Course outcome'; };
  return <div className="page-content">
    <PageTitle eyebrow="STUDENT · ACTIVE RECALL" title="Flashcards" description="A simple way to strengthen what you know, one idea at a time." />
    <div className="flashcard-filters"><Field label="Module"><select value={moduleId} onChange={(e) => setModuleId(e.target.value)}><option value="">Choose a module</option>{modules.map((m) => <option key={m.id} value={m.id}>{m.number ? `Module ${m.number} · ` : ''}{m.title}</option>)}</select></Field><Field label="Course outcome"><select value={coFilter} onChange={(e) => setCoFilter(e.target.value)}><option value="">All outcomes</option>{cos.map((co) => <option key={co} value={co}>{coLabelForId(co)}</option>)}</select></Field><span className="flashcard-filter-note">{cards.length} cards in this module</span></div>
    {state === 'loading' && <StatusPanel kind="loading" title="Loading flashcards…" />}
    {state === 'error' && <StatusPanel kind="error" title="Flashcards couldn't be loaded" action="Retry" onAction={moduleId ? loadCards : loadModules}>{error}</StatusPanel>}
    {state === 'empty' && <StatusPanel title="Choose a subject" action="Retry" onAction={loadModules}>Select a course to find its flashcards.</StatusPanel>}
    {state === 'no-modules' && <StatusPanel title="No modules available" action="Retry" onAction={loadModules}>This course has no modules to study yet.</StatusPanel>}
    {state === 'ready' && !card && <StatusPanel title={cards.length ? 'No cards for this outcome' : 'No flashcards yet'} action={cards.length ? 'Clear outcome filter' : 'Retry'} onAction={cards.length ? () => setCoFilter('') : loadCards}>{cards.length ? 'Choose another outcome or show all cards.' : 'Flashcards will appear here when course materials are available.'}</StatusPanel>}
    {state === 'ready' && card && <section className="flashcard-stage"><div className="flashcard-progress"><span>Card <strong>{index + 1}</strong> of {visible.length}</span><span className="co-chip">{coLabelForId(card.co_id)}</span></div>
      <button className={`flashcard ${flipped ? 'flipped' : ''}`} onClick={() => setFlipped(!flipped)} aria-label={flipped ? 'Show question' : 'Flip to answer'}><span className="flashcard-side-label">{flipped ? 'ANSWER' : 'QUESTION'}</span><span className="flashcard-text">{flipped ? (card.back || card.answer || 'Answer not provided.') : (card.front || card.question || 'Question not provided.')}</span><span className="flashcard-hint">Click to {flipped ? 'see question' : 'reveal answer'}</span></button>
      <div className="flashcard-controls"><Button onClick={() => { setIndex((index - 1 + visible.length) % visible.length); setFlipped(false); }} disabled={visible.length < 2}><ArrowLeft size={16} /> Previous</Button><button className={`known-toggle ${known[card.id] ? 'known' : ''}`} onClick={toggleKnown} disabled={!card.id}><CheckCircle2 size={17} /> {known[card.id] ? 'Known this session' : 'Mark as known'}</button><Button onClick={() => { setIndex((index + 1) % visible.length); setFlipped(false); }} disabled={visible.length < 2}>Next <ArrowRight size={16} /></Button></div>
      <p className="local-note">“Known” status is temporary; it clears when you leave this page or reload.</p>
    </section>}
  </div>;
}

function AskCourse({ session, subjectId }) {
  const [question, setQuestion] = useState(''); const [messages, setMessages] = useState([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [recent, setRecent] = useState([]);
  const [citation, setCitation] = useState(null); const [citationText, setCitationText] = useState(''); const [citationBusy, setCitationBusy] = useState(false); const [citationError, setCitationError] = useState('');
  const ask = async (event, supplied = question) => {
    event?.preventDefault(); const prompt = supplied.trim(); if (!prompt || !subjectId || busy) return;
    setBusy(true); setError(''); setQuestion(''); setMessages((items) => [...items, { id: crypto.randomUUID(), question: prompt, status: 'loading' }]);
    try {
      const result = await api.askCourse(session.token, subjectId, prompt);
      const answer = result?.refused ? 'I couldn’t find relevant information in the available course material.' : (result?.answer || 'The course service returned no answer.');
      const citations = Array.isArray(result?.citations) ? result.citations : [];
      setMessages((items) => items.map((item, i) => i === items.length - 1 ? { ...item, status: 'ready', answer, citations, refused: Boolean(result?.refused) } : item));
      const nextRecent = [prompt, ...recent.filter((item) => item !== prompt)].slice(0, 5); setRecent(nextRecent);
    } catch (err) {
      setMessages((items) => items.map((item, i) => i === items.length - 1 ? { ...item, status: 'error' } : item)); setError(errorText(err));
    } finally { setBusy(false); }
  };
  const openCitation = async (item, prompt) => {
    setCitation(item); setCitationText(''); setCitationError(''); setCitationBusy(true);
    try {
      const chunks = await api.retrieve(session.token, subjectId, prompt);
      const match = (Array.isArray(chunks) ? chunks : []).find((chunk) => String(chunk.module_id) === String(item.module_id) && Number(chunk.slide_number) === Number(item.slide_number));
      if (match?.text) setCitationText(match.text); else setCitationError('The citation is available, but its slide preview was not returned.');
    } catch (err) { setCitationError(errorText(err)); }
    finally { setCitationBusy(false); }
  };
  return <div className="page-content ask-page">
    <PageTitle eyebrow="STUDENT · COURSE-GROUNDED HELP" title="Ask the Course" description="Ask about what you’re learning. Answers are grounded in your course materials, with slide citations." />
    <div className="ask-layout"><section className="ask-main"><div className="ask-intro"><span className="ask-icon"><MessageSquareText size={20} /></span><div><strong>A question about your course?</strong><p>Answers come from the course material—not the open web.</p></div><span className="grounded-badge"><span /> COURSE-GROUNDED</span></div>
      {!subjectId && <StatusPanel title="Choose a subject to ask a question" compact>Select a course from the subject menu before asking the course assistant.</StatusPanel>}
      <div className="qa-thread">{messages.length === 0 ? <div className="qa-empty"><div className="qa-empty-icon"><Search size={22} /></div><h2>What would you like to understand?</h2><p>Try asking about a concept, a definition, or an example from your slides.</p></div> : messages.map((item) => <div className="qa-exchange" key={item.id}><div className="qa-question"><span className="qa-avatar">You</span><p>{item.question}</p></div>{item.status === 'loading' && <div className="qa-answer qa-loading"><LoaderCircle size={17} className="spin" /> Searching your course material…</div>}{item.status === 'error' && <div className="qa-answer qa-inline-error"><XCircle size={16} /> The question could not be answered because the course service is unavailable. Submit it again when the connection is restored.</div>}{item.status === 'ready' && <div className={`qa-answer ${item.refused ? 'qa-refused' : ''}`}><span className="answer-label"><Sparkles size={15} /> {item.refused ? 'NOT IN COURSE MATERIAL' : 'COURSE ANSWER'}</span><p>{item.answer}</p>{item.citations.length > 0 && <div className="citation-row">{item.citations.map((source, i) => <button key={`${source.module_id}-${source.slide_number}-${i}`} className="citation-chip" onClick={() => openCitation(source, item.question)}><BookOpen size={13} /> Module · Slide {source.slide_number}</button>)}</div>}{!item.refused && item.citations.length === 0 && <p className="citation-warning">No slide citations were returned for this answer.</p>}</div>}</div>)}</div>
      <form className="ask-composer" onSubmit={ask}><textarea aria-label="Your course question" placeholder="Ask a question about your course material…" value={question} onChange={(e) => setQuestion(e.target.value)} rows={2} disabled={busy || !subjectId} /><div className="composer-bottom"><span>Answers may be limited to the material available in this course.</span><Button variant="primary" type="submit" disabled={busy || !question.trim() || !subjectId}>{busy ? <LoaderCircle size={16} className="spin" /> : <Send size={16} />} Ask</Button></div></form>
      {error && <StatusPanel kind="error" compact title="Couldn't reach the course assistant" action="Dismiss" onAction={() => setError('')}>{error}</StatusPanel>}
    </section><aside className="recent-panel"><div className="aside-heading"><Clock3 size={16} /><h3>Recent questions</h3></div>{recent.length ? recent.map((item) => <button key={item} className="recent-question" onClick={() => ask(null, item)} disabled={busy}>{item}<ArrowUpRight size={14} /></button>) : <p className="muted small-text">Your recent questions appear here while this page is open.</p>}<div className="recent-footnote">Question history is not stored and clears when you leave the page or sign out.</div></aside></div>
    {citation && <div className="modal-backdrop" onClick={() => setCitation(null)}><section role="dialog" aria-modal="true" aria-labelledby="citation-title" className="citation-modal" onClick={(e) => e.stopPropagation()}><button className="modal-close" onClick={() => setCitation(null)} aria-label="Close citation"><X size={19} /></button><span className="eyebrow">COURSE SOURCE</span><h2 id="citation-title">Module · Slide {citation.slide_number}</h2>{citationBusy ? <StatusPanel kind="loading" compact title="Loading slide excerpt…" /> : citationError ? <StatusPanel kind="error" compact title="Slide preview unavailable">{citationError}</StatusPanel> : <p className="citation-text">{citationText}</p>}</section></div>}
  </div>;
}

function CalendarPage({ session, subjectId, notify }) {
  const faculty = session.role === 'faculty'; const [view, setView] = useState('month'); const [cursor, setCursor] = useState(() => new Date()); const [events, setEvents] = useState([]); const [state, setState] = useState('idle'); const [error, setError] = useState(''); const [selected, setSelected] = useState(null); const [editor, setEditor] = useState(null); const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({ title: '', type: 'teaching', starts_at: '', ends_at: '' });
  const [start, end] = useMemo(() => dateRange(cursor, view), [cursor, view]);
  const load = useCallback(async () => {
    if (!subjectId) { setState('empty'); return; }
    setState('loading'); setError('');
    try { const rows = await api.events(session.token, subjectId, start.toISOString(), end.toISOString()); setEvents(Array.isArray(rows) ? rows : []); setState('ready'); }
    catch (err) { setError(errorText(err)); setState('error'); }
  }, [session.token, subjectId, start, end]);
  useEffect(() => { load(); }, [load]);
  const move = (direction) => setCursor((current) => advanceCalendarPeriod(current, view, direction));
  const openCreate = (date) => { const chosen = new Date(date); chosen.setHours(9, 0, 0, 0); const finish = new Date(chosen); finish.setHours(10, 0, 0, 0); setSelected(null); setForm({ title: '', type: 'teaching', starts_at: localInputValue(chosen), ends_at: localInputValue(finish) }); setEditor({ mode: 'create' }); };
  const openEdit = (event) => { setForm({ title: event.title || '', type: event.type || 'custom', starts_at: localInputValue(new Date(event.starts_at)), ends_at: event.ends_at ? localInputValue(new Date(event.ends_at)) : '' }); setEditor({ mode: 'edit', id: event.id, event }); };
  const saveEvent = async (e) => {
    e.preventDefault(); if (!form.title.trim()) return;
    setBusy(true);
    const payload = { subject_id: subjectId, type: form.type, title: form.title.trim(), starts_at: new Date(form.starts_at).toISOString(), ...(form.ends_at ? { ends_at: new Date(form.ends_at).toISOString() } : {}) };
    try {
      if (editor.mode === 'edit') { const updated = await api.updateEvent(session.token, editor.id, payload); setEvents((rows) => rows.map((row) => row.id === editor.id ? { ...row, ...updated } : row)); notify('Calendar event updated.'); }
      else { const created = await api.createEvent(session.token, payload); setEvents((rows) => [...rows, created]); notify('Calendar event added.'); }
      setEditor(null);
    } catch (err) { notify(errorText(err), 'error'); }
    finally { setBusy(false); }
  };
  const removeEvent = async (event) => {
    if (!window.confirm(`Delete “${event.title}”? This cannot be undone.`)) return;
    try { await api.deleteEvent(session.token, event.id); setEvents((rows) => rows.filter((row) => row.id !== event.id)); setSelected(null); notify('Calendar event deleted.'); }
    catch (err) { notify(errorText(err), 'error'); }
  };
  const title = view === 'month' ? cursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' }) : `${start.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${new Date(end.getTime() - 86400000).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`;
  const cells = Array.from({ length: 42 }, (_, i) => { const date = new Date(start); date.setDate(start.getDate() + i); return date; });
  const eventsFor = (day) => events.filter((item) => dateKey(new Date(item.starts_at)) === dateKey(day)).sort((a, b) => new Date(a.starts_at) - new Date(b.starts_at));
  const visibleDays = view === 'week' ? cells.filter((day) => dateKey(day) >= dateKey(start) && dateKey(day) < dateKey(end)).slice(0, 7) : cells;
  return <div className="page-content">
    <PageTitle eyebrow={`${faculty ? 'FACULTY' : 'STUDENT'} · COURSE SCHEDULE`} title="Calendar" description={faculty ? 'Keep the important moments of your course in view.' : 'A clear view of the deadlines and events for your course.'} right={faculty ? <Button variant="primary" onClick={() => openCreate(cursor)}><Plus size={16} /> Add event</Button> : null} />
    <section className="calendar-card"><div className="calendar-toolbar"><div className="calendar-title-group"><div className="calendar-nav"><button aria-label="Previous period" onClick={() => move(-1)}><ArrowLeft size={16} /></button><button aria-label="Next period" onClick={() => move(1)}><ArrowRight size={16} /></button></div><h2>{title}</h2><button className="today-button" onClick={() => setCursor(new Date())}>Today</button></div><div className="view-switch"><button className={view === 'month' ? 'active' : ''} onClick={() => setView('month')}>Month</button><button className={view === 'week' ? 'active' : ''} onClick={() => setView('week')}>Week</button></div></div>
      {state === 'loading' && <StatusPanel kind="loading" title="Loading calendar events…" compact />}{state === 'error' && <StatusPanel kind="error" title="Calendar events unavailable" action="Retry" onAction={load}>{error}</StatusPanel>}{state === 'empty' && <StatusPanel title="Choose a subject to see its calendar" action="Retry" onAction={load}>Events are shown for one course at a time.</StatusPanel>}
      {state === 'ready' && <><div className={`calendar-grid ${view === 'week' ? 'calendar-week' : ''}`}><div className="weekday-row">{['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => <span key={day}>{day}</span>)}</div><div className="calendar-days">{visibleDays.map((day) => <div key={dateKey(day)} className={`calendar-day ${day.getMonth() !== cursor.getMonth() && view === 'month' ? 'outside-month' : ''} ${dateKey(day) === dateKey(new Date()) ? 'is-today' : ''}`} onDoubleClick={() => faculty && openCreate(day)}><div className="day-head"><button className="day-number" onClick={() => setCursor(day)}>{day.getDate()}</button>{faculty && <button className="day-add" aria-label={`Add event on ${dateKey(day)}`} onClick={() => openCreate(day)}><Plus size={14} /></button>}</div><div className="day-events">{eventsFor(day).slice(0, view === 'month' ? 3 : 6).map((event) => <button key={event.id} className={`calendar-event event-${event.type || 'custom'}`} onClick={() => setSelected(event)}><span>{new Date(event.starts_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}</span>{event.title}</button>)}{eventsFor(day).length > (view === 'month' ? 3 : 6) && <span className="more-events">+{eventsFor(day).length - (view === 'month' ? 3 : 6)} more</span>}</div></div>)}</div></div>
        <div className="calendar-legend">{[['quiz', 'Quiz'], ['assignment', 'Assignment'], ['exam', 'Exam'], ['teaching', 'Teaching'], ['custom', 'Custom']].map(([type, label]) => <span key={type}><i className={`legend-dot event-${type}`} />{label}</span>)}</div>
        {events.length === 0 && <div className="calendar-empty"><span className="empty-calendar-icon"><CalendarDays size={19} /></span><div><strong>No events in this period</strong><p>{faculty ? 'Add an event to keep your course plans together.' : 'Your course events will appear here when they are added.'}</p></div>{faculty && <Button onClick={() => openCreate(cursor)}><Plus size={15} /> Add event</Button>}</div>}
      </>}
    </section>
    {selected && <div className="modal-backdrop" onClick={() => setSelected(null)}><section role="dialog" aria-modal="true" aria-labelledby="event-title" className="event-modal" onClick={(e) => e.stopPropagation()}><button className="modal-close" onClick={() => setSelected(null)} aria-label="Close event"><X size={19} /></button><span className={`event-type-pill event-${selected.type || 'custom'}`}>{selected.type || 'Event'}</span><h2 id="event-title">{selected.title}</h2><p className="event-date"><CalendarDays size={16} />{niceDate(selected.starts_at, { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}</p><p className="event-date"><Clock3 size={16} />{new Date(selected.starts_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}{selected.ends_at ? ` – ${new Date(selected.ends_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : ''}</p>{selected.description && <p className="muted">{selected.description}</p>}{faculty && <div className="question-actions"><Button onClick={() => openEdit(selected)}>Edit or move</Button><Button variant="danger-ghost" onClick={() => removeEvent(selected)}><Trash2 size={15} /> Delete</Button></div>}</section></div>}
    {editor && <div className="modal-backdrop" onClick={() => !busy && setEditor(null)}><form role="dialog" aria-modal="true" aria-labelledby="event-editor-title" className="event-editor" onSubmit={saveEvent} onClick={(e) => e.stopPropagation()}><button type="button" className="modal-close" onClick={() => setEditor(null)} aria-label="Close event form"><X size={19} /></button><span className="eyebrow">COURSE CALENDAR</span><h2 id="event-editor-title">{editor.mode === 'edit' ? 'Edit event' : 'Add an event'}</h2><Field label="Event title"><input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="e.g. Midterm review" /></Field><Field label="Event type"><select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{['quiz', 'assignment', 'exam', 'teaching', 'custom'].map((type) => <option value={type} key={type}>{type[0].toUpperCase() + type.slice(1)}</option>)}</select></Field><Field label="Starts"><input type="datetime-local" required value={form.starts_at} onChange={(e) => setForm({ ...form, starts_at: e.target.value })} /></Field><Field label="Ends (optional)"><input type="datetime-local" value={form.ends_at} onChange={(e) => setForm({ ...form, ends_at: e.target.value })} /></Field><div className="question-actions"><Button type="button" onClick={() => setEditor(null)}>Cancel</Button><Button variant="primary" type="submit" disabled={busy}>{busy ? 'Saving…' : editor.mode === 'edit' ? 'Save changes' : 'Add event'}</Button></div></form></div>}
  </div>;
}
function localInputValue(date) { if (Number.isNaN(date.getTime())) return ''; const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000); return local.toISOString().slice(0, 16); }

function CostPage({ session }) {
  const [rows, setRows] = useState([]); const [state, setState] = useState('loading'); const [error, setError] = useState('');
  const from = useMemo(() => `${new Date().getFullYear()}-01-01T00:00:00Z`, []); const to = useMemo(() => new Date().toISOString(), []);
  const load = useCallback(async () => { setState('loading'); setError(''); try { const data = await api.usage(session.token, from, to); setRows(Array.isArray(data) ? data : []); setState('ready'); } catch (err) { setError(errorText(err)); setState('error'); } }, [session.token, from, to]);
  useEffect(() => { load(); }, [load]);
  const totals = rows.reduce((acc, row) => ({ calls: acc.calls + Number(row.calls || 0), prompt: acc.prompt + Number(row.prompt_tokens || 0), completion: acc.completion + Number(row.completion_tokens || 0), total: acc.total + Number(row.total_tokens || 0) }), { calls: 0, prompt: 0, completion: 0, total: 0 });
  const max = Math.max(...rows.map((row) => Number(row.total_tokens || 0)), 1);
  return <div className="page-content">
    <PageTitle eyebrow="FACULTY · TRANSPARENCY" title="AI usage & cost" description="A view of reported token use. Usage data is read from the course service, never estimated in this page." />
    {state === 'loading' && <StatusPanel kind="loading" title="Loading usage summary…" />}{state === 'error' && <StatusPanel kind="error" title="Usage summary unavailable" action="Retry" onAction={load}>{error}</StatusPanel>}
    {state === 'ready' && <>
      <section className="usage-overview"><div className="usage-total"><span className="eyebrow">TOTAL TOKENS · THIS YEAR</span><strong>{totals.total.toLocaleString()}</strong><span>Reported by the usage log</span></div><div className="usage-stat"><span>AI calls</span><strong>{totals.calls.toLocaleString()}</strong><small>Across reported steps</small></div><div className="usage-stat"><span>Prompt tokens</span><strong>{totals.prompt.toLocaleString()}</strong><small>Reported usage</small></div><div className="usage-stat"><span>Completion tokens</span><strong>{totals.completion.toLocaleString()}</strong><small>Reported usage</small></div></section>
      {rows.length === 0 ? <StatusPanel title="No usage has been reported" action="Refresh" onAction={load}>The usage endpoint returned no records for the selected period. Token and call totals are shown as zero because no records were returned.</StatusPanel> : <>
        <section className="usage-card"><div className="content-toolbar"><div><h2>Tokens by step</h2><p className="muted">{niceDate(from, { month: 'short', day: 'numeric', year: 'numeric' })} – {niceDate(to, { month: 'short', day: 'numeric', year: 'numeric' })}</p></div></div><div className="usage-bars">{rows.map((row) => <div className="usage-bar-row" key={row.step}><span>{row.step}</span><div className="usage-track"><i style={{ width: `${Math.max(2, Number(row.total_tokens || 0) / max * 100)}%` }} /></div><strong>{Number(row.total_tokens || 0).toLocaleString()}</strong><small>{Number(row.calls || 0)} calls</small></div>)}</div></section>
        <section className="usage-card comparison-card"><div className="content-toolbar"><div><h2>Usage model comparison</h2><p className="muted">The design principle behind the course assistant.</p></div><span className="source-chip">Measured data only</span></div><div className="comparison-table-wrap"><table className="data-table"><thead><tr><th>Approach</th><th>Usage pattern</th><th>Calls / tokens</th><th>What this log can confirm</th></tr></thead><tbody><tr><td><strong>One AI call per student</strong></td><td>Repeated per learner</td><td className="not-reported">Not reported</td><td>Student count and per-student attribution are not provided by this endpoint.</td></tr><tr><td><strong>AI once per module</strong></td><td>Reuse course-level material</td><td className="not-reported">Not reported</td><td>Per-module breakdown is not provided by this endpoint.</td></tr></tbody></table></div><p className="comparison-note">The usage summary reports totals by step only. A numeric comparison would require per-module usage and enrollment data, so no savings estimate is shown.</p></section>
      </>}
      <p className="usage-range-note">Reporting period: January 1, {new Date().getFullYear()} to today · No token-to-currency conversion is available.</p>
    </>}
  </div>;
}

function PageTitle({ eyebrow, title, description, right }) { return <header className="page-title-row"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{right && <div className="page-title-action">{right}</div>}</header>; }

function ChatPanel({ session, onClose, onNavigate, subject, initialPrompt = '' }) {
  const [messages, setMessages] = useState([]); const [input, setInput] = useState(initialPrompt); const [busy, setBusy] = useState(false); const [conversationId, setConversationId] = useState(null); const [error, setError] = useState(''); const [lastPrompt, setLastPrompt] = useState(''); const [confirming, setConfirming] = useState('');
  const panelRef = useRef(null);
  const faculty = session.role === 'faculty';
  const suggestions = faculty ? ['Which COs are weak in this class?', 'Make a remedial quiz for CO3', 'Export the CO sheet'] : ['What should I revise this week?', 'Explain a concept from the slides'];
  useEffect(() => {
    const panel = panelRef.current;
    if (!panel) return undefined;
    const previousFocus = document.activeElement;
    const focusableSelector = 'button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';
    const focusables = () => [...panel.querySelectorAll(focusableSelector)];
    (focusables()[0] || panel).focus();
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); onClose(); return; }
      if (event.key !== 'Tab') return;
      const items = focusables();
      if (!items.length) { event.preventDefault(); panel.focus(); return; }
      if (event.shiftKey && document.activeElement === items[0]) { event.preventDefault(); items.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === items.at(-1)) { event.preventDefault(); items[0].focus(); }
    };
    panel.addEventListener('keydown', handleKeyDown);
    return () => {
      panel.removeEventListener('keydown', handleKeyDown);
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, [onClose]);
  const send = async (prompt = input) => {
    const message = prompt.trim(); if (!message || busy) return;
    setInput(''); setError(''); setLastPrompt(message); setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'user', text: message }]); setBusy(true);
    try {
      const result = await api.chat(session.token, message, conversationId);
      setConversationId(result?.conversation_id || conversationId);
      setMessages((items) => [...items, { id: crypto.randomUUID(), role: 'assistant', text: result?.reply || 'The assistant returned no reply.', toolCalls: Array.isArray(result?.tool_calls) ? result.tool_calls : [], proposals: Array.isArray(result?.proposals) ? result.proposals : [], drafts: Array.isArray(result?.drafts) ? result.drafts : [] }]);
    } catch (err) { setError(errorText(err)); }
    finally { setBusy(false); }
  };
  const actOnProposal = async (proposalId, approve) => {
    setConfirming(proposalId);
    try {
      const result = await api.confirmProposal(session.token, proposalId, approve);
      setMessages((items) => items.map((message) => ({ ...message, proposals: message.proposals?.map((p) => (p.proposal_id || p.id) === proposalId ? { ...p, local_status: normalizeProposalStatus(result) } : p) })));
      setError('');
    } catch (err) { setError(errorText(err)); }
    finally { setConfirming(''); }
  };
  const clear = () => { setMessages([]); setConversationId(null); setError(''); setLastPrompt(''); };
  return <div className="chat-scrim" onClick={onClose}><aside ref={panelRef} role="dialog" aria-modal="true" aria-labelledby="assistant-title" tabIndex={-1} className="chat-panel" onClick={(e) => e.stopPropagation()}>
    <div className="chat-header"><div className="chat-heading-icon"><Sparkles size={18} /></div><div><strong id="assistant-title">Ask the assistant</strong><span>{faculty ? 'Faculty assistant' : 'Your course assistant'}{subject ? ` · ${subject.code || subject.name}` : ''}</span></div><button className="chat-clear" onClick={clear} disabled={messages.length === 0 || busy}>Clear chat</button><button className="chat-close" onClick={onClose} aria-label="Close assistant"><PanelRightClose size={19} /></button></div>
    <div className="chat-messages">{messages.length === 0 ? <div className="chat-welcome"><div className="chat-welcome-icon"><Sparkles size={24} /></div><h2>{faculty ? 'What would you like to work on?' : 'How can I help you study?'}</h2><p>{faculty ? 'I can help you explore course outcomes, prepare drafts, and organize course events.' : 'Ask a question about your course or get help planning your next study session.'}</p><div className="suggestion-list">{suggestions.map((text) => <button key={text} onClick={() => send(text)} disabled={busy}>{text}<ArrowUpRight size={14} /></button>)}</div></div> : messages.map((message) => <div key={message.id} className={`chat-message ${message.role === 'user' ? 'from-user' : 'from-assistant'}`}><span className="chat-message-avatar">{message.role === 'user' ? (session.user?.name?.[0] || (faculty ? 'F' : 'S')) : <Sparkles size={14} />}</span><div className="chat-message-content"><div className="chat-message-label">{message.role === 'user' ? 'You' : 'Assistant'}</div><p>{message.text}</p>{message.toolCalls?.length > 0 && <div className="tool-chip-row">{message.toolCalls.map((tool, i) => <span className="tool-chip" key={`${tool.name}-${i}`}><span className="tool-dot" />{tool.status === 'error' || tool.status === 'failed' ? 'Failed' : tool.status === 'call_limit_exceeded' ? 'Limited' : 'Called'} {tool.name}</span>)}</div>}{message.proposals?.map((proposal, i) => <ProposalCard key={proposal.id || i} proposal={proposal} confirming={confirming} onAction={actOnProposal} />)}{faculty && message.drafts?.map((draft, i) => <div className="quiz-draft-card" key={draft.id || i}><span className="draft-icon"><FileQuestion size={16} /></span><div><strong>Quiz draft ready for review</strong><p>{draft.count ?? draft.question_count ?? draft.questions?.length ?? 'Generated'} questions{draft.co_number || draft.co ? ` · CO${String(draft.co_number || draft.co).replace(/^CO/i, '')}` : ''}. This draft is not published.</p><button onClick={() => { onNavigate('questions'); onClose(); }}>Review questions <ArrowRight size={13} /></button></div></div>)}</div></div>)}{busy && <div className="chat-working"><span className="chat-message-avatar"><Sparkles size={14} /></span><span><i /><i /><i /> Working with course data…</span></div>}{error && <div className="chat-error" role="alert"><XCircle size={16} /><div><strong>Assistant unavailable</strong><p>{error}</p>{lastPrompt && <button onClick={() => send(lastPrompt)} disabled={busy}><RefreshCw size={13} /> Retry last message</button>}</div></div>}</div>
    {messages.length === 0 && <div className="chat-role-note">{faculty ? 'Faculty prompts' : 'Student prompts'} · Responses depend on configured course tools.</div>}
    <form className="chat-composer" onSubmit={(e) => { e.preventDefault(); send(); }}><textarea aria-label="Message the assistant" placeholder="Write a message…" value={input} onChange={(e) => setInput(e.target.value)} rows={2} disabled={busy} /><div><span>Enter to send · Shift + Enter for a new line</span><Button variant="primary" type="submit" disabled={busy || !input.trim()} aria-label="Send message"><Send size={16} /></Button></div></form>
  </aside></div>;
}
function ProposalCard({ proposal, confirming, onAction }) {
  const args = proposal.arguments || proposal;
  const proposalId = proposal.proposal_id || proposal.id;
  const state = proposal.local_status || proposal.status;
  const pending = !proposal.local_status && ['pending_confirmation', 'pending'].includes(proposal.status);
  const startsAt = args.starts_at || proposal.starts_at;
  const moving = String(proposal.action || '').includes('move');
  const title = args.title || proposal.title || (moving ? 'Move calendar event' : 'Schedule an event');
  const subject = args.subject_name || proposal.subject_name || args.subject_id || proposal.subject || 'Current course';
  return <div className="proposal-card"><span className="proposal-icon"><CalendarDays size={16} /></span><div className="proposal-body"><div className="proposal-header"><strong>{title}</strong><span className="proposal-badge">PROPOSAL</span></div><p>{startsAt ? niceDate(startsAt) : 'Date not provided'}{startsAt ? ` · ${new Date(startsAt).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : ''}{args.ends_at ? ` – ${new Date(args.ends_at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}` : ''}</p><small>{subject}{args.type ? ` · ${args.type}` : ''}</small>{pending && proposalId ? <div className="proposal-actions"><Button variant="success" disabled={Boolean(confirming)} onClick={() => onAction(proposalId, true)}>{confirming === proposalId ? <LoaderCircle size={14} className="spin" /> : <Check size={14} />} Approve</Button><Button variant="secondary" disabled={Boolean(confirming)} onClick={() => onAction(proposalId, false)}><X size={14} /> Cancel</Button></div> : state ? <div className={`proposal-result status-${state}`}>{proposalStatusLabel(state)}</div> : <small className="muted">The server did not return a proposal ID; this action cannot be confirmed.</small>}</div></div>;
}

export default function App() {
  const [session, setSession] = useState(null); const [page, setPage] = useState(() => location.hash.split('/')[2] || 'home'); const [subjectList, setSubjectList] = useState([]); const [subjectId, setSubjectId] = useState(''); const [subjectState, setSubjectState] = useState('idle'); const [subjectError, setSubjectError] = useState('');
  const [chatOpen, setChatOpen] = useState(false); const [chatPrefill, setChatPrefill] = useState(''); const [toast, setToast] = useState(null); const [mobileNavOpen, setMobileNavOpen] = useState(false);
  const notify = useCallback((message, type = 'success') => setToast({ message, type, id: Date.now() }), []);
  const closeToast = useCallback(() => setToast(null), []);
  const closeChat = useCallback(() => { setChatOpen(false); setChatPrefill(''); }, []);
  useEffect(() => {
    if (!session?.role) return;
    const syncRoute = () => {
      const [, routeRole, routePage] = location.hash.split('/');
      const allowed = (NAV[session.role] || []).some((item) => item.id === routePage);
      if (routeRole === session.role && allowed) setPage(routePage);
      else { setPage('home'); history.replaceState(null, '', `#/${session.role}/home`); }
    };
    syncRoute(); window.addEventListener('hashchange', syncRoute);
    return () => window.removeEventListener('hashchange', syncRoute);
  }, [session?.role]);
  useEffect(() => {
    if (!session?.token) return;
    setSubjectState('loading'); setSubjectError('');
    api.subjects(session.token).then((data) => {
      const rows = Array.isArray(data) ? data : []; setSubjectList(rows); setSubjectId((current) => rows.some((s) => s.id === current) ? current : rows[0]?.id || ''); setSubjectState(rows.length ? 'ready' : 'empty');
    }).catch((err) => { setSubjectList([]); setSubjectId(''); setSubjectError(errorText(err)); setSubjectState('error'); });
  }, [session?.token]);
  const subject = subjectList.find((item) => item.id === subjectId) || null;
  const navigate = (nextPage) => {
    const permitted = (NAV[session?.role] || []).some((item) => item.id === nextPage);
    if (permitted) { setPage(nextPage); location.hash = `#/${session.role}/${nextPage}`; setChatOpen(false); setChatPrefill(''); setMobileNavOpen(false); }
  };
  const logout = () => { setSession(null); setPage('home'); setSubjectList([]); setSubjectId(''); setChatOpen(false); history.replaceState(null, '', '#/login'); };
  const login = (nextSession) => { setSession(nextSession); setPage('home'); location.hash = `#/${nextSession.role}/home`; };
  const renderPage = () => {
    if (!session) return null;
    if (page === 'questions' && session.role === 'faculty') return <QuestionReview session={session} subjectId={subjectId} notify={notify} onGenerate={(prompt) => { setChatPrefill(prompt); setChatOpen(true); }} />;
    if (page === 'calendar') return <CalendarPage session={session} subjectId={subjectId} notify={notify} />;
    if (page === 'cost' && session.role === 'faculty') return <CostPage session={session} />;
    if (page === 'study-plan' && session.role === 'student') return <StudyPlan session={session} subjectId={subjectId} notify={notify} />;
    if (page === 'flashcards' && session.role === 'student') return <Flashcards session={session} subjectId={subjectId} />;
    if (page === 'ask-course' && session.role === 'student') return <AskCourse session={session} subjectId={subjectId} />;
    return <HomePage session={session} subject={subject} navigate={navigate} />;
  };
  if (!session) return <><Login onLogin={login} /><Toast toast={toast} onClose={closeToast} /></>;
  const userLabel = session.user?.name || session.user?.usn || session.user?.email || (session.role === 'faculty' ? 'Faculty account' : 'Student account');
  const NavIcon = ({ item }) => { const Icon = item.icon; return <Icon size={18} strokeWidth={1.8} />; };
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNavOpen ? 'sidebar-open' : ''}`}>
      <button className="brand sidebar-brand" onClick={() => navigate('home')}><span className="brand-mark"><GraduationCap size={20} /></span><span>Scholar</span></button>
      <div className="sidebar-course-label">YOUR WORKSPACE</div><nav className="sidebar-nav">{NAV[session.role].map((item) => <button className={`nav-item ${page === item.id ? 'selected' : ''}`} key={item.id} onClick={() => navigate(item.id)}><NavIcon item={item} /><span>{item.label}</span>{page === item.id && <span className="nav-active-dot" />}</button>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-help"><span className="help-sparkle"><Sparkles size={16} /></span><strong>Need a hand?</strong><p>Ask the assistant for course-grounded help.</p><button onClick={() => { setChatOpen(true); setMobileNavOpen(false); }}>Open assistant <ArrowUpRight size={13} /></button></div><div className="sidebar-footer"><span>Scholar Academic Assistant</span><span>Thoughtful learning, together.</span></div></div>
    </aside>
    <div className="app-main"><header className="topbar"><button className="mobile-menu" onClick={() => setMobileNavOpen(!mobileNavOpen)} aria-label="Toggle navigation"><Menu size={19} /></button><div className="breadcrumb"><span>Workspace</span><span className="breadcrumb-slash">/</span><strong>{PAGE_TITLES[page]}</strong></div>
      <div className="topbar-actions"><div className="subject-select-wrap"><BookOpen size={15} /><select aria-label="Select subject" value={subjectId} onChange={(e) => setSubjectId(e.target.value)} disabled={subjectState === 'loading' || subjectState === 'error' || subjectList.length === 0}><option value="">{subjectState === 'loading' ? 'Loading subjects…' : subjectState === 'error' ? 'Subjects unavailable' : 'Select a subject'}</option>{subjectList.map((item) => <option value={item.id} key={item.id}>{item.code ? `${item.code} · ` : ''}{item.name}</option>)}</select><ChevronDown size={14} className="select-chevron" /></div><span className={`role-badge role-${session.role}`}>{session.role}</span><div className="profile-chip"><span className="profile-avatar">{userLabel.charAt(0).toUpperCase()}</span><span className="profile-name">{userLabel}</span></div><button className="logout-button" onClick={logout} title="Sign out" aria-label="Sign out"><LogOut size={17} /></button></div>
    </header>
    {subjectState === 'error' && <div className="topbar-notice" role="status"><XCircle size={15} /> Course list unavailable: {subjectError} <button onClick={() => { setSubjectState('loading'); api.subjects(session.token).then((rows) => { setSubjectList(Array.isArray(rows) ? rows : []); setSubjectState(rows?.length ? 'ready' : 'empty'); }).catch((err) => { setSubjectError(errorText(err)); setSubjectState('error'); }); }}>Retry</button></div>}
    <main className="main-scroll" key={page}>{renderPage()}</main>
    <button className="assistant-fab" onClick={() => setChatOpen(true)}><span className="fab-icon"><MessageCircle size={18} /></span><span>Ask the assistant</span><span className="fab-key">⌘ J</span></button>
    </div>
    {mobileNavOpen && <button className="mobile-nav-backdrop" aria-label="Close navigation" onClick={() => setMobileNavOpen(false)} />}
    {chatOpen && <ChatPanel session={session} onClose={closeChat} onNavigate={navigate} subject={subject} initialPrompt={chatPrefill} />}
    <Toast toast={toast} onClose={closeToast} />
  </div>;
}
