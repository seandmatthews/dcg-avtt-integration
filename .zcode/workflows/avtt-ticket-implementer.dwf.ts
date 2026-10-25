/* zcode-workflow
description: "Run ONE existing docs/tickets/ ticket end to end: baseline gates
  on main, implement on its own worktree branch (status → in-progress), gate +
  fresh-eyes code review loop (ruff + the repo's run-tests.py tiers — the
  workflow runs them, not the agents), and only on the reviewer's sign-off flip
  the ticket to completed, move it to docs/tickets/archive/ in the same change,
  and merge --no-ff into main with the gates re-run (auto-revert on red).
  Concurrency-safe: each run has its own worktree; the shared main checkout is
  guarded by a cross-run lock (.zcode/tools/checkout-lock.ps1). Adapted from
  pigeon-simulator's pigeon-ticket-pipeline."
whenToUse: When you have ONE concrete ticket (e.g. 04) and want the full
  implement → review → merge loop run on it. Safe to run several tickets
  concurrently (per-run worktrees; the main-checkout lock serializes exactly the
  merge). For turning a new idea into a ticket first, use avtt-ticket-forge.
args:
  reviewRounds:
    type: number
    description: Max review rounds (gate-fix or reviewer kick-back) before the run
      is flagged for human intervention.
    required: false
    default: 5
  ticket:
    type: string
    description: 'The ticket number to run, e.g. "04" (a filename prefix like
      "04-presets-publisher" also works). Must match exactly one file in
      docs/tickets/ with Status: proposed or in-progress.'
    required: true
*/
// dcg-avtt-integration — single-ticket implementer.
// One existing docs/tickets/ ticket in: it is validated (proposed or
// in-progress, not superseded/completed), implemented on its own worktree
// branch, gate-checked (ruff + the repo's run-tests.py tiers — run by this
// script, never by the agents' claims), and reviewed by a fresh-eyes code
// reviewer. ONLY on the reviewer's sign-off does the implementer flip the
// ticket to completed, move it to docs/tickets/archive/ in the same change,
// and merge into main; merged main is re-gated with auto-revert on failure.
// Anything that cannot converge within the round cap ends flagged for human
// intervention, with the branch kept.
// Adapted from pigeon-simulator's pigeon-ticket-pipeline (same family).
// The play-test leg does not exist here: this repo is a prep-time CLI, so
// the reviewer's independent evidence is the diff, the code around it, and
// the tests the acceptance criteria name.

// ROOT and WT_BASE are derived, never hardcoded (ticket 19): the run executes
// with its cwd at the workspace — the repo root the run was started from — so
// `git rev-parse --show-toplevel` yields ROOT wherever this repo is cloned,
// and the per-run worktrees hang off ROOT's parent as siblings of the
// checkout (AGENTS.md: per-run worktrees under ../dcg-avtt-wt/).
const rootProbe = await world.run("git", ["rev-parse", "--show-toplevel"]);
const ROOT = rootProbe.exitCode === 0
  ? rootProbe.stdout.trim().replace(/\\/g, "/")
  : "";
if (ROOT === "") {
  return {
    conclusion: "Aborted before any work: could not derive the repo root — `git rev-parse --show-toplevel` failed from the workspace (exit " + rootProbe.exitCode + "): " + rootProbe.stderr.trim().slice(0, 200) + ". Start the run from inside the dcg-avtt-integration checkout; ROOT and WT_BASE are derived from it, never hardcoded (ticket 19).",
    findings: [],
    verified: [],
    notCovered: ["everything — the repo root could not be derived, no work started"],
  } satisfies WorkflowReport;
}
const parentSlash = ROOT.lastIndexOf("/");
if (parentSlash <= 0) {
  return {
    conclusion: "Aborted before any work: the derived repo root \"" + ROOT + "\" has no parent directory — the per-run worktrees cannot be placed beside it (ticket 19). Nothing was changed.",
    findings: [],
    verified: [],
    notCovered: ["everything — the worktree base could not be derived, no work started"],
  } satisfies WorkflowReport;
}
const WT_BASE = ROOT.slice(0, parentSlash) + "/dcg-avtt-wt";

const ticketArg = String(args.ticket ?? "").trim().toLowerCase().replace(/\.md$/, "");
const prefix = /^\d+$/.test(ticketArg) ? ticketArg.padStart(2, "0") + "-" : ticketArg;
const maxRounds = typeof args.reviewRounds === "number" && args.reviewRounds >= 1 ? Math.floor(args.reviewRounds) : 5;

