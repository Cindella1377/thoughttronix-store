# PRD: The ThoughtTronix Store — Applicant Tracking System

*Commissioned by ThoughtTronix Product Management. "Your Thoughts, Our Business."*

*Builds on `prd/core-platform.md` and `prd/account-email.md`. Where this document is silent, the core PRD's conventions hold.*

---

## Problem Statement

ThoughtTronix has nowhere to hire. A person who wants to work there has no page to look at and no way to apply, and the company has no record of who applied, who looked at them, or why a decision was made. `User.job_title` is the only trace of employment in the system.

Hiring also holds data the store has never had to protect. A résumé carries someone's address, phone number, and work history, and a recruiter's notes can be candid. Today, every `is_staff` user sees everything in the back office, and uploaded files in `media/` are reachable by anyone with the URL. Neither is acceptable for candidate data.

## Solution

**A careers site inside the store.** A new `careers` app adds a public list of open jobs and a page for each. An applicant signs in, uploads a PDF résumé, and optionally adds a cover letter.

**A pipeline staff can shape.** Recruiters edit one shared list of hiring stages. Each stage has a fixed *kind* set in code, so names and order can change without breaking any rule.

**Decisions are firm, and on the record.** Recruiters move an open application forward, backward, or past stages freely. Reaching Hired or Rejected closes it. Undoing that takes a deliberate Reopen with a written reason. Every move and note is kept in an add-only timeline.

**Applicants see only what is safe.** "My applications" shows a status worked out from the stage's kind, such as *Under review*. Stage names, the timeline, and notes are never shown to applicants. Applicants can withdraw, and they get an email at the moments that matter.

**Hiring data stays with the hiring team.** Only recruiters and superusers reach the Careers tab, résumés, notes, and reports. Nobody can act on their own application from the staff side. Personal data is removed 12 months after an application closes.

## User Stories

**Visitor**

1. As a visitor, I can browse every Open job, newest first, with its department, location, employment type, and salary range when one is given.
2. As a visitor, I can read a job's full description at its own URL.
3. As a visitor, a Closed job's link tells me it is no longer accepting applications instead of showing a 404.
4. As a visitor, a Draft job does not exist for me: it is not listed, and its URL is a 404.
5. As a visitor, when no jobs are open I see a designed empty state.
6. As a visitor, an Open job's page tells me to sign in to apply, and signing in brings me back to that job.

**Applicant**

7. As an applicant, I can apply to an Open job with a PDF résumé of up to 5 MB and an optional cover letter.
8. As an applicant, I am told, without losing my cover letter, when my résumé is missing, too large, or not really a PDF.
9. As an applicant, I can apply to a job only once, ever; afterward the job page links to "My applications".
10. As an applicant, I receive an email confirming my application was received.
11. As an applicant, "My applications" shows each job, the date I applied, and my status: *Received*, *Under review*, *Application successful*, *Not moving forward*, or *Withdrawn*.
12. As an applicant, with no applications I see a designed empty state that links to open jobs.
13. As an applicant, I never see stage names, notes, or the timeline.
14. As an applicant, I can download the résumé I submitted, and no other applicant can.
15. As an applicant, I can withdraw an open application after a confirmation telling me to email the careers address if I change my mind.
16. As an applicant, I receive an email when I am hired, rejected, or when my withdrawal is recorded, and none for moves between other stages or for a Reopen.
17. As an applicant, the careers email address is shown so I can reach the hiring team.

**Recruiter (staff with `is_recruiter`) and admin (superuser)**

