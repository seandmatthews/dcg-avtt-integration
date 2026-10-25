/* zcode-workflow
description: "Turn ONE idea into a reviewed docs/tickets/ ticket: a writer
  grounds every claim before writing (repo files read; Atlas-behavior claims
  checked against the pinned reference source per AGENTS.md; campaign-generator
  claims read in that repo), a fresh-eyes reviewer re-verifies independently
  (repo check, Atlas check, checkable criteria, fit against the constitution and
  open tickets), and on sign-off a registrar commits the ticket file to main.
  House format per docs/tickets/CONVENTIONS.md: two-digit numbering, never
  reused; deliberately no tickets index."
whenToUse: When you have ONE idea, improvement or finding for
  dcg-avtt-integration that should become a backlog ticket — spikes, publisher
  work, pack content, test discipline, docs. The forge grounds the ticket before
  it lands; a reviewer must pass before the ticket commits to main. Use
  avtt-ticket-implementer to BUILD an existing ticket.
args:
  idea:
    type: string
    description: "The improvement idea or finding, in one or two plain sentences:
      what should change and why."
    required: true
  reviewRounds:
    type: number
    description: Max reality-check review rounds before the run is flagged for human
      intervention.
    required: false
    default: 3
*/
// dcg-avtt-integration — ticket forge: one idea in, a reviewed ticket out.
//
// Adapted from pigeon-simulator's pigeon-ticket-forge (same family, same
// machine, same reviewer discipline). The T-069 lesson translates directly:
// a ticket that is self-consistent can still be wrong about the world —
// here, a claim about Atlas's behavior written from memory with nobody
// re-reading the pinned source. The grounding rule replaces the photo
// research: repo claims are verified by reading the repo; Atlas-behavior
// claims by reading the pinned reference source; campaign-generator claims
// by reading that repo. There is no real-world photo leg in this repo — a
// file-format adapter has no zebra crossings.

// ROOT is derived, never hardcoded (ticket 19): the run executes with its
// cwd at the workspace — the repo root the run was started from — so
// `git rev-parse --show-toplevel` yields ROOT wherever this repo is cloned.
const rootProbe = await world.run("git", ["rev-parse", "--show-toplevel"]);
const ROOT = rootProbe.exitCode === 0
  ? rootProbe.stdout.trim().replace(/\\/g, "/")
  : "";
if (ROOT === "") {
  return {
    conclusion: "Aborted before any work: could not derive the repo root — `git rev-parse --show-toplevel` failed from the workspace (exit " + rootProbe.exitCode + "): " + rootProbe.stderr.trim().slice(0, 200) + ". Start the run from inside the dcg-avtt-integration checkout; ROOT is derived from it, never hardcoded (ticket 19).",
    findings: [],
    verified: [],
    notCovered: ["everything — the repo root could not be derived, no work started"],
  } satisfies WorkflowReport;
}
const ideaText = String(args.idea ?? "").trim();
const maxRounds = typeof args.reviewRounds === "number" && args.reviewRounds >= 1 ? Math.floor(args.reviewRounds) : 3;

interface TicketDraft {
  /** Assigned two-digit number, e.g. "07" (docs/tickets/ numbering; never reused). */
  id: string;
  title: string;
  /** P1, P2 or P3, as written in the ticket header. */
  priority: string;
  /** Repo-relative path of the written ticket file. */
  path: string;
  /** Full markdown content of the ticket file. */
  content: string;
}

interface TicketReview {
  /** "pass" only when the ticket is implementable without questions, every claim about repo/Atlas/campaign-generator state was confirmed by reading what it names, and every criterion is checkable. */
  verdict: "pass" | "changes";
  /** Blocking issues — must be empty on pass. Each names the file or section and the problem. */
  blocking: string[];
  /** What you checked against what: which files, which README sections, which Atlas source files. */
  evidence: string;
}

interface CommitResult {
  status: "committed" | "blocked";
  /** Short commit hash, empty when blocked. */
  commit: string;
  /** Empty when committed; otherwise why. */
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
    /** Ticket path that carries the outcome. */
    where: string;
    /** One sentence: what happened to it. */
    what: string;
    /** The review evidence and/or commit. */
    evidence: string;
    /** "verified" when the reviewer checked the draft and the file exists on disk; else "unconfirmed". */
    status: "verified" | "unconfirmed";
    severity: "low" | "high";
  }[];
  verified: string[];
  notCovered: string[];
}

