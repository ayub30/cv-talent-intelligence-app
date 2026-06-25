import { useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  AdjustmentsHorizontalIcon,
  ArrowDownTrayIcon,
  ArrowPathIcon,
  BeakerIcon,
  BuildingOffice2Icon,
  ChatBubbleLeftRightIcon,
  CheckCircleIcon,
  CircleStackIcon,
  ClipboardDocumentCheckIcon,
  DocumentMagnifyingGlassIcon,
  ExclamationTriangleIcon,
  MagnifyingGlassIcon,
  PaperAirplaneIcon,
  ShieldCheckIcon,
  SparklesIcon,
  StarIcon,
  UserGroupIcon,
} from '@heroicons/react/24/outline';

type Page =
  | 'dashboard'
  | 'contract'
  | 'search'
  | 'ai'
  | 'profile'
  | 'shortlist'
  | 'ingestion'
  | 'companies'
  | 'analytics';

type ApiCandidate = {
  id: string;
  name: string;
  reply_company: string;
  location: string;
  seniority: string;
  availability_status: string;
  current_project_name: string | null;
  last_updated: string;
  chroma_doc_id: string;
  skills: Array<{ skill: string; years_experience: number }>;
};

type Candidate = {
  id: string;
  name: string;
  role: string;
  company: string;
  location: string;
  score: number;
  confidence: number;
  completeness: number;
  availability: string;
  availabilityStatus: string;
  seniority: string;
  clearance: string;
  skills: string[];
  evidence: string[];
  gaps: string[];
  last_updated: string;
};

type AskMatch = {
  name: string;
  role?: string;
  score?: number;
  evidence?: string;
};

type ApiProfile = ApiCandidate & {
  cv_text: string;
  is_stale: boolean;
  completeness: number;
  gaps: string[];
};

type ProfileEditFields = {
  name: string;
  reply_company: string;
  location: string;
  seniority: string;
  availability_status: string;
  current_project_name: string;
  skills: Array<{ skill: string; years_experience: number }>;
};

const pages: Array<{ key: Page; label: string; icon: typeof UserGroupIcon }> = [
  { key: 'dashboard', label: 'Command', icon: ClipboardDocumentCheckIcon },
  { key: 'contract', label: 'Contract intake', icon: DocumentMagnifyingGlassIcon },
  { key: 'search', label: 'Talent search', icon: MagnifyingGlassIcon },
  { key: 'ai', label: 'AI match', icon: ChatBubbleLeftRightIcon },
  { key: 'profile', label: 'Profiles', icon: UserGroupIcon },
  { key: 'shortlist', label: 'Shortlist', icon: StarIcon },
  { key: 'ingestion', label: 'Ingestion', icon: CircleStackIcon },
  { key: 'companies', label: 'Companies', icon: BuildingOffice2Icon },
  { key: 'analytics', label: 'Analytics', icon: BeakerIcon },
];

const companies = [
  ['Northstar Digital', 'Digital engineering', 284, 91, 268, 'London'],
  ['Atlas Advisory', 'Cloud advisory', 241, 84, 221, 'Manchester'],
  ['Civitas Systems', 'AI product', 176, 88, 163, 'Birmingham'],
  ['Redwood Consulting', 'Transformation', 302, 73, 244, 'Edinburgh'],
  ['Fortis Risk', 'Cyber risk', 138, 94, 132, 'Remote'],
  ['Bluebridge Data', 'Analytics', 219, 81, 190, 'Bristol'],
] as const;

const skills = [
  ['Azure', 92, 71, 'High'],
  ['RAG', 88, 38, 'Critical'],
  ['Data migration', 76, 55, 'High'],
  ['Healthcare', 70, 47, 'Medium'],
  ['Cyber security', 64, 62, 'Stable'],
  ['Programme recovery', 58, 74, 'Surplus'],
] as const;

const AVAILABILITY_LABELS: Record<string, string> = {
  available: 'Available now',
  on_project: 'On project',
  on_bench: 'On bench',
  rolling_off: 'Rolling off',
};

const STALE_MONTHS = 6;
const INACTIVITY_TIMEOUT_MS = 30 * 60 * 1000;

function isCandidateStale(last_updated: string): boolean {
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - STALE_MONTHS);
  return new Date(last_updated) < cutoff;
}

function mapApiCandidate(api: ApiCandidate): Candidate {
  const role = api.seniority.charAt(0).toUpperCase() + api.seniority.slice(1);
  return {
    id: api.id,
    name: api.name,
    role,
    company: api.reply_company,
    location: api.location,
    score: 0,
    confidence: 0,
    completeness: 0,
    availability: AVAILABILITY_LABELS[api.availability_status] ?? api.availability_status,
    availabilityStatus: api.availability_status,
    seniority: api.seniority,
    clearance: '—',
    skills: api.skills.map((s) => s.skill),
    evidence: [],
    gaps: [],
    last_updated: api.last_updated,
  };
}

const defaultContract =
  'Healthcare client needs a senior Azure data engineering team to migrate clinical datasets, build governed analytics, and support an AI knowledge assistant with cited retrieval.';