18. As a recruiter, I see a Careers tab in the back office. Other staff do not, and cannot reach any page behind it.
19. As a recruiter, I can create a job as a Draft, edit it, publish it, close it, and reopen it.
20. As a recruiter, I cannot delete a job that has applications.
21. As a recruiter, I see a job's applications in a table I can filter by stage, with a designed empty state.
22. As a recruiter, I see a job's open applications on a board, one column per active stage, with closed applications collapsed into a count.
23. As a recruiter, I can move an open application from the table, the board, or its detail page.
24. As a recruiter, moving someone to a Hired or Rejected stage first warns me that this will email the applicant.
25. As a recruiter, I can reopen a closed application into an In progress stage by giving a written reason.
26. As a recruiter, I cannot move a closed application, move anyone to Withdrawn, or reopen an anonymized application.
27. As a recruiter, an application's detail page shows its résumé link, cover letter, and one timeline of moves and notes.
28. As a recruiter, I can add a note without a reload; notes cannot be edited or deleted.
29. As a recruiter, I can add, rename, reorder, retire, and restore stages.
30. As a recruiter, I can retire a stage only when no application sits in it, and never when that would leave a required kind without an active stage.
31. As a recruiter, a report page shows totals per job, a funnel by kind, rejected versus withdrawn counts, and average days to hire, with no names.
32. As an employee who applied to a job, I am purely an applicant: my application is missing from every staff screen I can reach, and I cannot act on it or read its notes.

**Any developer**

33. As a developer, a fresh database has working default stages after `migrate`, with no seed needed.
34. As a developer, `seed` creates demo jobs in all three statuses, applications across the pipeline, notes, and a recruiter account.
35. As a developer, `uv run python manage.py purge_applications` anonymizes every application closed for 12 months and reports how many.

## Implementation Decisions

**A new app.** `careers` owns the models, service module, views, templates, and URLs. It touches other apps only at their edges: `accounts.User` gains `is_recruiter`, the navbar gains a Careers link, the back-office rail gains a Careers tab, and `seed` creates demo data.

**Roles.** `User` gains `is_recruiter`, a boolean defaulting to false, set in Django admin and added to `accounts/admin.py`. `User.can_recruit` is the one place that answers the question: true for a superuser, or for a user who is both `is_staff` and `is_recruiter`. This is a deliberate exception to "No role field": store data did not need dividing among staff, and candidate data does. It stays a single yes/no field, with no Groups.

**Models.**

- `Job`: `title`, `slug` (unique), `description` (plain text, rendered with `linebreaks`), `department` (plain text), `location`, `employment_type`, `salary_range` (optional text), `status`, `created_at`, and `published_at`.
  - `Job.Status` is `TextChoices`: Draft, Open, Closed. Allowed moves are Draft → Open, Open → Closed, and Closed → Open.
  - `Job.EmploymentType` is `TextChoices`: Full-time, Part-time, Contract, Internship.
  - `get_absolute_url` gives `/careers/<slug>/`.
- `Stage`: `name`, `kind`, `position`, `is_active`.
  - `Stage.Kind` is `TextChoices`: Entry, In progress, Hired, Rejected, Withdrawn. It is what the code reads. No rule ever reads a stage's name.
  - New stages may be In progress, Hired, or Rejected. A stage's kind cannot change after creation.
  - There is exactly one active Entry stage and exactly one active Withdrawn stage, and at least one active Hired stage and one active Rejected stage.
- `Application`: `job` (`PROTECT`), `user` (nullable, `SET_NULL`), `stage` (`PROTECT`), `resume`, `cover_letter` (optional), `created_at`, `closed_at` (null while open), and `anonymized_at` (null until anonymized).
  - A `UniqueConstraint` on job and user enforces one application per person per job. Null users do not conflict, so anonymized records are unaffected.
  - `is_open` is true while the stage's kind is Entry or In progress.
  - `public_status` maps the kind to the applicant's label, the one place that does so.
- `StageChange`: `application` (cascade), `from_stage` (nullable, `PROTECT`), `to_stage` (`PROTECT`), `changed_by` (nullable, `SET_NULL`), `note` (optional), `created_at`. Add-only. The first row has no `from_stage`.
- `Note`: `application` (cascade), `author` (nullable, `SET_NULL`), `body`, `created_at`. Add-only.

`Application.stage` and the newest `StageChange` hold the same fact on purpose, for simple queries. The service module writes both in one transaction, and nothing else changes a stage.

**The rules live in `careers/services.py`.** This is the project's third deep module, because these workflows cross models, files, and email, and stage moves are the riskiest logic in the app. Every public function has a docstring and type hints, and time-dependent ones take an optional `now`. Each raises a clear error when a rule is broken.