const HONESTY =
  "Never present a check you did not run as evidence, and never claim to have read a source you did not open. If something is impossible, or your instructions contradict each other, escalate and say so plainly rather than working around it. ";

const out = {
  flagged: false,
  flagReason: "",
  committed: false,
  commit: "",
  roundsUsed: 0,
  lastVerdict: "",
};

// One persistent ticket writer for the whole run — the draft and every
// review-round revision, so it carries its own context between kick-backs.
const writer = agent("ticket-writer", {
  system:
    "You are the ticket writer for dcg-avtt-integration. You write technically specific, self-contained ticket files that a stranger could implement without asking questions, in the house format of docs/tickets/CONVENTIONS.md (the open tickets 01-06 show the style; AGENTS.md is law and README.md is the constitution). " +
    HONESTY,
});

if (ideaText === "") {
  return {
    conclusion: "Aborted before any work: the idea argument was empty. Nothing was changed.",
    findings: [],
    verified: [],
    notCovered: ["everything — no idea was given"],
  } satisfies WorkflowReport;
}

// The campaign-generator grounding leg is conditional (ticket 19): the
// sibling repo is private and need not exist on this machine, so the script
// probes it before the writer is ever pointed at it. When it is absent the
// writer is told to ground only in-repo claims and to name the gap — never
// to fabricate grounding for a repo it cannot read.
const CG_DIR = ROOT.slice(0, ROOT.lastIndexOf("/")) + "/dnd-campaign-generator";
const cgProbe = await world.run("git", ["-C", CG_DIR, "rev-parse", "--show-toplevel"]);
const cgAvailable = cgProbe.exitCode === 0;
const cgGrounding = cgAvailable
  ? "A claim about the campaign generator's files or layouts: read " + CG_DIR + "."
  : "This machine has NO readable campaign-generator checkout at " + CG_DIR + " (the probe `git -C <dir> rev-parse --show-toplevel` failed), so ground ONLY in-repo claims: make no claim about the campaign generator's files or layouts — what it does becomes something the ticket must establish on a machine that has the repo, named explicitly there as unverified here.";
if (!cgAvailable) {
  log("campaign-generator grounding degraded: no readable sibling at " + CG_DIR + " — the writer grounds only in-repo claims and names the gap (ticket 19)");
}

phase("Draft the ticket from the idea");
const draft: TicketDraft = await writer.ask<TicketDraft>(
  "Turn the owner's idea into the next ticket in " + ROOT + " (docs only — never touch src/, tests/, packs/, fixtures/).\n\n" +
    "THE IDEA (from the repo's owner): " + ideaText + "\n\n" +
    "1. Read AGENTS.md (law), README.md (the constitution — the ticket must obey its four contract rules and its non-goals §9, and cite sections the way the repo does), and docs/tickets/CONVENTIONS.md (numbering, rules, template).\n" +
    "2. Pick the next free two-digit number: list docs/tickets/*.md AND docs/tickets/archive/*.md, take the highest NN + 1 (numbers are never reused; gaps are fine). Read every open (proposed/in-progress) ticket so you do not duplicate or contradict one; a finding already carried by an open ticket is not a new ticket.\n" +
    "3. GROUND EVERY CLAIM BEFORE WRITING IT: read the files and README sections the ticket will name, in this repo. A claim about Atlas's behavior must come from the pinned reference source, never from memory: read the clone at %TEMP%\\atlas-vtt (Git Bash: $TEMP/atlas-vtt), first confirming the pin with git -C <clone> describe --tags against the README §7 table; if it is missing, re-clone per AGENTS.md — to $TEMP, never into the repo. " + cgGrounding + " What cannot be verified today is not claimed — it becomes part of what the ticket must establish (that is what spike tickets are for).\n" +
    "4. Never invent house-rule values (README §5.2/§6): a pack/preset ticket that needs the owner's table values says the human supplies them and records provenance in packs/icrpg/PACK.md.\n" +
    "5. Write docs/tickets/NN-short-name.md exactly in the CONVENTIONS.md template: **Status:** proposed · **Priority:** P1|P2|P3 · **Area:** files/modules · **Found by:** what surfaced it + today's date (get it from your shell); then ## Problem (self-contained evidence: observed behavior, file:line, reproduction — must still make sense on its own), ## Proposal (enough detail that an agent can implement it without re-deriving the design; call out anything that needs a user ruling rather than deciding it silently), ## Acceptance criteria (each criterion names the test that pins it, or is directly checkable; a spike ticket's criterion is its written-up decision), and the ## Implementation notes placeholder left as-is. This repo has deliberately NO tickets index — do not create or update one.\n" +
    "Return the TicketDraft (content = the full markdown).",
);
log("ticket " + draft.id + " drafted: " + draft.title);

