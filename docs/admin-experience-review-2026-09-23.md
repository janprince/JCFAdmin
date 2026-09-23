# Jan Cosmic Foundation — administration experience review

23 September 2026 · Review and implementation

## Assessment

The portal has useful foundations: shared Django templates, consistent server-rendered lists, real search and filters, reusable record forms, status indicators, and a separation between the Foundation database and Inner Space. The existing uncommitted work was preserved. Replacing the framework would discard useful behavior without addressing the main experience problems.

The major design issue was that the home screen described the database rather than the team's work. A large contacts chart led the page while messages, applications, giving, and publishing were several navigation steps away. The long sidebar exposed the internal module structure. Small secondary type, generic template blue, and inconsistent interaction feedback made the interface feel inherited rather than designed for this Foundation.

The project notes said Poppins, but the actual code and browser already used IBM Plex Sans. The typography review was based on the rendered implementation, not the stale notes.

## What changed

| Area | Finding | Implemented response |
|---|---|---|
| Overview | Totals and a large chart dominated; incoming work was hidden. | A work-focused overview: unread messages, centre requests, volunteer applications, the consultation schedule, upcoming public events, completed giving by currency, and publishing drafts. Contact trends are supporting information. |
| Navigation | The expanded module list required scrolling and knowledge of backend terminology. | Task groups: Community, Inbox, Consultations, Teaching & events, Giving, Inner Space, and Website content. The active group opens on the server; the most specific destination is highlighted. Staff navigation retains its permission condition. |
| Finding a page | No quick route across modules. | A keyboard-accessible page finder, opened by the header or Ctrl/Cmd K. It searches page names, not records, and says so. Keyboard navigation, empty results, Escape, and native dialog focus containment are supported. |
| Typography | Small, template-driven UI lacked a deliberate hierarchy. | Self-hosted variable Public Sans, with system fallbacks. One family for headings, controls, and text; tabular figures for data. Larger fields and controls, a 28px primary heading, and clearer contrast between labels and values. |
| Visual identity | Generic blue template and gradient monogram. | Indigo actions and navigation, white working surfaces, cool neutral canvas, restrained gold active markers, and a simple Foundation office wordmark. Light and dark themes share the same hierarchy. |
| Donations | All currencies were summed into one value labelled GHS; general gifts could not be isolated. | Completed totals grouped by currency, a General donations filter, and search across donor, email, office reference, and Paystack reference. Invalid initiative IDs produce an empty result rather than an exception. |
| Consultations | Unfinished past appointments appeared in Upcoming. | Separate Upcoming, Today, Needs an update, and Completed views. Overview links go to the corresponding queue. |
| Events | Multi-day events were treated as past after their start date. Draft overview links had no matching filter. | Current events remain current through their end date; published upcoming and past views use that rule. A real Unpublished filter supports the publishing queue. |
| Sign in/out | The login felt generic; logout used GET even though Django requires POST. | A focused sign-in layout with an existing Foundation photograph, password visibility toggle, preserved return destination, and CSRF-protected POST sign-out. |
| Forms | It was easy to navigate away without understanding that edits were unsaved. | Full record editors show unsaved/saving feedback and trigger the browser's navigation warning. Invalid controls receive focus and associated help/error descriptions. Search filters are excluded. |
| Mobile tables | Offscreen columns and actions were not explained. | Overflowing tables receive a visible scroll hint and a keyboard-focusable region. Page layouts avoid horizontal viewport overflow. |
| Feedback | Errors and warnings disappeared automatically after four seconds. | Errors/warnings remain until dismissed; success notices have a longer display period. Dismiss controls have accessible names. |

## Design direction

“Foundation office” is a working environment for coordinators, administrators, and the media team. It should feel composed and specific to their responsibilities, without reproducing the public website's large serif headings or promotional sections.

| Token | Value | Role |
|---|---|---|
| Office indigo | `#393477` | Actions, links, emphasis |
| Navigation indigo | `#24243E` | Persistent navigation |
| Canvas | `#F4F5F8` | Page background |
| Surface | `#FFFFFF` | Tables, forms, focused work |
| Text | `#282B3B` | Primary reading |
| Foundation gold | `#D3AE63` | Wordmark and current navigation marker |

The first design pass kept the shared table/form foundation rather than generating a new card style per module. In visual review, the overview was adjusted to balance its columns and keep trend information subordinate to pending work. A duplicated inherited logo state and conflicting Paces theme rules were corrected.

