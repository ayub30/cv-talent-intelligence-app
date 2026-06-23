import { useMemo, useState, type ReactNode } from 'react';
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

type Candidate = {
  id: number;
  name: string;
  role: string;
  company: string;
  location: string;
  score: number;
  confidence: number;
  completeness: number;
  availability: string;
  clearance: string;
  skills: string[];
  evidence: string[];
  gaps: string[];
};

type AskMatch = {
  name: string;
  role?: string;
  score?: number;
  evidence?: string;
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

const candidates: Candidate[] = [
  {
    id: 1,
    name: 'Maya Okafor',
    role: 'Principal Data Engineer',
    company: 'Northstar Digital',
    location: 'London',
    score: 94,
    confidence: 91,
    completeness: 96,
    availability: '2 weeks',
    clearance: 'BPSS',
    skills: ['Azure', 'Databricks', 'Python', 'FHIR', 'Data migration', 'RAG'],
    evidence: [
      'Led Azure Databricks migration for 18 clinical datasets across 4 trusts.',
      'Built retrieval pipelines for policy and patient pathway knowledge bases.',
      'Owned data quality controls, lineage, and stakeholder reporting.',
    ],
    gaps: ['No explicit SC clearance recorded.'],
  },
  {
    id: 2,
    name: 'Daniel Hughes',
    role: 'Senior Cloud Architect',
    company: 'Atlas Advisory',
    location: 'Manchester',
    score: 89,
    confidence: 87,
    completeness: 88,
    availability: 'Available now',
    clearance: 'SC',
    skills: ['Azure', 'Terraform', 'Kubernetes', 'Security architecture', 'FinOps'],
    evidence: [
      'Designed secure landing zones for regulated workloads.',
      'Delivered Terraform module library used by nine delivery teams.',
    ],
    gaps: ['Healthcare experience is adjacent, not direct.'],
  },
  {
    id: 3,
    name: 'Aisha Rahman',
    role: 'AI Product Lead',
    company: 'Civitas Systems',
    location: 'Birmingham',
    score: 86,
    confidence: 82,
    completeness: 91,
    availability: '4 weeks',
    clearance: 'None',
    skills: ['RAG', 'LLM evaluation', 'Governance', 'Prompt design', 'Azure AI'],
    evidence: [
      'Ran LLM evaluation framework across retrieval quality and hallucination risk.',
      'Shipped clinician-facing assistant prototype with cited policy sources.',
    ],
    gaps: ['Needs technical pairing for platform implementation.'],
  },
  {
    id: 4,
    name: 'Elena Varga',
    role: 'Cyber Security Consultant',
    company: 'Fortis Risk',
    location: 'Remote',
    score: 82,
    confidence: 80,
    completeness: 93,
    availability: 'Available now',
    clearance: 'SC',
    skills: ['ISO 27001', 'Risk assessment', 'NIST', 'Azure security'],
    evidence: ['Assessed Azure security controls for sensitive health records platform.'],
    gaps: ['Less direct experience with data engineering delivery.'],
  },
  {
    id: 5,
    name: 'Tom Spencer',
    role: 'Programme Delivery Director',
    company: 'Redwood Consulting',
    location: 'Edinburgh',
    score: 78,
    confidence: 75,
    completeness: 84,
    availability: 'Allocated',
    clearance: 'SC',
    skills: ['Transformation', 'PMO', 'Healthcare ops', 'Data strategy'],
    evidence: ['Recovered delayed healthcare transformation portfolio across six workstreams.'],
    gaps: ['CV is stale and lacks recent technical delivery detail.'],
  },
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

const defaultContract =
  'Healthcare client needs a senior Azure data engineering team to migrate clinical datasets, build governed analytics, and support an AI knowledge assistant with cited retrieval.';

export function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [selectedId, setSelectedId] = useState(1);
  const [query, setQuery] = useState('Azure healthcare RAG');
  const [minScore, setMinScore] = useState(75);
  const [contract, setContract] = useState(defaultContract);
  const [shortlist, setShortlist] = useState<number[]>([1, 2, 3]);
  const [askInput, setAskInput] = useState('Find the best team for this contract');
  const [aiAnswer, setAiAnswer] = useState('Ask the assistant to rank people using the backend /ask route.');
  const [aiMatches, setAiMatches] = useState<AskMatch[]>([]);
  const [isAsking, setIsAsking] = useState(false);

  const selected = candidates.find((candidate) => candidate.id === selectedId) ?? candidates[0];
  const filteredCandidates = useMemo(() => {
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    return candidates.filter((candidate) => {
      const haystack = [candidate.name, candidate.role, candidate.company, candidate.location, ...candidate.skills].join(' ').toLowerCase();
      return candidate.score >= minScore && terms.every((term) => haystack.includes(term) || term.length < 3);
    });
  }, [minScore, query]);

  function toggleShortlist(id: number) {
    setShortlist((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  async function askLLM(question = askInput) {
    if (!question.trim()) return;
    setIsAsking(true);
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
      setAiAnswer(error instanceof Error ? error.message : 'The assistant request failed.');
      setAiMatches([]);
    } finally {
      setIsAsking(false);
    }
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
        </header>

        <section className="content">
          {page === 'dashboard' && (
            <Dashboard
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
              shortlist={shortlist}
              toggleShortlist={toggleShortlist}
              openProfile={(id) => {
                setSelectedId(id);
                setPage('profile');
              }}
            />
          )}
          {page === 'ai' && (
            <AIWorkspace
              askInput={askInput}
              setAskInput={setAskInput}
              askLLM={askLLM}
              isAsking={isAsking}
              aiAnswer={aiAnswer}
              aiMatches={aiMatches}
            />
          )}
          {page === 'profile' && <Profile candidate={selected} shortlisted={shortlist.includes(selected.id)} toggleShortlist={toggleShortlist} />}
          {page === 'shortlist' && <Shortlist ids={shortlist} toggleShortlist={toggleShortlist} />}
          {page === 'ingestion' && <Ingestion />}
          {page === 'companies' && <CompanyDirectory />}
          {page === 'analytics' && <Analytics />}
        </section>
      </main>
    </div>
  );
}

function Dashboard({
  setPage,
  contract,
  setContract,
  askLLM,
  setSelectedId,
}: {
  setPage: (page: Page) => void;
  contract: string;
  setContract: (value: string) => void;
  askLLM: (question?: string) => void;
  setSelectedId: (id: number) => void;
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
                <b>{candidate.score}%</b>
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
  shortlist,
  toggleShortlist,
  openProfile,
}: {
  query: string;
  setQuery: (value: string) => void;
  minScore: number;
  setMinScore: (value: number) => void;
  filteredCandidates: Candidate[];
  shortlist: number[];
  toggleShortlist: (id: number) => void;
  openProfile: (id: number) => void;
}) {
  return (
    <div className="stack">
      <Panel title="Search controls">
        <div className="filters">
          <input value={query} onChange={(event) => setQuery(event.target.value)} />
          <select><option>All companies</option><option>Northstar Digital</option><option>Atlas Advisory</option></select>
          <select><option>Any availability</option><option>Available now</option><option>2 weeks</option></select>
          <label>Minimum match {minScore}%<input type="range" min={50} max={95} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} /></label>
        </div>
      </Panel>
      <Panel title={`${filteredCandidates.length} talent results`} action={<button><AdjustmentsHorizontalIcon /> Columns</button>}>
        <CandidateTable candidates={filteredCandidates} shortlist={shortlist} toggleShortlist={toggleShortlist} openProfile={openProfile} />
      </Panel>
    </div>
  );
}

function AIWorkspace({
  askInput,
  setAskInput,
  askLLM,
  isAsking,
  aiAnswer,
  aiMatches,
}: {
  askInput: string;
  setAskInput: (value: string) => void;
  askLLM: (question?: string) => void;
  isAsking: boolean;
  aiAnswer: string;
  aiMatches: AskMatch[];
}) {
  return (
    <div className="two-col wide-left">
      <Panel title="AI match workspace" action={<span className="status-pill">Backend /ask</span>}>
        <div className="chat-window">
          <div className="bubble user">Find people for a healthcare Azure data migration with RAG experience.</div>
          <div className="bubble assistant">{aiAnswer}</div>
        </div>
        <div className="ask-bar">
          <input value={askInput} onChange={(event) => setAskInput(event.target.value)} onKeyDown={(event) => event.key === 'Enter' && askLLM()} />
          <button disabled={isAsking} onClick={() => askLLM()}>
            <PaperAirplaneIcon />
            {isAsking ? 'Asking' : 'Ask'}
          </button>
        </div>
      </Panel>
      <Panel title="Ranked recommendation">
        <div className="mini-list">
          {(aiMatches.length
            ? aiMatches
            : candidates.slice(0, 3).map<AskMatch>((c) => ({ name: c.name, role: c.role, score: c.score, evidence: c.evidence[0] }))
          ).map((match) => (
            <div key={match.name} className="match-card">
              <strong>{match.name}</strong>
              <small>{match.role}</small>
              <p>{match.evidence ?? 'Strong CV evidence for this requirement.'}</p>
              <b>{match.score ?? 90}%</b>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Profile({ candidate, shortlisted, toggleShortlist }: { candidate: Candidate; shortlisted: boolean; toggleShortlist: (id: number) => void }) {
  const [tab, setTab] = useState('Overview');
  return (
    <div className="two-col">
      <Panel title={candidate.name} action={<button onClick={() => toggleShortlist(candidate.id)}>{shortlisted ? 'Shortlisted' : 'Add to shortlist'}</button>}>
        <p className="subhead">{candidate.role} - {candidate.company} - {candidate.location}</p>
        <div className="profile-metrics">
          <Score label="Match" value={candidate.score} />
          <Score label="Confidence" value={candidate.confidence} />
          <Score label="Completeness" value={candidate.completeness} />
        </div>
        <div className="pills">{candidate.skills.map((skill) => <Pill key={skill}>{skill}</Pill>)}</div>
      </Panel>
      <Panel title="Profile detail">
        <div className="tabs">{['Overview', 'CV evidence', 'Gaps'].map((item) => <button key={item} className={tab === item ? 'active-tab' : ''} onClick={() => setTab(item)}>{item}</button>)}</div>
        {tab === 'Overview' && <p className="body-copy">Best role: technical lead for data platform and retrieval pipeline implementation.</p>}
        {tab === 'CV evidence' && candidate.evidence.map((item) => <Evidence key={item}>{item}</Evidence>)}
        {tab === 'Gaps' && candidate.gaps.map((item) => <Warning key={item}>{item}</Warning>)}
      </Panel>
    </div>
  );
}

function Shortlist({ ids, toggleShortlist }: { ids: number[]; toggleShortlist: (id: number) => void }) {
  const [exported, setExported] = useState(false);
  const shortlisted = candidates.filter((candidate) => ids.includes(candidate.id));
  return (
    <div className="stack">
      <Panel title="Shortlist builder" action={<button onClick={() => setExported(true)}><ArrowDownTrayIcon /> Export pack</button>}>
        {exported && <Evidence>Proposal pack queued: CV summaries, AI evidence, gaps, and approval notes.</Evidence>}
        <div className="shortlist-grid">
          {shortlisted.map((candidate) => (
            <div className="shortlist-card" key={candidate.id}>
              <button className="remove" onClick={() => toggleShortlist(candidate.id)}>Remove</button>
              <strong>{candidate.name}</strong>
              <small>{candidate.role}</small>
              <Score label="Match" value={candidate.score} />
              <textarea placeholder="Proposal rationale" defaultValue={candidate.id === 1 ? 'Best technical lead for delivery.' : ''} />
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

function Ingestion() {
  const [issuesOnly, setIssuesOnly] = useState(false);
  const rows = [
    ['Northstar Digital CV folder', 284, 268, 4, 12, 'Healthy'],
    ['Atlas Advisory HRIS export', 241, 221, 7, 13, 'Review'],
    ['Redwood Consulting SharePoint', 302, 244, 18, 40, 'At risk'],
    ['Fortis Risk CV pack', 138, 132, 1, 5, 'Healthy'],
  ];
  const visible = issuesOnly ? rows.filter((row) => Number(row[3]) > 3 || Number(row[4]) > 12) : rows;
  return (
    <div className="stack">
      <div className="metric-grid">
        <Metric icon={CircleStackIcon} label="Parsed CVs" value="8,420" detail="94% indexed" />
        <Metric icon={ExclamationTriangleIcon} label="Needs review" value="1,148" detail="Stale or failed" />
        <Metric icon={ArrowPathIcon} label="Skill aliases" value="612" detail="Mapped to taxonomy" />
      </div>
      <Panel title="CV ingestion health" action={<label className="inline-check"><input type="checkbox" checked={issuesOnly} onChange={(event) => setIssuesOnly(event.target.checked)} /> Issues only</label>}>
        <DataTable headers={['Source', 'Total', 'Indexed', 'Failed', 'Stale', 'Status']} rows={visible} />
      </Panel>
    </div>
  );
}

function CompanyDirectory() {
  const [selected, setSelected] = useState<typeof companies[number]>(companies[0]);
  return (
    <div className="two-col wide-left">
      <Panel title="Company directory">
        <div className="company-grid">
          {companies.map((company) => (
            <button key={company[0]} className={selected[0] === company[0] ? 'company-card selected' : 'company-card'} onClick={() => setSelected(company)}>
              <strong>{company[0]}</strong>
              <small>{company[1]}</small>
              <Score label="Complete" value={company[3]} />
            </button>
          ))}
        </div>
      </Panel>
      <Panel title={selected[0]}>
        <Field label="Focus" value={selected[1]} />
        <Field label="Employees" value={String(selected[2])} />
        <Field label="Indexed CVs" value={String(selected[4])} />
        <Field label="Location" value={selected[5]} />
      </Panel>
    </div>
  );
}

function Analytics() {
  return (
    <div className="two-col">
      <Panel title="Demand vs supply">
        <div className="bar-list">
          {skills.map(([skill, demand, supply]) => (
            <div key={skill}>
              <div className="bar-label"><strong>{skill}</strong><span>Demand {demand}% / supply {supply}%</span></div>
              <Bar value={demand} tone="cyan" />
              <Bar value={supply} tone="slate" />
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Gap register">
        <DataTable headers={['Capability', 'Demand', 'Supply', 'Risk']} rows={skills.map(([skill, demand, supply, risk]) => [skill, `${demand}%`, `${supply}%`, risk])} />
        <Evidence>Current demand is shifting toward Azure data migration and RAG-backed assistants. The biggest commercial risk is evidence quality, not raw headcount.</Evidence>
      </Panel>
    </div>
  );
}

function CandidateTable({ candidates: rows, shortlist, toggleShortlist, openProfile }: { candidates: Candidate[]; shortlist: number[]; toggleShortlist: (id: number) => void; openProfile: (id: number) => void }) {
  return (
    <div className="candidate-table">
      {rows.map((candidate) => (
        <div className="candidate-row" key={candidate.id}>
          <button className="candidate-main" onClick={() => openProfile(candidate.id)}>
            <strong>{candidate.name}</strong>
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
      <div><span>{label}</span><strong>{value}%</strong></div>
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