- `submit_application(job, user, resume, cover_letter="", now=None)`: the job must be Open. Places the application in the Entry stage, writes the first `StageChange`, and queues the received email. A duplicate caught by the constraint, as from a double-click, is reported as already applied.
- `move_application(application, stage, by, note="", now=None)`: `by` must pass `can_recruit` and must not be the applicant. The application must be open and the stage active and not Withdrawn. Moving to a Hired or Rejected stage sets `closed_at` and queues that email.
- `reopen_application(application, stage, reason, by, now=None)`: the application must be closed and not anonymized, the stage must be active and In progress, and `reason` is required and stored as the `StageChange` note. Clears `closed_at`. Sends no email. A Closed job does not block it.
- `withdraw_application(application, by, now=None)`: `by` must be the applicant and the application open. Moves it to the Withdrawn stage, sets `closed_at`, and queues the confirmation email.
- `anonymize_application(application, now=None)`: deletes the résumé file first, then clears `user`, `cover_letter`, every `Note`, and every `StageChange` note. Clears `changed_by` on rows the applicant made. Sets `anonymized_at`. Running it twice is harmless.

Emails are sent with `transaction.on_commit`, so nobody hears about a move that failed. An email cannot be recalled, so it goes only after the save succeeds.

**Moves.** While an application is open, recruiters may move it to any active stage except Withdrawn: forward, backward, or skipping ahead. Moving to Hired or Rejected closes it. Hiring only records the decision: the job stays Open, other applications stay where they are, and the account is unchanged. Closing the job, rejecting the others, and granting access stay manual.

**Applicant statuses.**

| Stage kind | Applicant sees |
|---|---|
| Entry | Received |
| In progress | Under review |
| Hired | Application successful |
| Rejected | Not moving forward |
| Withdrawn | Withdrawn |

**Emails.** They follow the pattern in `User.change_email`, with templates in `templates/careers/email/`, and use the labels above, never a stage name or a note.

| Event | Email |
|---|---|
| Application submitted | Received |
| Moved to a Hired stage | Application successful |
| Moved to a Rejected stage | Not moving forward |
| Applicant withdraws | Withdrawal confirmed |
| Moved between other stages | None |
| Reopened | None; recruiters contact the applicant themselves |

**Stage administration.** A back-office page lists stages in order, with their kind and how many applications sit in each. Recruiters add and rename stages, reorder them with up and down buttons, and retire and restore them. `Stage.can_retire()` requires that no application, open or closed, sits in the stage and that the stage's required kind keeps an active stage. There is no delete in the app, and `PROTECT` stops one anywhere else. Retired stages disappear from the choices for moves and stay in the timeline.

**Default stages.** A data migration (`RunPython`) creates Applied (Entry), Screening, Interview, Offer (In progress), Hired, Rejected, and Withdrawn. They are in a migration because the app breaks without them; demo content belongs in `seed`.

**Résumés.** A résumé is stored privately, never in `media/`.

- `PRIVATE_MEDIA_ROOT` defaults to `private_media/` under the project root and is gitignored. `Application.resume` uses a `FileSystemStorage` with no base URL, chosen by a callable so tests can redirect it, so no public URL exists.
- Files are stored under a random name.
- `ResumeForm` requires a `.pdf` name, a size of at most 5 MB, and a file beginning with `%PDF-`. A name alone does not prove a file is a PDF.
- A protected view returns the file with `FileResponse` as a download, with `X-Content-Type-Options: nosniff`. It serves the owner and anyone passing `can_recruit` who is not the applicant, and gives everyone else a 404.

**Access to the staff side.** A `RecruiterRequiredMixin` guards every back-office careers view with `can_recruit`. Applications reach those views through `Application.objects.visible_to(user)`, which leaves out the viewer's own applications, so a recruiter's own record is a 404 on every staff URL. The Careers tab shows only when `can_recruit` is true.