export function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState(false);

  const [page, setPage] = useState<Page>('dashboard');
  const [selectedId, setSelectedId] = useState<string>('');
  const [query, setQuery] = useState('');
  const [minScore, setMinScore] = useState(75);
  const [contract, setContract] = useState(defaultContract);
  const [shortlist, setShortlist] = useState<string[]>([]);
  const [askInput, setAskInput] = useState('Find the best team for this contract');
  const [aiAnswer, setAiAnswer] = useState('Ask the assistant to rank people using the backend /ask route.');
  const [aiMatches, setAiMatches] = useState<AskMatch[]>([]);
  const [aiError, setAiError] = useState<string | null>(null);
  const [isAsking, setIsAsking] = useState(false);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [totalCandidates, setTotalCandidates] = useState(0);
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidatesRefreshKey, setCandidatesRefreshKey] = useState(0);
  const [isCandidatesLoading, setIsCandidatesLoading] = useState(true);
  const [candidatesError, setCandidatesError] = useState<string | null>(null);
  const [filterCompany, setFilterCompany] = useState('');
  const [filterAvailability, setFilterAvailability] = useState('');
  const [filterSeniority, setFilterSeniority] = useState('');
  const [filterSkill, setFilterSkill] = useState('');
  const [filterMinYears, setFilterMinYears] = useState('');
  const [filterLocation, setFilterLocation] = useState('');
  const [profileApiData, setProfileApiData] = useState<ApiProfile | null>(null);
  const [isProfileLoading, setIsProfileLoading] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileRefreshKey, setProfileRefreshKey] = useState(0);

  function refreshCandidates() {
    setCandidatePage(1);
    setCandidatesRefreshKey((k) => k + 1);
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setIsLoggingIn(true);
    setLoginError(null);
    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      });
      if (res.status === 401) {
        setLoginError('Invalid email or password.');
        return;
      }
      if (!res.ok) throw new Error(`Login failed: ${res.status}`);
      setIsAuthenticated(true);
      refreshCandidates();
    } catch (err) {
      setLoginError(err instanceof Error ? err.message : 'Login failed.');
    } finally {
      setIsLoggingIn(false);
    }
  }

  async function handleLogout() {
    await fetch('/auth/logout', { method: 'POST' });
    setIsAuthenticated(false);
    setCandidates([]);
    setPage('dashboard');
  }

  useEffect(() => {
    if (!isAuthenticated) return;
    let timerId: ReturnType<typeof setTimeout>;
    function resetTimer() {
      clearTimeout(timerId);
      timerId = setTimeout(() => {
        void fetch('/auth/logout', { method: 'POST' });
        setIsAuthenticated(false);
        setCandidates([]);
        setPage('dashboard');
      }, INACTIVITY_TIMEOUT_MS);
    }
    const events = ['mousemove', 'keydown', 'click', 'touchstart'] as const;
    resetTimer();
    events.forEach((evt) => window.addEventListener(evt, resetTimer));
    return () => {
      clearTimeout(timerId);
      events.forEach((evt) => window.removeEventListener(evt, resetTimer));
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  // Initial mount fetch — determines auth state and loads first page
  useEffect(() => {
    setIsCandidatesLoading(true);
    fetch('/candidates?page=1&limit=50')
      .then((res) => {
        if (res.status === 401) {
          setIsAuthenticated(false);
          setIsCandidatesLoading(false);
          return null;
        }
        if (!res.ok) throw new Error(`Failed to load candidates: ${res.status}`);
        setIsAuthenticated(true);
        return res.json() as Promise<{ total: number; items: ApiCandidate[] }>;
      })
      .then((data) => {
        if (!data) return;
        setCandidates(data.items.map(mapApiCandidate));
        setTotalCandidates(data.total);
        setIsCandidatesLoading(false);
      })
      .catch((err: unknown) => {
        setCandidatesError(err instanceof Error ? err.message : 'Failed to load candidates.');
        setIsCandidatesLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetch when filters, page, or refresh key change (only after auth established)
  useEffect(() => {
    if (!isAuthenticated) return;
    const params = new URLSearchParams({ page: String(candidatePage), limit: '50' });
    if (filterSkill) params.set('skill', filterSkill);
    if (filterMinYears) params.set('min_years', filterMinYears);
    if (filterCompany) params.set('company', filterCompany);
    if (filterAvailability) params.set('availability', filterAvailability);
    if (filterSeniority) params.set('seniority', filterSeniority);
    if (filterLocation) params.set('location', filterLocation);

    let cancelled = false;
    setIsCandidatesLoading(true);
    setCandidatesError(null);
    fetch(`/candidates?${params.toString()}`)
      .then((res) => {
        if (res.status === 401) {
          if (!cancelled) { setIsAuthenticated(false); setIsCandidatesLoading(false); }
          return null;
        }
        if (!res.ok) throw new Error(`Failed to load candidates: ${res.status}`);
        return res.json() as Promise<{ total: number; items: ApiCandidate[] }>;
      })
      .then((data) => {
        if (cancelled || !data) return;
        setCandidates(data.items.map(mapApiCandidate));
        setTotalCandidates(data.total);
        setIsCandidatesLoading(false);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setCandidatesError(err instanceof Error ? err.message : 'Failed to load candidates.');
          setIsCandidatesLoading(false);
        }
      });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterSkill, filterMinYears, filterCompany, filterAvailability, filterSeniority, filterLocation, candidatePage, candidatesRefreshKey]);

  const selected = candidates.find((c) => c.id === selectedId) ?? candidates[0];

  useEffect(() => {
    if (!selected) return;
    setIsProfileLoading(true);
    setProfileApiData(null);
    setProfileError(null);
    fetch(`/profile/${selected.id}`)
      .then((res) => {
        if (res.status === 401) { setIsAuthenticated(false); return null; }
        if (!res.ok) throw new Error(`Failed to load profile: ${res.status}`);
        return res.json() as Promise<ApiProfile>;
      })
      .then((data) => {
        if (!data) return;
        setProfileApiData(data);
        setIsProfileLoading(false);
      })
      .catch((err: unknown) => {
        setProfileError(err instanceof Error ? err.message : 'Failed to load profile.');
        setIsProfileLoading(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id, profileRefreshKey]);

  const uniqueCompanies = useMemo(() => [...new Set(candidates.map((c) => c.company))].sort(), [candidates]);
  const uniqueLocations = useMemo(() => [...new Set(candidates.map((c) => c.location).filter(Boolean))].sort(), [candidates]);

  const filteredCandidates = useMemo(() => {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) return candidates;
    return candidates.filter((candidate) => {
      const haystack = [candidate.name, candidate.role, candidate.company, candidate.location, ...candidate.skills]
        .join(' ')
        .toLowerCase();
      return terms.every((term) => haystack.includes(term) || term.length < 3);
    });
  }, [candidates, query]);

  function toggleShortlist(id: string) {
    setShortlist((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  async function askLLM(question = askInput) {
    if (!question.trim()) return;
    setIsAsking(true);
    setAiError(null);
    setPage('ai');
    try {
      const response = await fetch('/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question,
          contract,
          filters: { query, minScore, shortlistedIds: shortlist },
        }),
      });
      if (!response.ok) throw new Error(`Request failed: ${response.status}`);
      const data = await response.json();
      setAiAnswer(data.answer);
      setAiMatches(data.matches ?? []);
    } catch (error) {
      setAiError(error instanceof Error ? error.message : 'The assistant is unreachable. Check the backend.');
      setAiMatches([]);
    } finally {
      setIsAsking(false);
    }
  }

  if (isAuthenticated === null) {
    return <div className="auth-loading">Loading…</div>;
  }

  if (!isAuthenticated) {
    return (
      <LoginPage
        email={loginEmail}
        setEmail={setLoginEmail}
        password={loginPassword}
        setPassword={setLoginPassword}
        error={loginError}
        isLoading={isLoggingIn}
        onSubmit={handleLogin}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">TG</div>
          <div>
            <strong>TalentGraph</strong>
            <span>CV intelligence</span>
          </div>
        </div>
        <nav>
          {pages.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.key} className={page === item.key ? 'nav-item active' : 'nav-item'} onClick={() => setPage(item.key)}>
                <Icon />
                {item.label}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-note">
          <ShieldCheckIcon />
          <strong>Permission aware</strong>
          <p>AI results only use CVs and fields the current role can access.</p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="crumb">Consulting group / 40 companies / 8,420 profiles</span>
            <h1>CV Talent Intelligence</h1>
          </div>
          <div className="global-search">
            <MagnifyingGlassIcon />
            <input value={query} onChange={(event) => setQuery(event.target.value)} onFocus={() => setPage('search')} />
            <button onClick={() => askLLM('Find the best candidates for this contract')}>
              <SparklesIcon />
              Match
            </button>
          </div>
          <button className="logout-btn" onClick={handleLogout}>Log out</button>
        </header>

        <section className="content">
          {page === 'dashboard' && (
            <Dashboard
              candidates={candidates}
              setPage={setPage}
              contract={contract}
              setContract={setContract}
              askLLM={askLLM}
              setSelectedId={setSelectedId}
            />
          )}
          {page === 'contract' && <ContractIntake contract={contract} setContract={setContract} askLLM={askLLM} />}
          {page === 'search' && (
            <TalentSearch
              query={query}
              setQuery={setQuery}
              minScore={minScore}
              setMinScore={setMinScore}
              filteredCandidates={filteredCandidates}
              totalCandidates={totalCandidates}
              candidatePage={candidatePage}
              setCandidatePage={(p) => setCandidatePage(p)}
              shortlist={shortlist}
              toggleShortlist={toggleShortlist}
              openProfile={(id) => {
                setSelectedId(id);
                setPage('profile');
              }}
              isLoading={isCandidatesLoading}
              error={candidatesError}
              uniqueCompanies={uniqueCompanies}
              uniqueLocations={uniqueLocations}
              filterCompany={filterCompany}
              setFilterCompany={(v) => { setFilterCompany(v); setCandidatePage(1); }}
              filterAvailability={filterAvailability}
              setFilterAvailability={(v) => { setFilterAvailability(v); setCandidatePage(1); }}
              filterSeniority={filterSeniority}
              setFilterSeniority={(v) => { setFilterSeniority(v); setCandidatePage(1); }}
              filterSkill={filterSkill}
              setFilterSkill={(v) => { setFilterSkill(v); setCandidatePage(1); }}
              filterMinYears={filterMinYears}
              setFilterMinYears={(v) => { setFilterMinYears(v); setCandidatePage(1); }}
              filterLocation={filterLocation}
              setFilterLocation={(v) => { setFilterLocation(v); setCandidatePage(1); }}
            />
          )}
          {page === 'ai' && (
            <AIWorkspace
              askInput={askInput}
              setAskInput={setAskInput}
              askLLM={askLLM}
              isAsking={isAsking}
              aiAnswer={aiAnswer}
              aiError={aiError}
              aiMatches={aiMatches}
              candidates={candidates}
            />
          )}
          {page === 'profile' && selected && (
            <Profile
              candidate={selected}
              shortlisted={shortlist.includes(selected.id)}
              toggleShortlist={toggleShortlist}
              cvText={profileApiData?.cv_text ?? null}
              isStale={profileApiData?.is_stale ?? false}
              isProfileLoading={isProfileLoading}
              profileError={profileError}
              profileApiData={profileApiData}
              onProfileSaved={() => {
                refreshCandidates();
                setProfileRefreshKey((k) => k + 1);
              }}
            />
          )}
          {page === 'shortlist' && <Shortlist ids={shortlist} candidates={candidates} toggleShortlist={toggleShortlist} />}
          {page === 'ingestion' && <Ingestion onUploadSuccess={refreshCandidates} />}
          {page === 'companies' && <CompanyDirectory />}
          {page === 'analytics' && <Analytics />}
        </section>
      </main>
    </div>
  );
}

function LoginPage({
  email,
  setEmail,
  password,
  setPassword,
  error,
  isLoading,
  onSubmit,
}: {
  email: string;
  setEmail: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  error: string | null;
  isLoading: boolean;
  onSubmit: (e: React.FormEvent) => void;
}) {
  return (
    <div className="login-page">
      <div className="login-card">
        <div className="login-brand">
          <div className="brand-mark">TG</div>
          <div>
            <strong>TalentGraph</strong>
            <span>CV intelligence</span>
          </div>
        </div>
        <h2>Sign in</h2>
        <form className="login-form" onSubmit={onSubmit}>
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@reply.com"
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </label>
          {error && <div className="login-error"><ExclamationTriangleIcon /> {error}</div>}
          <button type="submit" className="login-submit" disabled={isLoading}>
            {isLoading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}

function Dashboard({
  candidates,
  setPage,
  contract,
  setContract,
  askLLM,
  setSelectedId,
}: {
  candidates: Candidate[];
  setPage: (page: Page) => void;
  contract: string;
  setContract: (value: string) => void;
  askLLM: (question?: string) => void;
  setSelectedId: (id: string) => void;
}) {
  return (
    <div className="stack">
      <div className="metric-grid">
        <Metric icon={UserGroupIcon} label="Indexed employees" value="8,420" detail="+312 this month" />
        <Metric icon={CircleStackIcon} label="CV completeness" value="86%" detail="1,148 need review" />
        <Metric icon={ClipboardDocumentCheckIcon} label="Open contract matches" value="27" detail="8 high priority" />
        <Metric icon={ChatBubbleLeftRightIcon} label="RAG health" value="94%" detail="42 failed parses" />
      </div>

      <div className="two-col">
        <Panel title="Contract intake" action={<button onClick={() => askLLM('Rank the best people for this contract')}>Generate match plan</button>}>
          <textarea className="large-input" value={contract} onChange={(event) => setContract(event.target.value)} />
          <div className="pills">
            {['Azure', 'Healthcare', 'Data migration', 'RAG', 'Governance'].map((tag) => <Pill key={tag}>{tag}</Pill>)}
          </div>
        </Panel>
        <Panel title="Best current matches" action={<button onClick={() => setPage('search')}>View all</button>}>
          <div className="mini-list">
            {candidates.slice(0, 4).map((candidate) => (
              <button
                key={candidate.id}
                onClick={() => {
                  setSelectedId(candidate.id);
                  setPage('profile');
                }}
              >
                <span>
                  <strong>{candidate.name}</strong>
                  <small>{candidate.role}</small>
                </span>
                <b>{candidate.score > 0 ? `${candidate.score}%` : '—'}</b>
              </button>
            ))}
          </div>
        </Panel>
      </div>
      <CompanyCards />
    </div>
  );
}

function ContractIntake({ contract, setContract, askLLM }: { contract: string; setContract: (value: string) => void; askLLM: (question?: string) => void }) {
  return (
    <div className="two-col wide-left">
      <Panel title="Requirement workspace" action={<button onClick={() => askLLM('Extract requirements and recommend candidates')}>Run match</button>}>
        <textarea className="contract-editor" value={contract} onChange={(event) => setContract(event.target.value)} />
        <div className="check-grid">
          {['Start date required', 'Security review needed', 'Proposal evidence required'].map((item) => <CheckToggle key={item} label={item} />)}
        </div>
      </Panel>
      <Panel title="Extracted requirement">
        <div className="field-list">
          {[
            ['Sector', 'Healthcare'],
            ['Cloud', 'Azure'],
            ['Capability', 'Data migration'],
            ['AI', 'RAG assistant'],
            ['Governance', 'Clinical data controls'],
          ].map(([label, value]) => <Field key={label} label={label} value={value} />)}
        </div>
      </Panel>
    </div>
  );
}

function TalentSearch({
  query,
  setQuery,
  minScore,
  setMinScore,
  filteredCandidates,
  totalCandidates,
  candidatePage,
  setCandidatePage,
  shortlist,
  toggleShortlist,
  openProfile,
  isLoading,
  error,
  uniqueCompanies,
  uniqueLocations,
  filterCompany,
  setFilterCompany,
  filterAvailability,
  setFilterAvailability,
  filterSeniority,
  setFilterSeniority,
  filterSkill,
  setFilterSkill,
  filterMinYears,
  setFilterMinYears,
  filterLocation,
  setFilterLocation,
}: {
  query: string;
  setQuery: (value: string) => void;
  minScore: number;
  setMinScore: (value: number) => void;
  filteredCandidates: Candidate[];
  totalCandidates: number;
  candidatePage: number;
  setCandidatePage: (page: number) => void;
  shortlist: string[];
  toggleShortlist: (id: string) => void;
  openProfile: (id: string) => void;
  isLoading: boolean;
  error: string | null;
  uniqueCompanies: string[];
  uniqueLocations: string[];
  filterCompany: string;
  setFilterCompany: (value: string) => void;
  filterAvailability: string;
  setFilterAvailability: (value: string) => void;
  filterSeniority: string;
  setFilterSeniority: (value: string) => void;
  filterSkill: string;
  setFilterSkill: (value: string) => void;
  filterMinYears: string;
  setFilterMinYears: (value: string) => void;
  filterLocation: string;
  setFilterLocation: (value: string) => void;
}) {
  const LIMIT = 50;
  const totalPages = Math.max(1, Math.ceil(totalCandidates / LIMIT));

  return (
    <div className="stack">
      <Panel title="Search controls">
        <div className="filters">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search by name, skill, location…" />
          <input value={filterSkill} onChange={(event) => setFilterSkill(event.target.value)} placeholder="Skill (e.g. Python)" />
          <input
            type="number"
            value={filterMinYears}
            onChange={(event) => setFilterMinYears(event.target.value)}
            placeholder="Min years"
            min={0}
            style={{ width: '100px' }}
          />
          <select value={filterLocation} onChange={(event) => setFilterLocation(event.target.value)}>
            <option value="">Any location</option>
            {uniqueLocations.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
          <select value={filterCompany} onChange={(event) => setFilterCompany(event.target.value)}>
            <option value="">All companies</option>
            {uniqueCompanies.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={filterAvailability} onChange={(event) => setFilterAvailability(event.target.value)}>
            <option value="">Any availability</option>
            <option value="available">Available now</option>
            <option value="on_bench">On bench</option>
            <option value="rolling_off">Rolling off</option>
            <option value="on_project">On project</option>
          </select>
          <select value={filterSeniority} onChange={(event) => setFilterSeniority(event.target.value)}>
            <option value="">Any seniority</option>
            <option value="junior">Junior</option>
            <option value="mid">Mid</option>
            <option value="senior">Senior</option>
            <option value="principal">Principal</option>
          </select>
          <label>Minimum match {minScore}%<input type="range" min={50} max={95} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></label>
        </div>
      </Panel>
      {isLoading ? (
        <Panel title="Loading candidates…">
          <p className="body-copy">Fetching talent data from the server…</p>
        </Panel>
      ) : error ? (
        <Panel title="Could not load candidates">
          <Warning>{error}</Warning>
        </Panel>
      ) : totalCandidates === 0 ? (
        <Panel title="0 talent results">
          <p className="body-copy">No candidates match the current filters. Try adjusting your search.</p>
        </Panel>
      ) : (
        <Panel title={`${totalCandidates} talent results`} action={<button><AdjustmentsHorizontalIcon /> Columns</button>}>
          <CandidateTable candidates={filteredCandidates} shortlist={shortlist} toggleShortlist={toggleShortlist} openProfile={openProfile} />
          {totalPages > 1 && (
            <div className="pagination">
              <button disabled={candidatePage <= 1} onClick={() => setCandidatePage(candidatePage - 1)}>Previous</button>
              <span>Page {candidatePage} of {totalPages}</span>
              <button disabled={candidatePage >= totalPages} onClick={() => setCandidatePage(candidatePage + 1)}>Next</button>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}

function AIWorkspace({
  askInput,
  setAskInput,
  askLLM,
  isAsking,
  aiAnswer,
  aiError,
  aiMatches,
  candidates,
}: {
  askInput: string;
  setAskInput: (value: string) => void;
  askLLM: (question?: string) => void;
  isAsking: boolean;
  aiAnswer: string;
  aiError: string | null;
  aiMatches: AskMatch[];
  candidates: Candidate[];
}) {
  return (
    <div className="two-col wide-left">
      <Panel title="AI match workspace" action={<span className="status-pill">Backend /ask</span>}>
        <div className="chat-window">
          <div className="bubble user">Find people for a healthcare Azure data migration with RAG experience.</div>
          {isAsking ? (
            <div className="bubble assistant">Thinking…</div>
          ) : aiError ? (
            <Warning>{aiError}</Warning>
          ) : (
            <div className="bubble assistant">{aiAnswer}</div>
          )}
        </div>
        <div className="ask-bar">
          <input value={askInput} onChange={(event) => setAskInput(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && askLLM()} />
          <button disabled={isAsking} onClick={() => askLLM()}>
            <PaperAirplaneIcon />
            {isAsking ? 'Asking…' : 'Ask'}
          </button>
        </div>
      </Panel>
      <Panel title="Ranked recommendation">
        <div className="mini-list">
          {(aiMatches.length
            ? aiMatches
            : candidates.slice(0, 3).map<AskMatch>((c) => ({ name: c.name, role: c.role, score: c.score || undefined, evidence: c.evidence[0] }))
          ).map((match) => (
            <div key={match.name} className="match-card">
              <strong>{match.name}</strong>
              <small>{match.role}</small>
              <p>{match.evidence ?? 'Strong CV evidence for this requirement.'}</p>
              <b>{match.score != null ? `${match.score}%` : '—'}</b>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Profile({
  candidate,
  shortlisted,
  toggleShortlist,
  cvText,
  isStale,
  isProfileLoading,
  profileError,
  profileApiData,
  onProfileSaved,
}: {
  candidate: Candidate;
  shortlisted: boolean;
  toggleShortlist: (id: string) => void;
  cvText: string | null;
  isStale: boolean;
  isProfileLoading: boolean;
  profileError: string | null;
  profileApiData: ApiProfile | null;
  onProfileSaved: () => void;
}) {
  const [tab, setTab] = useState('Overview');
  const [editFields, setEditFields] = useState<ProfileEditFields | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (profileApiData) {
      setEditFields({
        name: profileApiData.name,
        reply_company: profileApiData.reply_company,
        location: profileApiData.location,
        seniority: profileApiData.seniority,
        availability_status: profileApiData.availability_status,
        current_project_name: profileApiData.current_project_name ?? '',
        skills: profileApiData.skills.map((s) => ({ ...s })),
      });
      setSaveError(null);
      setSaveSuccess(false);
    }
  }, [profileApiData]);

  async function handleSave() {
    if (!editFields) return;
    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);
    try {
      const response = await fetch(`/profile/${candidate.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...editFields,
          current_project_name: editFields.current_project_name || null,
        }),
      });
      if (!response.ok) {
        const detail = await response.json().then((d: { detail?: string }) => d.detail).catch(() => null);
        throw new Error(detail ?? `Save failed: ${response.status}`);
      }
      setSaveSuccess(true);
      onProfileSaved();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Save failed.');
    } finally {
      setIsSaving(false);
    }
  }

  const evidenceItems = cvText
    ? cvText.split('. ').map((s) => s.trim()).filter(Boolean)
    : [];
  const currentCompleteness = profileApiData?.completeness ?? candidate.completeness;
  const currentGaps = profileApiData?.gaps ?? candidate.gaps;
  return (
    <div className="two-col">
      <Panel title={candidate.name} action={<button onClick={() => toggleShortlist(candidate.id)}>{shortlisted ? 'Shortlisted' : 'Add to shortlist'}</button>}>
        <p className="subhead">{candidate.role} - {candidate.company} - {candidate.location}</p>
        {isStale && <Warning>CV not updated in over 6 months — may be out of date.</Warning>}
        <div className="profile-metrics">
          <Score label="Match" value={candidate.score} />
          <Score label="Confidence" value={candidate.confidence} />
          <Score label="Completeness" value={currentCompleteness} />
        </div>
        <div className="pills">{candidate.skills.map((skill) => <Pill key={skill}>{skill}</Pill>)}</div>
      </Panel>
      <Panel title="Profile detail">
        <div className="tabs">{['Overview', 'CV evidence', 'Gaps', 'Edit'].map((item) => <button key={item} className={tab === item ? 'active-tab' : ''} onClick={() => setTab(item)}>{item}</button>)}</div>
        {tab === 'Overview' && (
          <div className="field-list">
            <Field label="Seniority" value={candidate.seniority} />
            <Field label="Availability" value={candidate.availability} />
            <Field label="Company" value={candidate.company} />
            <Field label="Location" value={candidate.location} />
          </div>
        )}
        {tab === 'CV evidence' && (
          isProfileLoading
            ? <p className="body-copy">Loading CV evidence…</p>
            : profileError
              ? <Warning>{profileError}</Warning>
              : evidenceItems.length
                ? evidenceItems.map((item, i) => <Evidence key={i}>{item}</Evidence>)
                : <p className="body-copy">No CV evidence indexed yet.</p>
        )}
        {tab === 'Gaps' && (currentGaps.length ? currentGaps.map((item) => <Warning key={item}>{item}</Warning>) : <p className="body-copy">No gaps recorded.</p>)}
        {tab === 'Edit' && (
          <ProfileEditForm
            fields={editFields}
            setFields={setEditFields}
            onSave={handleSave}
            isSaving={isSaving}
            saveError={saveError}
            saveSuccess={saveSuccess}
            isLoading={isProfileLoading}
          />
        )}
      </Panel>
    </div>
  );
}

function ProfileEditForm({
  fields,
  setFields,
  onSave,
  isSaving,
  saveError,
  saveSuccess,
  isLoading,
}: {
  fields: ProfileEditFields | null;
  setFields: (fields: ProfileEditFields) => void;
  onSave: () => void;
  isSaving: boolean;
  saveError: string | null;
  saveSuccess: boolean;
  isLoading: boolean;
}) {
  if (isLoading || !fields) return <p className="body-copy">Loading profile data…</p>;

  function updateField<K extends keyof ProfileEditFields>(key: K, value: ProfileEditFields[K]) {
    setFields({ ...fields!, [key]: value });
  }

  function updateSkill(index: number, key: 'skill' | 'years_experience', value: string | number) {
    const newSkills = fields!.skills.map((s, i) => (i === index ? { ...s, [key]: value } : s));
    updateField('skills', newSkills);
  }

  return (
    <div className="field-list">
      <div className="field">
        <span>Name</span>
        <input value={fields.name} onChange={(e) => updateField('name', e.target.value)} />
      </div>
      <div className="field">
        <span>Company</span>
        <input value={fields.reply_company} onChange={(e) => updateField('reply_company', e.target.value)} />
      </div>
      <div className="field">
        <span>Location</span>
        <input value={fields.location} onChange={(e) => updateField('location', e.target.value)} />
      </div>
      <div className="field">
        <span>Seniority</span>
        <select value={fields.seniority} onChange={(e) => updateField('seniority', e.target.value)}>
          <option value="junior">Junior</option>
          <option value="mid">Mid</option>
          <option value="senior">Senior</option>
          <option value="principal">Principal</option>
        </select>
      </div>
      <div className="field">
        <span>Availability</span>
        <select value={fields.availability_status} onChange={(e) => updateField('availability_status', e.target.value)}>
          <option value="available">Available now</option>
          <option value="on_project">On project</option>
          <option value="on_bench">On bench</option>
          <option value="rolling_off">Rolling off</option>
        </select>
      </div>
      <div className="field">
        <span>Current project</span>
        <input value={fields.current_project_name} onChange={(e) => updateField('current_project_name', e.target.value)} placeholder="None" />
      </div>
      <div>
        <span className="field"><span>Skills</span></span>
        {fields.skills.map((s, i) => (
          <div key={i} className="filters" style={{ marginTop: '4px' }}>
            <input value={s.skill} onChange={(e) => updateSkill(i, 'skill', e.target.value)} placeholder="Skill" />
            <input
              type="number"
              value={s.years_experience}
              min={0}
              step={0.5}
              onChange={(e) => updateSkill(i, 'years_experience', Number(e.target.value))}
              style={{ width: '80px' }}
              placeholder="Years"
            />
            <button onClick={() => updateField('skills', fields.skills.filter((_, j) => j !== i))}>Remove</button>
          </div>
        ))}
        <button style={{ marginTop: '8px' }} onClick={() => updateField('skills', [...fields.skills, { skill: '', years_experience: 0 }])}>Add skill</button>
      </div>
      {saveSuccess && <Evidence>Profile saved successfully.</Evidence>}
      {saveError && <Warning>{saveError}</Warning>}
      <button disabled={isSaving} onClick={onSave}>{isSaving ? 'Saving…' : 'Save changes'}</button>
    </div>
  );
}

function Shortlist({ ids, candidates, toggleShortlist }: { ids: string[]; candidates: Candidate[]; toggleShortlist: (id: string) => void }) {
  const shortlisted = candidates.filter((candidate) => ids.includes(candidate.id));
  const [rationales, setRationales] = useState<Record<string, string>>({});
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  function setRationale(id: string, value: string) {
    setRationales((prev) => ({ ...prev, [id]: value }));
  }

  async function handleExport() {
    if (shortlisted.length === 0) return;
    setIsExporting(true);
    setExportError(null);
    try {
      const profilesData = await Promise.all(
        shortlisted.map(async (candidate) => {
          const res = await fetch(`/profile/${candidate.id}`);
          if (!res.ok) return null;
          return res.json() as Promise<ApiProfile>;
        })
      );

      const pack = shortlisted.map((candidate, i) => {
        const profile = profilesData[i];
        const cvText = profile?.cv_text ?? '';
        const evidence = cvText
          ? cvText.split('. ').map((s: string) => s.trim()).filter(Boolean).slice(0, 5)
          : [];
        return {
          name: candidate.name,
          role: candidate.role,
          score: candidate.score,
          skills: candidate.skills,
          evidence,
          gaps: candidate.gaps,
          rationale: rationales[candidate.id] ?? '',
        };
      });

      const blob = new Blob(
        [JSON.stringify({ candidates: pack, generated_at: new Date().toISOString() }, null, 2)],
        { type: 'application/json' }
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'proposal-pack.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Export failed.');
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <div className="stack">
      <Panel
        title="Shortlist builder"
        action={
          <button onClick={handleExport} disabled={isExporting || shortlisted.length === 0}>
            <ArrowDownTrayIcon /> {isExporting ? 'Generating…' : 'Export pack'}
          </button>
        }
      >
        {exportError && <Warning>{exportError}</Warning>}
        {shortlisted.length === 0 ? (
          <p className="body-copy">No candidates shortlisted yet. Add candidates from the Talent Search page.</p>
        ) : (
          <div className="shortlist-grid">
            {shortlisted.map((candidate) => (
              <div className="shortlist-card" key={candidate.id}>
                <button className="remove" onClick={() => toggleShortlist(candidate.id)}>Remove</button>
                <strong>{candidate.name}</strong>
                <small>{candidate.role}</small>
                <Score label="Match" value={candidate.score} />
                <textarea
                  placeholder="Proposal rationale"
                  value={rationales[candidate.id] ?? ''}
                  onChange={(e) => setRationale(candidate.id, e.target.value)}
                />
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}

type IngestExtracted = {
  name: string;
  reply_company: string;
  location: string;
  seniority: string;
  availability_status: string;
  current_project_name: string | null;
  skills: Array<{ skill: string; years_experience: number }>;
};

type IngestResult = {
  success: boolean;
  filename: string;
  extracted: IngestExtracted;
};

type IngestStatusRow = {
  company: string;
  total: number;
  indexed: number;
  failed: number;
  stale: number;
  status: string;
};

function Ingestion({ onUploadSuccess }: { onUploadSuccess: () => void }) {
  const [issuesOnly, setIssuesOnly] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<IngestResult | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [statusRows, setStatusRows] = useState<IngestStatusRow[]>([]);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);

  async function fetchStatus() {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const res = await fetch('/ingest/status');
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const data = await res.json() as IngestStatusRow[];
      setStatusRows(data);
    } catch (err) {
      setStatusError(err instanceof Error ? err.message : 'Failed to load ingestion status.');
    } finally {
      setStatusLoading(false);
    }
  }

  useEffect(() => {
    fetchStatus();
  }, []);

  const tableRows = statusRows.map((r) => [r.company, r.total, r.indexed, r.failed, r.stale, r.status]);
  const visible = issuesOnly ? tableRows.filter((row) => Number(row[3]) > 3 || Number(row[4]) > 12) : tableRows;

  async function handleUpload() {
    if (!selectedFile) return;
    setIsUploading(true);
    setUploadResult(null);
    setUploadError(null);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      const response = await fetch('/ingest', { method: 'POST', body: formData });
      if (!response.ok) {
        const detail = await response.json().then((d: { detail?: string }) => d.detail).catch(() => null);
        throw new Error(detail ?? `Upload failed: ${response.status}`);
      }
      const data = await response.json() as IngestResult;
      setUploadResult(data);
      onUploadSuccess();
      fetchStatus();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed.');
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <div className="stack">
      <div className="metric-grid">
        <Metric icon={CircleStackIcon} label="Parsed CVs" value="8,420" detail="94% indexed" />
        <Metric icon={ExclamationTriangleIcon} label="Needs review" value="1,148" detail="Stale or failed" />
        <Metric icon={ArrowPathIcon} label="Skill aliases" value="612" detail="Mapped to taxonomy" />
      </div>
      <Panel title="Upload CV">
        <div className="filters">
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(event) => {
              setSelectedFile(event.target.files?.[0] ?? null);
              setUploadResult(null);
              setUploadError(null);
            }}
          />
          <button disabled={!selectedFile || isUploading} onClick={handleUpload}>
            {isUploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
        {uploadResult && (
          <div>
            <Evidence>Uploaded {uploadResult.filename} — extraction preview below.</Evidence>
            <div className="field-list">
              <Field label="Name" value={uploadResult.extracted.name} />
              <Field label="Company" value={uploadResult.extracted.reply_company} />
              <Field label="Location" value={uploadResult.extracted.location} />
              <Field label="Seniority" value={uploadResult.extracted.seniority} />
              <Field label="Availability" value={uploadResult.extracted.availability_status} />
              {uploadResult.extracted.current_project_name && (
                <Field label="Current project" value={uploadResult.extracted.current_project_name} />
              )}
            </div>
            <div className="pills">
              {uploadResult.extracted.skills.map((s) => (
                <Pill key={s.skill}>{s.skill} ({s.years_experience}y)</Pill>
              ))}
            </div>
          </div>
        )}
        {uploadError && <Warning>{uploadError}</Warning>}
      </Panel>
      <Panel title="CV ingestion health" action={<label className="inline-check"><input type="checkbox" checked={issuesOnly} onChange={(event) => setIssuesOnly(event.target.checked)} /> Issues only</label>}>
        {statusLoading && <Evidence>Loading ingestion status…</Evidence>}
        {statusError && <Warning>{statusError}</Warning>}
        {!statusLoading && !statusError && <DataTable headers={['Source', 'Total', 'Indexed', 'Failed', 'Stale', 'Status']} rows={visible} />}
      </Panel>
    </div>
  );
}

type ApiCompany = {
  name: string;
  employee_count: number;
  indexed_cv_count: number;
  completeness_score: number;
};

function CompanyDirectory() {
  const [apiCompanies, setApiCompanies] = useState<ApiCompany[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedName, setSelectedName] = useState<string | null>(null);

  useEffect(() => {
    fetch('/companies')
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load companies: ${res.status}`);
        return res.json() as Promise<ApiCompany[]>;
      })
      .then((data) => {
        setApiCompanies(data);
        if (data.length > 0) setSelectedName(data[0].name);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load companies.');
        setIsLoading(false);
      });
  }, []);

  const selected = apiCompanies.find((c) => c.name === selectedName) ?? apiCompanies[0] ?? null;

  if (isLoading) {
    return (
      <div className="two-col wide-left">
        <Panel title="Company directory">
          <p className="body-copy">Loading company data…</p>
        </Panel>
      </div>
    );
  }

  if (error) {
    return (
      <div className="two-col wide-left">
        <Panel title="Company directory">
          <Warning>{error}</Warning>
        </Panel>
      </div>
    );
  }

  return (
    <div className="two-col wide-left">
      <Panel title="Company directory">
        <div className="company-grid">
          {apiCompanies.map((company) => (
            <button
              key={company.name}
              className={selected?.name === company.name ? 'company-card selected' : 'company-card'}
              onClick={() => setSelectedName(company.name)}
            >
              <strong>{company.name}</strong>
              <small>{company.employee_count} employees</small>
              <Score label="Complete" value={company.completeness_score} />
            </button>
          ))}
        </div>
      </Panel>
      {selected && (
        <Panel title={selected.name}>
          <Field label="Employees" value={String(selected.employee_count)} />
          <Field label="Indexed CVs" value={String(selected.indexed_cv_count)} />
          <Field label="Completeness" value={`${selected.completeness_score}%`} />
        </Panel>
      )}
    </div>
  );
}

type ApiSkillAnalytics = {
  skill: string;
  supply_pct: number;
  demand_pct: number;
};

function Analytics() {
  const [apiSkills, setApiSkills] = useState<ApiSkillAnalytics[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/analytics/skills')
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load analytics: ${res.status}`);
        return res.json() as Promise<ApiSkillAnalytics[]>;
      })
      .then((data) => {
        setApiSkills(data);
        setIsLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load analytics.');
        setIsLoading(false);
      });
  }, []);

  if (isLoading) {
    return (
      <div className="two-col">
        <Panel title="Demand vs supply">
          <p className="body-copy">Loading analytics data…</p>
        </Panel>
      </div>
    );
  }

  if (error) {
    return (
      <div className="two-col">
        <Panel title="Demand vs supply">
          <Warning>{error}</Warning>
        </Panel>
      </div>
    );
  }

  return (
    <div className="two-col">
      <Panel title="Demand vs supply">
        <div className="bar-list">
          {apiSkills.map((item) => (
            <div key={item.skill}>
              <div className="bar-label">
                <strong>{item.skill}</strong>
                <span>Demand {item.demand_pct}% / supply {item.supply_pct}%</span>
              </div>
              <Bar value={item.demand_pct} tone="cyan" />
              <Bar value={item.supply_pct} tone="slate" />
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Gap register">
        <DataTable
          headers={['Capability', 'Demand', 'Supply']}
          rows={apiSkills.map((item) => [item.skill, `${item.demand_pct}%`, `${item.supply_pct}%`])}
        />
        <Evidence>Demand reflects skill utilisation on active projects; supply reflects share of indexed workforce with each skill.</Evidence>
      </Panel>
    </div>
  );
}

function CandidateTable({ candidates: rows, shortlist, toggleShortlist, openProfile }: { candidates: Candidate[]; shortlist: string[]; toggleShortlist: (id: string) => void; openProfile: (id: string) => void }) {
  if (rows.length === 0) {
    return <p className="body-copy">No candidates match the current search. Try adjusting your query.</p>;
  }
  return (
    <div className="candidate-table">
      {rows.map((candidate) => (
        <div className="candidate-row" key={candidate.id}>
          <button className="candidate-main" onClick={() => openProfile(candidate.id)}>
            <strong>{candidate.name}{isCandidateStale(candidate.last_updated) && <span className="stale-badge">Stale</span>}</strong>
            <small>{candidate.role} - {candidate.company}</small>
          </button>
          <div className="pills">{candidate.skills.slice(0, 4).map((skill) => <Pill key={skill}>{skill}</Pill>)}</div>
          <Score label="Match" value={candidate.score} />
          <button onClick={() => toggleShortlist(candidate.id)}>{shortlist.includes(candidate.id) ? 'Shortlisted' : 'Add'}</button>
        </div>
      ))}
    </div>
  );
}

function CompanyCards() {
  return (
    <Panel title="Company coverage">
      <div className="company-grid">
        {companies.slice(0, 5).map((company) => (
          <div className="company-card" key={company[0]}>
            <strong>{company[0]}</strong>
            <small>{company[2]} employees</small>
            <Score label="Complete" value={company[3]} />
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Panel({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2>{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Metric({ icon: Icon, label, value, detail }: { icon: typeof UserGroupIcon; label: string; value: string; detail: string; }) {
  return (
    <div className="metric-card">
      <div><span>{label}</span><Icon /></div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function Pill({ children }: { children: ReactNode }) {
  return <span className="pill">{children}</span>;
}

function Field({ label, value }: { label: string; value: string }) {
  return <div className="field"><span>{label}</span><strong>{value}</strong></div>;
}

function Score({ label, value }: { label: string; value: number }) {
  return (
    <div className="score">
      <div><span>{label}</span><strong>{value > 0 ? `${value}%` : '—'}</strong></div>
      <Bar value={value} tone={value >= 90 ? 'green' : value >= 80 ? 'cyan' : 'amber'} />
    </div>
  );
}

function Bar({ value, tone }: { value: number; tone: 'cyan' | 'green' | 'amber' | 'slate' }) {
  return <div className="bar"><div className={`bar-fill ${tone}`} style={{ width: `${value}%` }} /></div>;
}

function Evidence({ children }: { children: ReactNode }) {
  return <div className="evidence"><CheckCircleIcon /> {children}</div>;
}

function Warning({ children }: { children: ReactNode }) {
  return <div className="warning"><ExclamationTriangleIcon /> {children}</div>;
}

function CheckToggle({ label }: { label: string }) {
  return <label className="check-toggle"><span>{label}</span><input type="checkbox" /></label>;
}

function DataTable({ headers, rows }: { headers: string[]; rows: Array<Array<string | number>> }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>{row.map((cell, cellIndex) => <td key={`${index}-${cellIndex}`}>{cell}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