phase("Reality-check review");
const reviewer = agent("ticket-reviewer", {
  system:
    "You are the ticket reviewer for dcg-avtt-integration. You review a ticket BEFORE it lands: would an implementer be told the truth? You have not seen the draft being made and owe it no courtesy. You never edit any file; reading (repo, README, reference source) and your own skepticism are your instruments. Your standing grudge: a self-consistent ticket signed off while wrong about the world — about Atlas's behavior, about what the code does, about what the campaign generator emits — and problem-claims signed off unread. You exist so neither ships again. " +
    HONESTY,
});
let feedback = "";
for (let round = 1; round <= maxRounds; round++) {
  out.roundsUsed = round;
  const verdict = await reviewer.ask<TicketReview>(
    "Review ticket draft " + draft.id + " (\"" + draft.title + "\") — round " + round + " of at most " + maxRounds + ". Repo: " + ROOT + "." +
      (feedback !== "" ? "\n\nYOUR PREVIOUS VERDICT sent this back; check each item is actually fixed:\n- " + feedback : "") +
      "\n\n1. Read " + draft.path + " in full.\n" +
      "2. REPO CHECK — mandatory for every ticket: open every file of this repo the ticket names (its ## Problem, ## Proposal and acceptance criteria) and read enough around them to judge. Verify the claims about the current state are TRUE — the stub raises NotImplementedError, the cited README section says what the ticket says it says, the file does not exist / exists as claimed. Verify the proposed change WOULD solve the claimed problem as specified (right module, right mechanism, obeying the constitution's contract rules and non-goals). A claim about the repo you cannot confirm by reading it is a blocking problem; a fix aimed at the wrong site or mechanism is a blocking problem; a stale line number is NOT blocking — note it as drift to correct during implementation.\n" +
      "3. ATLAS + CAMPAIGN-GENERATOR CHECK — mandatory for any ticket claiming Atlas behavior or campaign-generator layout: read the pinned reference clone ($TEMP/atlas-vtt — confirm its tag against the README §7 table first; re-clone per AGENTS.md if missing, to $TEMP, never into the repo) or ../dnd-campaign-generator respectively. A behavior or layout claim you cannot confirm there is a blocking problem.\n" +
      "4. CHECKABLE: does every acceptance criterion have a way to pass or fail (a named test, or a directly checkable claim; a spike ticket: a written-up decision one can read)? Would the machine criteria actually catch the failure mode the ticket exists to prevent?\n" +
      "5. FIT: read the open tickets in docs/tickets/ — does this duplicate one, contradict a landed decision, violate the constitution (contract rules 1-4, non-goals §9), or collide on a ticket number? A ticket that invents house-rule/preset values instead of demanding them from the owner is a blocking problem (README §5.2/§6).\n" +
      "6. IMPLEMENTABILITY: could a stranger implement this without asking questions — files named, mechanism specified, user rulings called out rather than decided silently?\n\n" +
      "VERDICT DISCIPLINE: \"changes\" only for blocking problems — a claim you could not confirm by reading, a fix aimed at the wrong site, a violation of the constitution, an invented house-rule value, an uncheckable criterion, or a duplicate. Writing style alone never blocks. If the problem is real, the fix would work, and every claim matches what you read, PASS.\n\n" +
      "Return the TicketReview.",
  );
  out.lastVerdict = verdict.verdict;
  if (verdict.verdict === "pass") {
    log("round " + round + ": ticket review PASS — " + verdict.evidence.slice(0, 200));
    break;
  }
  feedback = verdict.blocking.join("\n- ");
  log("round " + round + ": review sent the ticket back — " + verdict.blocking.length + " blocking issue(s)");
  if (round < maxRounds) {
    const revised = await writer.ask<TicketDraft>(
      "The reviewer sent ticket " + draft.id + " back (round " + round + "). Fix EVERY one of these in " + draft.path +
        ":\n- " + feedback +
        "\n\nKeep the house format; do not weaken a criterion to escape the criticism — fix the ticket to be true. Return the TicketDraft again.",
    );
    draft.id = revised.id;
    draft.title = revised.title;
    draft.priority = revised.priority;
    draft.path = revised.path;
    draft.content = revised.content;
  }
}
if (out.lastVerdict !== "pass") {
  out.flagged = true;
  out.flagReason = "ticket was not accepted within " + maxRounds + " review rounds (last verdict: " + out.lastVerdict + ") — the draft is left UNCOMMITTED in the working tree at " + draft.path + " for human attention; last blocking items:\n- " + feedback;
}