**Public pages.** `/careers/` lists Open jobs as cards with badges. A job page shows one of: sign in to apply, the application form, a link to "My applications", or the closed message. "My applications" is linked from the account page, and the careers address comes from a `CAREERS_EMAIL` setting, read from `.env` with a working default.

**The staff application screens.** The table comes first and works alone: filter by stage, open a detail page, and move by form post. The board is an upgrade to a working screen. Each stage is a column of cards with a "Move to…" dropdown, and a move swaps that card and updates the affected column counts with HTMX. All screens call `move_application`. Partials live in `templates/careers/partials/`. Confirm steps are inline partials, not `hx-confirm`, as in `reviews`. Drag-and-drop is ruled out by "no JavaScript beyond HTMX".

**Reports.** A recruiter-only page under the Careers tab. Its queries live on the application queryset, so no fourth deep module is added and no hiring data reaches the all-staff dashboard. The funnel counts applications that reached each kind, using `StageChange`, so renamed and retired stages cannot break it. Days to hire runs from `created_at` to the application's latest move to a Hired stage. The report shows totals only.

**Data retention.** `purge_applications` calls `anonymize_application` for every application with `closed_at` more than `RETENTION_DAYS` (365) ago and not already anonymized. The cleanup takes an optional `now`. Anonymized applications remain in reports and appear to recruiters as "Former applicant". A `pre_delete` receiver on `User` also anonymizes that user's applications, because accounts are deleted only in Django admin and a receiver also covers its bulk delete.

**Seed.** The seed adds a demo `recruiter`, plus jobs in all three statuses and applications across every kind, with notes and timelines that obey the service rules. Résumés are small generated placeholder PDFs. Reset deletes applications and their private files, then restores the default stages from a constant. A test keeps that constant and the migration in step. The demo `customer` has no applications, so they can apply. `is_recruiter` is off for the existing demo employee, so the difference is easy to see.

**URLs.** All named in the `careers` namespace. Public URLs use slugs; back-office URLs use pks:

| Name | Path | Page |
|---|---|---|
| `jobs` | `/careers/` | Open jobs |
| `applications` | `/careers/applications/` | My applications |
| `withdraw` | `/careers/applications/<pk>/withdraw/` | Confirm (GET) or withdraw (POST) |
| `resume` | `/careers/applications/<pk>/resume/` | Protected résumé download |
| `apply` | `/careers/<slug>/apply/` | Submit an application (POST) |
| `job` | `/careers/<slug>/` | One job and its form |
| `manage_jobs` | `/manage/careers/` | Back-office job list |
| `job_create` | `/manage/careers/jobs/new/` | New job |
| `job_edit` | `/manage/careers/jobs/<pk>/edit/` | Edit a job and change its status |
| `manage_applications` | `/manage/careers/jobs/<pk>/applications/` | The table |
| `board` | `/manage/careers/jobs/<pk>/board/` | The board |
| `application` | `/manage/careers/applications/<pk>/` | Detail and timeline |
| `move` | `/manage/careers/applications/<pk>/move/` | Move (POST) |
| `reopen` | `/manage/careers/applications/<pk>/reopen/` | Reopen (POST) |
| `note` | `/manage/careers/applications/<pk>/notes/` | Add a note (POST, HTMX) |
| `stages` | `/manage/careers/stages/` | Stage administration |
| `reports` | `/manage/careers/reports/` | Hiring report |

The `jobs` paths before `<slug>` are fixed, so `applications` is a reserved slug.

**Every list view has a designed empty state:** open jobs, My applications, a job's applications, the board, the back-office job list, and the report.

**`CLAUDE.md` changes, made with the first phase that needs them.**

- The roles line gains the `is_recruiter` exception.
- "Exactly two deliberate deep modules" becomes three, adding `careers/services.py`.
- The project layout gains `careers/` and `private_media/`, and the opening line gains this PRD and its plan.

## Testing Decisions

Tests use the shared fixtures in `conftest.py`. Small fixtures are added for a recruiter, a job, and a valid PDF upload, and stages are fetched by `kind`, so tests depend on the data migration and never on the seed. A new autouse fixture points `PRIVATE_MEDIA_ROOT` at a temporary directory, as `media_root` does for `MEDIA_ROOT`. Service tests pass exact moments through `now` and call `careers/services.py` directly. Email tests use `django_capture_on_commit_callbacks(execute=True)`.

