# Working fast without losing quality: instructions for Claude

These are general instructions, learned on Realmwalker (2026-10-12), for any long piece of work with Claude Code.
To use them in every project: copy the block between the two lines below into your personal instructions file
(see "How to install" at the end). To use them in one project only: paste the block into that project's `CLAUDE.md`.

---

## How to work: fast, without losing quality

- **Done means usable.** A feature is finished only when someone can actually use it: wired into everything that
  calls it, with one test that uses it the way a user would. Never mark something done that nothing calls.
- **Light checks while building, heavy checks once.** While working, run only the tests for what you changed. Run
  the slow checks (the full test suite, long simulations, end-to-end runs) once per milestone, one at a time,
  before merging. Don't rerun a heavy check after a small fix if a targeted test covers it.
- **Helpers for bulk work.** Copying tables, entering data, converting many similar files: hand them to two or
  three helper agents in parallel on a cheaper, faster model, each with a precise brief (exactly what to do, the
  format, one finished example, where the source is, how to check its work). Keep the design and the core code in
  the main session, and review what the helpers return.
- **Edit with the built-in edit tools.** Use scripts only for mechanical changes across many files, and write the
  script to a file first rather than pasting it into the shell.
- **Read narrowly.** Search for the place you need and read only that part. Keep a short map of the biggest files
  in the project's `CLAUDE.md` so you don't page through them every time.
- **One milestone per session.** When a milestone is finished and merged, write down where things stand and what
  comes next, then stop. A long conversation makes every later step slower and more expensive, and once it is
  summarised, details get lost.
- **A short review before merging.** Have a fresh helper that hasn't seen the work check it against the
  milestone's checklist. Fix what it finds before merging, not after.
- **Report honestly.** Say what was checked and what wasn't; never call something done that has not been tried.

---

## How to install (Windows)

**For every project, on this PC (recommended):**
1. Press the Windows key, type `notepad`, press Enter.
2. In Notepad: File → Open. In the "File name" box type `%USERPROFILE%\.claude\CLAUDE.md` and press Enter.
   - If Notepad says the file does not exist, choose **Yes** to create it.
3. Copy the block between the two lines above (from "## How to work" down to "Report honestly...") and paste it at
   the end of the file.
4. File → Save. Close Notepad. Every new Claude Code session on this PC will now read these instructions.

**For one project only:** open that project's `CLAUDE.md` (in the project folder) the same way and paste the block
at the end.

(Or ask Claude: "Add the block from docs/WORKING_FAST.md to my personal CLAUDE.md", and approve the change.)