interface ReviewVerdict {
  /** "pass" only when every acceptance criterion is met or honestly deferred to a human, and nothing regressed. */
  verdict: "pass" | "changes";
  /** Blocking issues — must be empty on pass. Each names the file and the symptom. */
  blocking: string[];
  /** What you personally read: the diff stats, the changed files, the tests you judged. */
  evidence: string;
}

interface ImplResult {
  /** Short hash of the feature commit on the branch; empty when blocked. */
  commit: string;
  /** Two or three sentences: what changed. */
  summary: string;
  /** What tests/verification was added for this ticket. */
  verificationAdded: string;
  status: "committed" | "blocked";
  /** Empty when committed; otherwise why. */
  blocker: string;
}

interface FlipResult {
  /** Short hash of the amended feature commit on the branch. */
  branchCommit: string;
  status: "done" | "blocked";
  /** Empty when done; otherwise why. */
  blocker: string;
}

interface MergeResult {
  /** Short hash of the merge commit on main; empty when blocked. */
  mergeCommit: string;
  status: "merged" | "blocked";
  /** Empty when merged; otherwise why. */
  blocker: string;
}

interface ReaderReport {
  /** False when the report has gaps worth fixing before publishing. */
  ok: boolean;
  /** Concrete problems: unclear passages, unsupported claims, missing facts. */
  issues: string[];
}

interface WorkflowReport {
  conclusion: string;
  findings: {
    /** Branch or ticket that carries the outcome. */
    where: string;
    /** One sentence: what happened to it. */
    what: string;
    /** Gate commands that decided it, plus the commit. */
    evidence: string;
    /** "verified" only when the workflow's own gate runs passed; otherwise "unconfirmed". */
    status: "verified" | "unconfirmed";
    /** How much the user should care right now. */
    severity: "low" | "medium" | "high";
  }[];
  verified: string[];
  notCovered: string[];
}

artifact.board("pipeline", {
  title: "Ticket implementer",
  description: "One ticket: implemented, reviewed, flipped completed, archived and merged — or flagged for you.",
  key: "id",
  status: "state",
  columns: ["picked-up", "implementing", "reviewing", "signed-off", "merged", "flagged"],
  cardTitle: "id",
  detail: [
    { field: "title", label: "title" },
    { field: "note", label: "note" },
  ],
});

function tail(s: string, n: number): string {
  return s.length <= n ? s : "...\n" + s.slice(s.length - n);
}

function runGit(gitArgs: string[], timeoutMs?: number) {
  if (timeoutMs === undefined) {
    return world.run("git", gitArgs);
  }
  return world.run("git", gitArgs, { timeoutMs: timeoutMs });
}

// Cross-run mutex for the shared main checkout (.zcode/tools/checkout-lock.ps1).
// Concurrent implementer runs are fully parallel inside their own worktrees;
// every section that touches ROOT — the baseline snapshot, the baseline gates,
// the merge into main, the post-merge gates, any revert — holds this lock.
// Acquire timeout 1800s: a held lock means another run's baseline/merge+gates
// is in progress, so waiting is correct. A lock older than 1 h is stolen by
// the tool (its holder crashed and can never release).
const LOCK_SCRIPT = ROOT + "/.zcode/tools/checkout-lock.ps1";
async function lockMain(): Promise<boolean> {
  const r = await world.run("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LOCK_SCRIPT, "acquire", "main", "1800"], { timeoutMs: 1830000 });
  return r.exitCode === 0;
}
async function unlockMain(): Promise<void> {
  await world.run("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", LOCK_SCRIPT, "release", "main"]);
}

// The repo's verification gates, runnable against any checkout (main or a
// worktree). uv's --directory flag aims them at the checkout; the first run
// in a fresh worktree pays one uv sync while it builds that checkout's .venv.
async function gateSuite(dir: string): Promise<{ ok: boolean; summary: string; detail: string }> {
  const lint = await world.run("python", ["-m", "uv", "--directory", dir, "tool", "run", "ruff", "check", "src", "tests", "run-tests.py"], { timeoutMs: 600000 });
  const tests = await world.run("python", ["-m", "uv", "--directory", dir, "run", "python", "run-tests.py", "--all"], { timeoutMs: 600000 });
  let ok = true;
  let summary = "";
  let detail = "";
  if (lint.exitCode !== 0) {
    ok = false;
    summary += " lint:FAIL";
    detail += "--- ruff check (exit " + lint.exitCode + ") ---\n" + tail(lint.stdout + "\n" + lint.stderr, 1500) + "\n";
  } else {
    summary += " lint:ok";
  }
  if (tests.exitCode !== 0) {
    ok = false;
    summary += " tests:FAIL";
    detail += "--- run-tests.py --all (exit " + tests.exitCode + ") ---\n" + tail(tests.stdout + "\n" + tests.stderr, 2500) + "\n";
  } else {
    summary += " tests:ok";
  }
  return { ok, summary: summary.trim(), detail };
}