Public Sans is an intentional UI choice, not a claim that one font guarantees accessibility. The [official typography guidance](https://digital.gov/resources/an-introduction-to-typography) emphasizes size, spacing, contrast, and readability across contexts; those were addressed alongside the family change. The [font source and SIL license](https://github.com/google/fonts/tree/main/ofl/publicsans) are included locally in `static/jcf/fonts/`. The portal no longer requests Google Fonts at runtime.

## Priority findings that remain

### 1. Enforce permissions at the action, not only in navigation

**Implemented in the subsequent portal-access pass.** See [Portal accounts and role-based access](portal-access.md) for the role matrix, enforcement, account setup and rollout. The following describes the original review finding.

`staff_mgmt/views.py` uses `LoginRequiredMixin` for staff lists and edits, while navigation checks `staff_mgmt.view_worker`. Hiding the menu does not stop a signed-in account from using a direct URL. Other operational modules also primarily use authentication rather than a role-specific permission policy.

Define the intended capabilities of Admin, Administrator, Secretary, and Media Operations, then enforce them in views and POST handlers. This needs an agreed role policy; the visual redesign does not change who may access existing records. Do not infer that the displayed role label is an authorization boundary.

### 2. Convert state-changing GET routes to POST, with confirmations where appropriate

Examples remain in consultation completion/deletion (`consultations/views.py`), enquiry status updates and centre approvals (`website/views.py`), and some delete views. Centre approval can create/update a member and trigger an email. These should use explicit POST forms with CSRF protection, idempotency where relevant, and specific confirmation copy. A generic browser confirmation is not a substitute for the correct HTTP method.

The shared logout action was corrected because it was directly broken. A consistent conversion of the remaining endpoints and every caller deserves its own coordinated implementation and regression coverage.

### 3. Complete Foundation signup as a distinct journey

The public website's new `/join` form is a Foundation-wide registration followed by Telegram access. Existing `JoinCentreRequest` records require a centre, a phone number, an approval decision, and may trigger email and member creation. They are not the same process.

Add the Foundation registration endpoint and an appropriate admin view for name, email, optional phone, country, region, and registration date. Agree deduplication and contact-record linkage. Do not silently send the public form to the centre approval endpoint. The redesigned sidebar explicitly calls the existing queue “Centre join requests.”

### 4. Make inbox work trackable

“Read” is not the same as “handled.” An enquiry currently has a read flag; there is no visible owner, reply history, or resolved state. Introduce a small workflow—New, In progress, Resolved—with assignment and an activity log if multiple staff share responsibility. Keep email replies explicit. Bulk triage should follow only after this state model is agreed.

### 5. Strengthen publishing confidence

The existing forms support publication, but editors would benefit from a consistent preview of the public page, a clear draft/published summary, and revision history. A future pass should distinguish saving edits from publishing where accidental publication matters, and explain which image/text fields appear on the public site.

### 6. Reduce template baggage

Paces still loads sizeable generic CSS and JavaScript bundles. Its unused translation manager requests a relative `assets/data/translations/en.json` URL that returns 404 on admin pages. This is inherited behavior; the redesign does not patch the minified vendor runtime. A targeted asset pass should remove unused startup behavior and bundles after checking datepickers, dropdowns, rich text editing, and mobile navigation.

### 7. Clarify account support

The login has no supplied password-reset workflow. Add a tested reset route and staff support process instead of displaying a “Forgot password” link that goes nowhere. The current change adds no invented support address or reset destination.

## Implementation boundaries

- No production data, member decisions, payments, external messages, or Inner Space records were changed during review.
- Preview records are explicitly synthetic and live only in `/tmp/jcf-admin-review/preview.sqlite3`.
- Inner Space was disabled in the isolated settings. Its unavailable pages were rendered; its remote database and operational decisions were not exercised.
- No database migrations were added. The event date correction changes model behavior only.
- The public website repository was not changed in this admin task.
- This is an implementation and expert review, not usability research with actual staff or a complete security/accessibility certification.

## Validation

Django system checks, template compilation, route smoke checks, regression tests, and desktop/mobile browser checks are used for this change. The tests cover currency separation, completed/current-month giving, pending inbox counts, general donations and reference search, invalid filters, multi-day events, draft events, consultation queues, navigation selection, and POST logout. Browser checks cover the page finder, themes, unsaved editor warnings, mobile layouts/navigation, the message modal, and sign-out.

Completed results: all 9 Django regression tests passed; system checks and template compilation passed; 27 routes were smoke-tested (the isolated Inner Space pages returned their expected unavailable responses). Desktop and mobile interaction checks passed, with no JavaScript page errors. `git diff --check` passed. The local preview is available at `http://127.0.0.1:8001/dashboard/` while its development server is running.