Coverage, in priority order:

1. Résumé privacy: the owner and a recruiter can download; another customer, non-recruiter staff, and a visitor get a 404; the applicant-recruiter rule holds; the stored file has no public URL.
2. Staff access: every back-office careers URL refuses non-recruiter staff, customers, and visitors, and admits recruiters and superusers.
3. Own applications: a recruiter or superuser who applied cannot see, move, reopen, or annotate their own application through any staff URL.
4. Moves: free movement while open; closing on Hired and Rejected; refusal for closed applications, retired stages, and Withdrawn; a `StageChange` written with every move, and none on failure.
5. Reopen: a reason is required; the target must be active and In progress; `closed_at` clears; no email; works on a Closed job; refused when anonymized.
6. Withdraw: only the applicant, only while open; the timeline shows the applicant as the actor.
7. Applying: only Open jobs; signed-in users only; a duplicate is refused by the form and the database constraint; a résumé with a `.pdf` name but other contents is refused; the 5 MB limit; the cover letter survives a failed form.
8. Applicant privacy: "My applications" shows the mapped label for every kind, and a stage's name and note text never appear in that page or in any email.
9. Emails: the table above, each sent only on commit; a failed transaction sends nothing.
10. Stages: `can_retire` for an occupied stage and for each required kind; restoring; a kind cannot change after creation; renaming leaves every rule working; the migration creates the defaults.
11. Anonymize and purge: the file is gone and the text, notes, and user are cleared; history survives; the boundary at exactly `RETENTION_DAYS`; open applications are untouched; deleting a user anonymizes their applications.
12. Job statuses: Draft is a 404 publicly; Closed shows the message and refuses applications while recruiters keep working; allowed moves; a job with applications cannot be deleted.
13. Reports: funnel and totals with renamed and retired stages; rejected versus withdrawn; days to hire after a Reopen; the query count does not grow with the number of applications.
14. HTMX responses: board moves and notes return partials without `base.html`, and counts update.
15. Empty states and seed constants, read without invoking the command.

## Out of Scope

- Accounts-free or guest applications, and reapplying to the same job.
- A separate per-job pipeline, or multi-company support.
- Automatic closing dates on jobs.
- A `Department` table, job filters, or custom screening questions.
- Messaging or a contact form inside the app.
- Applicant-triggered data deletion. It can arrive later as a thin view over `anonymize_application`.
- Scorecards, interview scheduling, offer letters, and calendar links.
- Time-in-stage analytics.
- Hiring side effects: closing the job, rejecting others, or changing the hired person's account.
- Bulk moves, drag-and-drop, and résumé parsing or search.
- File formats other than PDF, and virus scanning.

## Further Notes

- **A silent Reopen can mislead someone.** An applicant wrongly told they were rejected hears nothing unless a recruiter follows up. This was chosen deliberately. A reminder on the Reopen confirm step is a small possible addition if it proves a problem.
- **A hire does not stop applications.** The job stays Open until someone closes it, and no banner reminds them. This was also chosen deliberately.
- **Purging needs a scheduler.** The project has no scheduler. Until whoever runs a deployment schedules `purge_applications` (daily is enough), it runs only by hand, and the 12-month promise is not kept automatically.
- **The purge includes hired people.** Their applications are anonymized after 12 months too. Employment records are a matter for HR systems, which this is not.
- **Private files need backing up separately.** `private_media/` is outside `media/` and the tracked snapshots, so backups and grading snapshots must not assume résumés come along, and must not publish them.
- **Retention is a design default, not legal advice.** A real deployment would need 12 months checked against local law.
- **Admin bypass.** A stage changed directly in Django admin, or in the database, skips the service rules and the log, so `Application` should be read-only there.
- **Snapshot.** The repository tracks a `db.sqlite3` snapshot for grading. Applying these migrations and re-running `seed` changes that file; whether to commit the updated snapshot is a separate decision.