if (!out.flagged) {
  phase("Land the ticket in the repo");
  const registrar = agent("registrar", {
    system:
      "You are a careful git registrar. You stage exactly the files you are told — never more — and commit with the given message. You never push, never rebase, never touch unrelated files (in particular never .zcode/, .venv/, uv.lock). " +
      HONESTY,
  });
  const committed = await registrar.ask<CommitResult>(
    "Commit the signed-off ticket in " + ROOT + " (branch main). Stage ONLY:\n" +
      "- " + draft.path + "\n" +
      "\nCommit message: docs(tickets): " + draft.id + " — " + draft.title + "\n" +
      "If anything unexpected is already staged or the commit fails, git reset to a clean staged-nothing state and return status blocked with the reason. Return the CommitResult.",
  );
  if (committed.status !== "committed") {
    out.flagged = true;
    out.flagReason = "ticket was accepted but the commit failed: " + committed.blocker + " — the draft is left in the working tree uncommitted; HUMAN INTERVENTION REQUIRED.";
  } else {
    out.committed = true;
    out.commit = committed.commit;
    log("ticket " + draft.id + " landed as " + committed.commit);
  }
}

phase("Write the run report");
let onDisk = false;
try {
  const disk = await files.read(draft.path);
  onDisk = disk.length > 0 && disk.indexOf("## Acceptance criteria") !== -1;
} catch {
  onDisk = false;
}
let md = "# Ticket forge — " + draft.id + " \"" + draft.title + "\"\n\n";
md += "**The idea:** " + ideaText + "\n\n";
md += "**Outcome:** " + (out.committed
  ? "SIGNED OFF and COMMITTED as " + out.commit + " — " + draft.path
  : "FLAGGED — not committed. " + out.flagReason) + "\n\n";
if (draft !== null) {
  md += "## Ticket\n\n" + draft.content + "\n\n";
}
md += "## Review\n\n- Rounds used: " + out.roundsUsed + " of " + maxRounds + "\n- Final verdict: " + (out.lastVerdict || "never reached") + "\n";
const reader = agent("report-reader", {
  system:
    "You are a cold reader: you judge a report purely as a reader would, from the text alone. You do not verify claims against the repository and you do not edit files. You name what is unclear, what the text fails to support, and what a developer reading it would still be missing. " +
    HONESTY,
});
const readerOut = await reader.ask<ReaderReport>(
  "Read this report and tell me what is wrong with it as a piece of writing for the repo's owner deciding what to do next:\n\n" + md +
    "\n\nAnswer with ok (false when there are gaps worth fixing) and a list of concrete issues. Return ONLY the ReaderReport.",
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
  title: "Ticket forge report — " + draft.id,
  description: (out.committed ? "committed as " + out.commit : "FLAGGED") + " · " + out.roundsUsed + " review round(s)",
  primary: true,
});

return {
  conclusion: out.committed
    ? "Idea \"" + ideaText.slice(0, 80) + "\" became ticket " + draft.id + " (\"" + draft.title + "\"), grounded and passed the reality-check review in " + out.roundsUsed + " round(s), and landed as commit " + out.commit + "."
    : "FLAGGED — the ticket did not land: " + out.flagReason,
  findings: [
    {
      where: draft.path,
      what: out.committed ? "ticket drafted, grounded against repo/README/reference source, reviewed, committed" : "not committed: " + out.flagReason,
      evidence: (out.commit !== "" ? "commit " + out.commit + "; " : "") + "ticket on disk with acceptance criteria: " + onDisk + "; review rounds: " + out.roundsUsed,
      status: (onDisk ? "verified" : "unconfirmed") as "verified" | "unconfirmed",
      severity: (out.flagged ? "high" : "low") as "low" | "high",
    },
  ],
  verified: [
    ...(onDisk ? ["ticket file exists on disk with an Acceptance criteria block (script read it back)"] : []),
    "reviewer read the files and sources the ticket names and confirmed the problem is real and the fix would work",
    ...(out.committed ? ["committed to main as " + out.commit] : []),
  ],
  notCovered: [
    "the idea's eventual IMPLEMENTATION — this run only produces the ticket; run it through avtt-ticket-implementer when you want it built",
    "any acceptance criterion that needs the owner's house-rule values or an Atlas-UI experiment — those stay human",
  ],
} satisfies WorkflowReport;