const HONESTY =
  "Never present a check you did not run as evidence. If a gate is impossible to pass, or your instructions contradict each other, escalate and say so plainly rather than working around it or faking a pass. ";

// One persistent implementer for the whole run — initial build and every
// review-round fix, so it carries its own context between kick-backs. It may
// touch the main checkout ONLY for the final flip-and-merge after sign-off.
const implementer = agent("implementer", {
  system:
    "You are the implementer for a ticket of dcg-avtt-integration (Python 3.10, stdlib-first, uv-managed, conventional commits). " +
    "You follow AGENTS.md exactly and honestly — README.md is the repo's constitution — and " + HONESTY +
    " You work in your worktree " + WT_BASE + " (branch assigned at pickup) and never touch the main checkout at " + ROOT +
    " — the ONE exception is the final flip-and-merge step, which you perform only when the workflow explicitly tells you the reviewer has signed off.",
});

const out = {
  flagged: false,
  flagReason: "",
  merged: false,
  mergeCommit: "",
  mainGates: "",
  roundsUsed: 0,
  lastVerdict: "",
};
function item(id: string, state: string, note: string) {
  report({ id: id, title: ticketTitle, state: state, note: note }, "pipeline");
}
let ticketTitle = ticketArg;
let BRANCH = "";
let WT = "";

// ---------- baseline: prove main is green before building on it ----------

let baselineOk = false;
phase("Prove main is green before starting");
if (!(await lockMain())) {
  return {
    conclusion: "Aborted before any work: could not acquire the shared main-checkout lock within 30 min — another implementer run is snapshotting/merging/gating main. Nothing was changed; re-run when the other run has finished.",
    findings: [],
    verified: [],
    notCovered: ["everything — the main-checkout lock was busy, no work started"],
  } satisfies WorkflowReport;
}
const preSt = await runGit(["-C", ROOT, "status", "--porcelain"]);
const trackedDirty = preSt.stdout
  .split(/\r?\n/)
  .filter((l) => l.trim() !== "" && !l.startsWith("??"));
if (trackedDirty.length > 0) {
  const housekeeper = agent("housekeeper", {
    system:
      "You are a careful git housekeeper. You commit only tracked changes as one chore snapshot; you never stage untracked files, never push, never rebase. " +
      HONESTY,
  });
  await housekeeper.ask(
    "The working tree of " + ROOT + " (branch main) has uncommitted tracked changes:\n" +
      trackedDirty.slice(0, 40).join("\n") +
      "\n\nCommit ALL tracked changes on main as ONE commit: \"chore: pre-run snapshot (uncommitted work on main)\". Stage only tracked files (git add -u). Never stage untracked files (.zcode/ and .venv/ stay untracked). Never push. Return one line: the commit hash, or what stopped you.",
  );
}
const baseline = await gateSuite(ROOT);
await unlockMain();
baselineOk = baseline.ok;
log("baseline gates on main:" + baseline.summary);
if (!baseline.ok) {
  return {
    conclusion:
      "Aborted before any work: main's own gate run failed (" + baseline.summary +
      "). Nothing was merged or changed; fix main first, then re-run.",
    findings: [
      {
        where: "main",
        what: "baseline gate run failed — no work started",
        evidence: "gateSuite on " + ROOT + ":" + baseline.summary,
        status: "unconfirmed",
        severity: "high",
      },
    ],
    verified: ["baseline gate run on main — it FAILED, so the run aborted"],
    notCovered: ["everything — the baseline gate run on main failed before the pipeline started"],
  } satisfies WorkflowReport;
}

// ---------- read + validate the ticket, set up its branch ----------

