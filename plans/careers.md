# Plan: Applicant Tracking System

> Source PRD: `prd/careers.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Owning app**: a new `careers` app, namespace `careers`. It touches other apps only at their edges: `accounts.User`, the navbar, the back-office tab rail, and `seed`.
- **Authorization**: `User.is_recruiter` is a boolean set in Django admin. `User.can_recruit` is the one check: a superuser, or a user who is both `is_staff` and `is_recruiter`. Every back-office careers view is guarded by it, and `Application.objects.visible_to(user)` hides the viewer's own applications from staff screens.
- **Models**:
  - `Job`: `Job.Status` (Draft, Open, Closed) and `Job.EmploymentType`; public URLs use its slug.
  - `Stage`: editable name, order, and `is_active`, with a fixed `Stage.Kind` (Entry, In progress, Hired, Rejected, Withdrawn). No rule reads a stage's name.
  - `Application`: `job` and `stage` are `PROTECT`; `user` is nullable with `SET_NULL`; a `UniqueConstraint` on job and user allows one application per person per job. `closed_at` and `anonymized_at` record its life cycle.
  - `StageChange` and `Note`: add-only, and both feed one timeline.
- **Deep module**: `careers/services.py` holds `submit_application`, `move_application`, `reopen_application`, `withdraw_application`, and `anonymize_application`. Nothing else changes a stage, and each move writes the stage and its `StageChange` in one transaction. Time-dependent functions take an optional `now`.
- **Private files**: résumés live under `PRIVATE_MEDIA_ROOT` (default `private_media/`, gitignored), have no public URL, and are served only by a permission-checked view. Tests redirect this folder with an autouse fixture.
- **Email**: sent with `transaction.on_commit`, following the `User.change_email` pattern. Emails use the applicant labels only, never a stage name or a note.
- **Required data**: default stages come from a data migration, not `seed`. Tests fetch stages by `kind`.
- **Public URLs**:
  - `/careers/` — open jobs
  - `/careers/<slug>/` — one job
  - `/careers/<slug>/apply/` — submit an application
  - `/careers/applications/` — My applications (`applications` is a reserved slug)
  - `/careers/applications/<pk>/withdraw/`
  - `/careers/applications/<pk>/resume/`
- **Back-office URLs** (pks, recruiter-only):
  - `/backoffice/careers/` — job list
  - `/backoffice/careers/jobs/new/`
  - `/backoffice/careers/jobs/<pk>/edit/`
  - `/backoffice/careers/jobs/<pk>/applications/` — table
  - `/backoffice/careers/jobs/<pk>/board/`
  - `/backoffice/careers/applications/<pk>/` — detail and timeline
  - `/backoffice/careers/applications/<pk>/move/`
  - `/backoffice/careers/applications/<pk>/reopen/`
  - `/backoffice/careers/applications/<pk>/notes/`
  - `/backoffice/careers/stages/`, with `new/`, `<pk>/edit/`, `<pk>/shift/`, `<pk>/retire/`, and `<pk>/restore/`
  - `/backoffice/careers/reports/`

---

## Phase 1: Post a job

**User stories**: 1–5, 6 (the sign-in message only), 18–20

### What to build

The smallest public careers site, run by the first recruiter. Add `is_recruiter` and `can_recruit`, the `Job` model, and a Careers tab that only recruiters and superusers see. Recruiters create Draft jobs, edit them, and move them through Draft → Open → Closed → Open. Visitors browse Open jobs and read one, a Closed job shows its message, and a Draft is a 404. An Open job tells visitors to sign in to apply, with sign-in returning to the job; applying itself arrives in Phase 2. Add the Careers link to the navbar.

### Acceptance criteria

- [ ] `is_recruiter` can be set in Django admin, and `can_recruit` is correct for customers, plain staff, recruiters, and superusers
- [ ] Every back-office careers URL refuses visitors, customers, and non-recruiter staff
- [ ] The Careers tab shows only when `can_recruit` is true
- [ ] A recruiter can create, edit, publish, close, and reopen a job, and disallowed status moves are refused
- [ ] The public list shows Open jobs only, newest first, with badges for the structured facts
- [ ] A Closed job's link shows a clear message; a Draft's link is a 404
- [ ] `applications` cannot be used as a job slug
- [ ] The public list and the back-office job list both have designed empty states
- [ ] `CLAUDE.md` is updated with the `is_recruiter` exception, the `careers/` entry, and this PRD and plan
- [ ] The test suite is green

---

## Phase 2: Apply with a private résumé

**User stories**: 6–9, 11–12, 14, 17, 33

### What to build

The first complete path for an applicant. Add `Stage`, `Application`, and `StageChange`, with the data migration that creates the default stages, and start `careers/services.py` with `submit_application`. A signed-in user applies to an Open job with a validated PDF and an optional cover letter. Private storage and the protected download arrive here, so a résumé never exists without protection. "My applications" lists each application and its date, with a basic status that Phase 4 finishes. The careers address is shown from `CAREERS_EMAIL`.

This phase also adds the job-page states for the application form, an existing application, and signing in. Protecting a job with applications from deletion, promised in Phase 1's story 20, is enforced by `PROTECT` from here on.

### Acceptance criteria

- [ ] After `migrate`, a fresh database has the default stages with the right kinds
- [ ] An application starts in the Entry stage with a first `StageChange` that has no from-stage
- [ ] Only Open jobs accept applications, and only from signed-in users
- [ ] A second application to the same job is refused by the form and by the database, including a double-submit
- [ ] A missing résumé, a file over 5 MB, and a `.pdf` file with other contents are each refused, and the cover letter survives
- [ ] The stored file has no public URL and sits outside `media/`
- [ ] The owner and a recruiter can download a résumé; another customer, non-recruiter staff, and a visitor get a 404
- [ ] A recruiter cannot use the staff path to reach their own résumé
- [ ] Downloads are sent as attachments with `X-Content-Type-Options: nosniff`
- [ ] Tests never write to the real `private_media/`, and the folder is gitignored
- [ ] "My applications" has a designed empty state linking to open jobs
- [ ] `CLAUDE.md` is updated for the third deep module and `private_media/`
- [ ] The test suite is green

---

## Phase 3: Review and move applications

**User stories**: 21, 23, 26–27 (moves only), 32

### What to build

The recruiter's core loop. Each job gets a table of applications filtered by stage, and each application gets a detail page with its résumé link, cover letter, and history of moves. `move_application` is the only way a stage changes: forward, backward, or skipping, with Hired and Rejected closing the application. `visible_to` keeps every recruiter away from their own application on all staff URLs. Moves send no email until Phase 4.

### Acceptance criteria

- [ ] The table lists a job's applications, filters by stage, and has a designed empty state
- [ ] Open applications can move to any active stage except Withdrawn
- [ ] Moving to a Hired or Rejected stage sets `closed_at`
- [ ] Closed applications, retired stages, and Withdrawn are refused, with no `StageChange` written on failure
- [ ] Each successful move writes one `StageChange` naming who made it
- [ ] Hiring leaves the job, other applications, and the user's account unchanged
- [ ] A recruiter or superuser who applied gets a 404 for their own application on every staff URL
- [ ] `Application` is read-only in Django admin
- [ ] The test suite is green

---

## Phase 4: Tell the applicant

**User stories**: 10–11, 13, 16, 24

### What to build

Finish what the applicant sees and hears. `public_status` maps each kind to its label, and "My applications" uses it. Add the received, successful, and not-moving-forward emails, sent only after the transaction commits. Moving to Hired or Rejected gains an inline confirm step warning that this will email the applicant.

### Acceptance criteria

- [ ] Each stage kind shows the right applicant label
- [ ] A stage's name and any note text never appear on applicant pages or in emails
- [ ] Applying sends the received email; moving to Hired or Rejected sends the matching email
- [ ] Moves between other stages send nothing
- [ ] A rolled-back transaction sends no email
- [ ] A move to Hired or Rejected shows the warning first, as an inline partial and not `hx-confirm`
- [ ] The test suite is green

---

## Phase 5: Withdraw and Reopen

**User stories**: 15, 25–26

### What to build

The two ways out of the normal path. An applicant withdraws an open application after a confirmation that gives the careers email address, and receives a confirmation email. A recruiter reopens a closed application into an In progress stage with a written reason, which sends no email and clears `closed_at`.

### Acceptance criteria

- [ ] Only the applicant can withdraw, and only while the application is open
- [ ] The timeline shows the applicant as the actor, and the confirmation email is sent on commit
- [ ] The confirmation step tells the applicant to email the careers address if they change their mind
- [ ] Withdrawn counts as closed, and recruiters can reopen it
- [ ] Reopen requires a reason, stored on the `StageChange`, and is never shown to the applicant
- [ ] Reopen accepts only an active In progress stage, works on a Closed job, and sends no email
- [ ] Reopening an anonymized application is refused
- [ ] The test suite is green

---

## Phase 6: Recruiter notes

**User stories**: 27–28

### What to build

Add the `Note` model and an HTMX form on the application detail page. Notes and stage moves merge into one timeline, in order. Notes can't be edited or deleted, and the form says so.

### Acceptance criteria

- [ ] A recruiter can add a note without a reload, and the response is a partial without `base.html`
- [ ] The timeline shows moves and notes together, in date order, including retired stage names
- [ ] No URL or admin path edits or deletes a note
- [ ] A blank note is refused in place
- [ ] Non-recruiters cannot read or add notes, and neither can the application's own applicant
- [ ] The test suite is green

---

## Phase 7: Edit the stages

**User stories**: 29–30

### What to build

The stage administration page. Recruiters add stages, rename them, reorder them with up and down buttons, and retire and restore them. `Stage.can_retire()` protects both occupied stages and the required kinds. A renamed or retired stage must leave every earlier rule working.

### Acceptance criteria

- [ ] The page lists stages in order, with their kind and application count
- [ ] New stages can be In progress, Hired, or Rejected, and a kind cannot change afterward
- [ ] A stage holding any application, open or closed, cannot be retired
- [ ] Retiring can never leave a required kind without an active stage
- [ ] Retired stages leave the move choices, stay in timelines, and can be restored
- [ ] The app offers no delete, and `PROTECT` blocks one elsewhere
- [ ] Moves, closing, emails, and applicant labels still work after a rename
- [ ] The test suite is green

---

## Phase 8: Data retention

**User stories**: 35

### What to build

Add `anonymize_application`, the `purge_applications` command, and the `pre_delete` receiver on `User`. Anonymized applications stay in reports as "Former applicant", and their résumé file is really gone.

### Acceptance criteria

- [ ] Anonymizing deletes the résumé file first, then clears the user, cover letter, notes, and `StageChange` notes
- [ ] `changed_by` is cleared on rows the applicant made, and running it twice is harmless
- [ ] The command handles the boundary at exactly `RETENTION_DAYS`, using a passed `now` in tests
- [ ] Open applications are never touched
- [ ] The command reports how many it anonymized
- [ ] Deleting a user, one at a time or in bulk through Django admin, anonymizes their applications
- [ ] Staff screens and résumé downloads handle anonymized applications without error
- [ ] The test suite is green

---

## Phase 9: The board

**User stories**: 22

### What to build

Upgrade the working table with a board for each job. Each active stage is a column of cards with a "Move to…" dropdown, and closed applications collapse into a count. A move swaps the card and updates the affected counts, using `move_application`. Moves to Hired and Rejected still go through the Phase 4 warning. No JavaScript beyond HTMX.

### Acceptance criteria

- [ ] One column shows per active stage, in order, with the right counts
- [ ] Closed applications appear only as a count
- [ ] A move changes the card and column counts without a reload, and partials omit `base.html`
- [ ] A refused move shows a clear error and changes nothing
- [ ] Hired and Rejected moves show the email warning first
- [ ] The viewer's own application does not appear
- [ ] The board works at phone width and has a designed empty state
- [ ] The test suite is green

---

## Phase 10: Hiring report

**User stories**: 31

### What to build

A recruiter-only page under the Careers tab, with totals per job, a funnel by kind, rejected versus withdrawn counts, and average days to hire. Queries live on the application queryset and read `StageChange` by kind, so renamed and retired stages can't break them. No hiring data reaches the all-staff dashboard.

### Acceptance criteria

- [ ] Only recruiters and superusers can reach the page
- [ ] The funnel counts applications that reached each kind, including through retired stages
- [ ] Days to hire uses the latest move to a Hired stage, including after a Reopen
- [ ] Anonymized applications are counted
- [ ] The page shows no applicant names
- [ ] The query count does not grow with the number of applications
- [ ] The page has a designed empty state
- [ ] The test suite is green

---

## Phase 11: Demo world

**User stories**: 34

### What to build

Extend `seed` so the whole hiring story can be shown from a fresh reset. Add a demo `recruiter`, jobs in all three statuses, and applications across every kind with timelines and notes that obey the service rules. Résumés are small generated PDFs. The reset removes private files and restores the default stages.

### Acceptance criteria

- [ ] `seed` runs repeatedly with the same result, and leaves no orphaned private files
- [ ] Every stage kind and job status appears
- [ ] Seeded timelines are valid, and a `recruiter` account can sign in to the Careers tab
- [ ] The existing demo employee has `is_recruiter` off, so the difference is easy to show
- [ ] The demo `customer` has no applications
- [ ] A test keeps the seed's default stages and the migration in step, without invoking the command
- [ ] The README and `CLAUDE.md` mention the new demo account and `purge_applications` where accounts and commands are listed
- [ ] The test suite is green