phase("Validate the ticket and set up its branch");
const matches = await files.glob("docs/tickets/" + prefix + "*.md");
if (matches.length !== 1) {
  return {
    conclusion: "Aborted before any work: \"" + prefix + "\" does not match exactly one file in docs/tickets/ (found " + matches.length + "). Nothing was changed. Note: completed tickets move to docs/tickets/archive/ and are no longer runnable.",
    findings: [],
    verified: [],
    notCovered: ["everything — the ticket ID was not valid, no work started"],
  } satisfies WorkflowReport;
}
const ticketPath = matches[0];
const ticketMd = await files.read(ticketPath);
const tTitle = /^# (\d{2}) — (.+)$/m.exec(ticketMd);
const tStatus = /\*\*Status:\*\* ([^\n]+)/.exec(ticketMd);
const tPriority = /\*\*Priority:\*\* ([^\n·]+)/.exec(ticketMd);
if (tTitle === null || tStatus === null) {
  return {
    conclusion: "Aborted before any work: could not parse " + ticketPath + " (expected the CONVENTIONS.md header: `# NN — Title` and a **Status:** line). Nothing was changed.",
    findings: [],
    verified: [],
    notCovered: ["everything — the ticket file was unreadable, no work started"],
  } satisfies WorkflowReport;
}
ticketTitle = tTitle[2].trim();
const ticketNum = tTitle[1];
const priority = tPriority !== null ? tPriority[1].trim() : "unparsed";
const statusWord = tStatus[1].trim().split(/[\s(]/)[0];
if (statusWord !== "proposed" && statusWord !== "in-progress") {
  const supTarget = /\*\*Status:\*\* superseded[^\d]*(\d{2})/.exec(ticketMd);
  return {
    conclusion: "Aborted before any work: " + ticketNum + " has status \"" + tStatus[1].trim() + "\"" +
      (supTarget !== null ? " — it was consolidated into " + supTarget[1] + "; run that ticket instead" : " — only proposed/in-progress tickets can be run") +
      ". Nothing was changed.",
    findings: [],
    verified: [],
    notCovered: ["everything — the ticket was not actionable, no work started"],
  } satisfies WorkflowReport;
}
const stem = ticketPath.replace(/^.*\//, "").replace(/\.md$/, "");
BRANCH = "feature/" + stem;
WT = WT_BASE + "/" + stem;
log("ticket " + ticketNum + " \"" + ticketTitle + "\" (" + priority + ") — building on branch " + BRANCH);
item(ticketNum, "picked-up", ticketPath);

const existing = await runGit(["-C", ROOT, "branch", "--list", BRANCH]);
if (existing.stdout.trim() !== "") {
  const anc = await runGit(["-C", ROOT, "merge-base", "--is-ancestor", BRANCH, "main"]);
  if (anc.exitCode === 0) {
    await runGit(["-C", ROOT, "branch", "-d", BRANCH]);
    log("removed leftover merged branch " + BRANCH);
  } else {
    out.flagged = true;
    out.flagReason =
      "branch " + BRANCH + " already exists with UNMERGED work (probably a previous flagged run) — human intervention required: inspect or delete " + BRANCH + " and its worktree, then re-run";
  }
}
if (!out.flagged) {
  const rmOld = await runGit(["-C", ROOT, "worktree", "remove", "--force", WT]);
  if (rmOld.exitCode === 0) log("cleared old worktree " + WT);
  const add = await runGit(["-C", ROOT, "worktree", "add", "-B", BRANCH, WT]);
  if (add.exitCode !== 0) {
    out.flagged = true;
    out.flagReason = "could not create worktree " + WT + " on branch " + BRANCH + ": " + tail(add.stderr, 300);
  }
}
if (out.flagged) {
  return {
    conclusion: "FLAGGED before any work: " + out.flagReason,
    findings: [
      {
        where: BRANCH,
        what: "worktree/branch setup failed — no work started",
        evidence: out.flagReason,
        status: "unconfirmed",
        severity: "high",
      },
    ],
    verified: [],
    notCovered: ["everything — setup failed before the pipeline started"],
  } satisfies WorkflowReport;
}
const mainHeadBefore = (await runGit(["-C", ROOT, "rev-parse", "--short", "HEAD"])).stdout.trim();

// ---------- implement ----------

let impl: ImplResult | null = null;
phase("Implement the ticket");
impl = await implementer.ask<ImplResult>(
  "Implement ticket " + ticketNum + " in your worktree " + WT + " (branch " + BRANCH + "). The ticket file is " + ticketPath + " in the worktree — read it there.\n\n" +
    "THE TICKET IS THE DEFINITION OF DONE (its Acceptance criteria block, verbatim; never redefine it):\n" + ticketMd + "\n\n" +
    "1. FLIP TO IN-PROGRESS FIRST (the CONVENTIONS.md ticket loop): set the ticket's **Status:** to in-progress in the worktree's ticket file. This repo has NO tickets index — the file is the record.\n" +
    "2. Implement it. REPO RULES (AGENTS.md is law; README.md is the constitution): stdlib-first (PyYAML is the one allowed dependency; no Pillow, no LLM anywhere); subprocess only in list form, never shell=True; pathlib for paths; nothing may write outside atlas-vtt/ plus the one licensed companion-note exception (contract rule 1); refuse-on-diff with stable stems (rule 3); never write library.json or collection.json (non-goals §9); the README's pinned-release table governs any Atlas-format constant.\n" +
    "3. REQUIRED IN THE SAME CHANGE-SET: the tests the acceptance criteria name (under tests/, collected automatically by run-tests.py; discipline placeholders in tests/test_disciplines.py get their real bodies moved to proper test files when their ticket lands). Never weaken an existing test's assertion to make it pass.\n" +
    "4. Run the gates yourself while you iterate until you believe they are green: python -m uv --directory " + WT + " tool run ruff check src tests run-tests.py  and  python -m uv --directory " + WT + " run python run-tests.py --all  (the first run in this fresh worktree pays one uv sync). The workflow re-runs ALL gates after you — their results, not your claims, decide — but do not skip your own check either.\n" +
    "5. Tick ONLY the acceptance criteria your runs have actually proven. Spike tickets: do what an agent can (source reads, written-up decisions, docs); if a criterion needs the Atlas UI or a human ruling, do the part you can, leave the criterion unticked, and say exactly what remains for the human in your summary — that is honest partial work, not failure. LEAVE the ticket's **Status:** as in-progress in your commit — the flip to completed happens only after the reviewer signs off.\n" +
    "6. Make your commit(s) on the branch: default is ONE commit — conventional-commit type that fits the change (feat/fix/docs/test/chore), scope " + ticketNum + ", e.g. feat(" + ticketNum + "): <change> (<title>) — EXCEPT when the ticket itself explicitly mandates a different structure. The worktree must end with a clean tracked tree. Never commit to main, never push. If external resources you cannot obtain are required (an Atlas-UI session, the owner's house-rule values), return status blocked with exactly what is needed.\n\n" +
    "Return the ImplResult.",
);
if (impl.status !== "committed") {
  out.flagged = true;
  out.flagReason = "implementer blocked before any review round: " + impl.blocker;
  item(ticketNum, "flagged", impl.blocker.slice(0, 120));
} else {
  log("implemented as " + impl.commit + " — " + impl.summary);
  item(ticketNum, "implementing", "commit " + impl.commit);
}

// ---------- review loop: gates and fresh-eyes code review ----------

if (!out.flagged && impl !== null) {
  phase("Review loop: gates and code review");
  const reviewer = agent("reviewer", {
    system:
      "You are the reviewer for dcg-avtt-integration. You have not seen how the work was made and you owe it no courtesy. You read the actual diff and the actual code, and you judge the work against the ticket's acceptance criteria — the workflow has already run the full gates on this worktree, so your independent evidence is the diff itself, the code around it, and the tests the criteria name. You never edit any file and you never commit; read-only git and the Read tool are your instruments. You would rather send work back than rubber-stamp it. " +
      HONESTY,
  });
  let feedback = "";
  for (let round = 1; round <= maxRounds; round++) {
    out.roundsUsed = round;
    const gates = await gateSuite(WT);
    if (!gates.ok) {
      log("round " + round + ": gates red on the worktree — back to the implementer" + gates.summary);
      impl = await implementer.ask<ImplResult>("The workflow ran the full verification gates against your worktree and they FAILED:" + gates.summary + "\n" + gates.detail +
        "\nFix the cause (never by weakening an existing test's assertion), amend or add the commit so the tracked tree ends clean, keep the ticket bookkeeping truthful (status stays in-progress), and return the ImplResult again.");
      continue;
    }
    const dirty = await runGit(["-C", WT, "status", "--porcelain"]);
    if (dirty.stdout.trim() !== "") {
      impl = await implementer.ask<ImplResult>("Your worktree has uncommitted tracked changes after your commit — the tree must end clean:\n" + dirty.stdout.slice(0, 2000) +
        "\nAmend or commit so the tracked tree is clean (gitignored build state like .venv/ stays untracked), then return the ImplResult again.");
      continue;
    }
    item(ticketNum, "reviewing", "round " + round + " — reviewer reading the diff and code");
    const verdict = await reviewer.ask<ReviewVerdict>(
      "Review ticket " + ticketNum + " (\"" + ticketTitle + "\") — round " + round + " of at most " + maxRounds + ". Worktree with the committed work: " + WT + " (branch " + BRANCH + " of " + ROOT + ")." +
      (feedback !== "" ? "\n\nYOUR PREVIOUS VERDICT sent this back; check each item is actually fixed:\n- " + feedback : "") +
      "\n\n1. CODE: inspect the change: git -C " + ROOT + " log --oneline main.." + BRANCH + " and git -C " + ROOT + " diff main..." + BRANCH +
      " (three-dot: merge-base to branch). Read the changed files in the worktree plus enough surrounding code to judge them: correctness; repo conventions (AGENTS.md: list-form subprocess, stdlib-first; README constitution: writes only inside atlas-vtt/ plus the one licensed companion-note exception, refuse-on-diff with stable stems, never library.json/collection.json, no runtime at the table); the tests the criteria name actually exist and pin the criterion (assert the behavior, not a tautology); the README's pinned-release constants were not invented from memory.\n" +
      "2. CRITERIA: every acceptance criterion is met, unmet, or honestly deferred — check them one by one (criteria the implementer ticked AND ones still open). A criterion ticked without evidence in the diff or tests is a blocking problem. A criterion deferred to a human (an Atlas-UI experiment, the owner's house-rule values) with the deferral said plainly in the implementation summary is NOT blocking.\n" +
      "3. TICKET HONESTY: the ticket file's **Status:** is still in-progress, and the work stayed inside the ticket's scope.\n\n" +
      "VERDICT DISCIPLINE: \"changes\" only for blocking problems — acceptance criterion unmet or falsely ticked, real bug, broken convention, contract-rule violation, or visible regression. Style and could-be-cleaner go in evidence, never block. Do not invent issues to justify a round; if the work is correct and meets the criteria, PASS.\n\n" +
      "Return the ReviewVerdict.",
    );
    out.lastVerdict = verdict.verdict;
    if (verdict.verdict === "pass") {
      log("round " + round + ": review PASS — " + verdict.evidence.slice(0, 200));
      break;
    }
    feedback = verdict.blocking.join("\n- ");
    log("round " + round + ": review sent work back — " + verdict.blocking.length + " blocking issue(s)");
    if (round < maxRounds) {
      impl = await implementer.ask<ImplResult>("The reviewer read the diff and the code, and sent ticket " + ticketNum + " back (round " + round + "). Fix EVERY one of these:\n- " + feedback +
        "\n\nThen amend or add the commit so the tracked tree is clean, keep the ticket bookkeeping truthful (status stays in-progress), and return the ImplResult again. Do not expand scope beyond the ticket.");
    }
  }

  if (out.lastVerdict !== "pass") {
    out.flagged = true;
    out.flagReason =
      "review did not accept the work within " + maxRounds + " rounds (last verdict: " + out.lastVerdict + ") — HUMAN INTERVENTION REQUIRED. Branch " + BRANCH +
      " and worktree " + WT + " are kept for inspection; last blocking items:\n- " + feedback;
    item(ticketNum, "flagged", "no acceptance in " + maxRounds + " rounds");
  }
}

// ---------- on sign-off: flip the ticket completed, then merge under the lock ----------

let flip: FlipResult | null = null;
if (!out.flagged && impl !== null && impl.status === "committed") {
  phase("Reviewer signed off — flip the ticket completed and archived");
  item(ticketNum, "signed-off", "reviewer accepted in round " + out.roundsUsed);
  flip = await implementer.ask<FlipResult>(
    "THE REVIEWER HAS SIGNED OFF — ticket " + ticketNum + " is accepted. Finish the CONVENTIONS.md ticket bookkeeping in your worktree " + WT + " (branch " + BRANCH + "):\n\n" +
      "1. Tick every acceptance criterion the recorded evidence proves; in ## Implementation notes record how it actually landed (today's real date from your shell, commit refs, any deliberate deviation from the proposal, and any criterion honestly left for a human).\n" +
      "2. Set the ticket's **Status:** to completed AND move the file: git mv docs/tickets/" + stem + ".md docs/tickets/archive/ — the CONVENTIONS rule is that the status flip and the archive move are the same change.\n" +
      "3. Fold those docs-only changes into your branch's LAST commit (git commit --amend, or a fixup + squash if the ticket mandated multiple commits) so the tracked tree ends clean.\n" +
      "4. Do NOT merge yet — the workflow merges in its own next step, under its main-checkout lock, and will tell you when.\n\n" +
      "Return the FlipResult (branchCommit = your amended commit hash).",
  );
  if (flip.status !== "done") {
    out.flagged = true;
    out.flagReason = "sign-off flip failed: " + flip.blocker + " — branch " + BRANCH + " is accepted but the ticket was not flipped; HUMAN INTERVENTION REQUIRED.";
    item(ticketNum, "flagged", "flip failed");
  }
}

// The merge, the post-merge gate suite and any revert all hold the shared
// main-checkout lock: a concurrent implementer run must not merge at the
// same time.
if (!out.flagged && flip !== null && flip.status === "done") {
  phase("Merge into main and re-gate it");
  if (await lockMain()) {
    const merged = await implementer.ask<MergeResult>(
      "Now the merge — the ONLY time you touch " + ROOT + ": git -C " + ROOT + " merge --no-ff " + BRANCH +
        " -m \"merge: " + ticketNum + " — " + ticketTitle + "\". If the merge conflicts, run git -C " + ROOT +
        " merge --abort and return status blocked with the conflict summary — do NOT resolve conflicts by hand.\n\n" +
        "The workflow holds the main-checkout lock while you do this and re-runs ALL gates on merged main afterwards, auto-reverting if they fail — that is expected, not your concern.\n\n" +
        "Return the MergeResult (mergeCommit = the merge commit hash on main).",
    );
    if (merged.status !== "merged") {
      out.flagged = true;
      out.flagReason = "sign-off merge failed: " + merged.blocker + " — branch " + BRANCH + " is accepted and the ticket is flipped completed on the branch, but NOT integrated; HUMAN INTERVENTION REQUIRED.";
      item(ticketNum, "flagged", "merge failed");
    } else {
      const mh = await runGit(["-C", ROOT, "rev-parse", "--short", "HEAD"]);
      const headNow = mh.exitCode === 0 ? mh.stdout.trim() : "";
      if (headNow === mainHeadBefore || headNow === "") {
        out.flagged = true;
        out.flagReason = "the implementer reported a merge but main's HEAD is unchanged (or unreadable) — integration did not actually happen; HUMAN INTERVENTION REQUIRED.";
        item(ticketNum, "flagged", "main HEAD unchanged after reported merge");
      } else {
        out.mergeCommit = headNow;
        const g = await gateSuite(ROOT);
        out.mainGates = g.summary;
        if (g.ok) {
          out.merged = true;
          log("merged " + out.mergeCommit + " into main — main gates" + g.summary);
          item(ticketNum, "merged", "merge " + out.mergeCommit + ", main gates" + g.summary);
        } else {
          const rev = await runGit(["-C", ROOT, "revert", "--no-edit", "-m", "1", "HEAD"]);
          if (rev.exitCode === 0) {
            out.flagged = true;
            out.flagReason = "merged, then AUTO-REVERTED: gates failed on integrated main" + g.summary + " — the branch passed its own gates but broke in combination; HUMAN INTERVENTION REQUIRED to reconcile.";
          } else {
            out.flagged = true;
            out.flagReason = "merged, gates failed on main, and the REVERT FAILED — main needs human attention NOW" + g.summary + "; revert error: " + tail(rev.stderr, 200);
          }
          item(ticketNum, "flagged", "main gates red" + g.summary);
        }
      }
    }
    await unlockMain();
  } else {
    out.flagged = true;
    out.flagReason = "could not acquire the shared main-checkout lock within 30 min — another implementer run holds it. Branch " + BRANCH + " is accepted and the ticket is flipped completed on the branch, but NOT integrated; merge " + BRANCH + " by hand or re-run later. HUMAN INTERVENTION REQUIRED.";
    item(ticketNum, "flagged", "main-checkout lock busy");
  }
}

// ---------- cleanup + report ----------

phase("Write the run report");
if (out.merged) {
  const rm = await runGit(["-C", ROOT, "worktree", "remove", WT]);
  const bd = await runGit(["-C", ROOT, "branch", "-d", BRANCH]);
  log(rm.exitCode === 0 && bd.exitCode === 0 ? "cleaned up worktree and merged branch" : "cleanup incomplete — worktree/branch may remain");
}
let md = "# Ticket implementer — \"" + ticketTitle + "\" (" + ticketNum + ")\n\n";
md += "**Ticket file:** " + ticketPath + " · **Priority:** " + priority + "\n\n";
md += "**Outcome:** " + (out.merged
  ? "SIGNED OFF and MERGED into main as " + out.mergeCommit + " — ticket flipped completed and archived, main gates" + out.mainGates
  : "FLAGGED — not merged. " + out.flagReason) + "\n\n";
md += "## Ticket\n\n" + ticketMd + "\n\n";
if (impl !== null && impl.status === "committed") {
  md += "## Implementation\n\n- Commit: `" + (flip !== null && flip.branchCommit !== "" ? flip.branchCommit : impl.commit) + "` on " + BRANCH + "\n- " + impl.summary + "\n- Verification added: " + impl.verificationAdded + "\n\n";
}
md += "## Review\n\n- Rounds used: " + out.roundsUsed + " of " + maxRounds + "\n- Final verdict: " + (out.lastVerdict || "never reached") + "\n";
if (out.mainGates !== "") {
  md += "- Gates on main after merge:" + out.mainGates + "\n";
}
md += "\n";
const reader = agent("report-reader", {
  system:
    "You are a cold reader: you judge a report purely as a reader would, from the text alone. You do not verify claims against the repository and you do not edit files. You name what is unclear, what the text fails to support, and what a developer reading it would still be missing. " +
    HONESTY,
});
const readerOut = await reader.ask<ReaderReport>(
  "Read this report and tell me what is wrong with it as a piece of writing for the repo's owner deciding what to do next:\n\n" + md +
    "\n\nAnswer with ok (false when there are gaps worth fixing) and a list of concrete issues: unclear passages, claims the text does not support, missing facts. Return ONLY the ReaderReport.",
);
let finalMd = md;
if (!readerOut.ok && readerOut.issues.length > 0) {
  const fixer = agent("report-fixer", {
    system: "You rewrite reports to fix flagged problems without inventing facts. Return ONLY the full corrected markdown.",
  });
  finalMd = await fixer.ask(
    "A cold reader flagged these problems in the report below:\n" + readerOut.issues.map((i: string) => "- " + i).join("\n") +
      "\n\nRewrite the report fixing every one (keep all facts; improve wording, structure and flagging only). Return ONLY the full corrected markdown.\n\n" + md,
  );
}
await artifact.markdown("report", finalMd, {
  title: "Ticket implementer report — " + ticketNum,
  description: (out.merged ? "signed off, merged as " + out.mergeCommit : "FLAGGED: " + out.flagReason.slice(0, 120)) + " · " + out.roundsUsed + " review round(s)",
  primary: true,
});

const verified: string[] = ["baseline gates on main before any work (ruff + run-tests.py --all)"];
if (impl !== null && impl.status === "committed") {
  verified.push("full gate suite on the worktree before every review round (" + out.roundsUsed + " round(s))");
}
if (out.merged) {
  verified.push("reviewer sign-off (diff + code + criteria read independently) BEFORE the ticket flip and merge");
  verified.push("merge commit " + out.mergeCommit + " followed by a full gate suite on main" + out.mainGates);
}
return {
  conclusion: out.merged
    ? "Ticket " + ticketNum + " (\"" + ticketTitle + "\") was implemented, reviewed and signed off in " + out.roundsUsed + " round(s); the implementer then flipped it completed, archived it, and merged into main (" + out.mergeCommit + ") with green gates on integrated main."
    : "FLAGGED — the implementer did not reach a merge: " + out.flagReason,
  findings: [
    {
      where: ticketNum + " (" + BRANCH + ")",
      what: out.merged
        ? "implemented, reviewed, signed off, ticket flipped completed and moved to docs/tickets/archive/, merged into main"
        : "not merged: " + out.flagReason,
      evidence: (impl !== null && impl.status === "committed" ? "commit " + impl.commit + "; " : "") +
        (out.mainGates !== "" ? "gates on main:" + out.mainGates : out.roundsUsed > 0 ? "worktree gates green each review round" : "no gate run reached"),
      status: (out.merged ? "verified" : "unconfirmed") as "verified" | "unconfirmed",
      severity: (out.flagged ? "high" : "low") as "low" | "high",
    },
  ],
  verified: verified,
  notCovered: [
    "any acceptance criterion the ticket reserves for a human ruling or an Atlas-UI experiment — the reviewer can only accept what the evidence shows; deferred items are named in the ticket's Implementation notes",
    ...(out.merged ? [] : ["the unmerged work on " + BRANCH + " — kept, but never integrated"]),
  ],
} satisfies WorkflowReport;