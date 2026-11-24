# User Acceptance Test Plan

Roomly is released from `v*` tags. This plan is the release gate for **every major version bump**
(`X.0.0`) and covers every journey a person can complete in the product: guest, signed-in renter,
group owner, group member and administrator.

Run it on a build of the release candidate, record the results, and sign off before tagging.

| | |
| --- | --- |
| Document version | 1.0 |
| Applies to | Roomly 3.0.0 and later major releases |
| Owner | Release manager |
| Environment | Dev or staging, with the demo seed |
| Duration | About 90 minutes for one tester |

## 1. Scope

The eight use cases of SSDS-001 §8.1.2 are in scope, plus the browser pages that expose them:

| Area | What the tester exercises |
| --- | --- |
| Access | Sign-up with email confirmation, sign-in, password reset, session restore, sign-out, account deletion, deleted-user attribution |
| Groups | Create, invite, accept/decline, six-member limit, ownership transfer, removal, leave/dissolve |
| Listings | Manual submission, card values, Unknown values, conflicts, price history, duplicate hold, reports |
| Administration | Source configuration, duplicate merge/split/keep-separate, report resolution, admin-only access |
| Search | Hard constraints, amenities, viewport, sorting, paging, saved searches, commute destinations |
| Comparison | Preview, best-value rules, save, share, change tracking |
| Room | Messages, threads, reactions, polls, voting, closing polls, message notifications |
| Notifications | Inbox, unread count, read/read-all, delivery settings |
| Pages | Header navigation, search dashboard, account pages, listing detail, compare, groups, notifications |

Out of scope for UAT: feed ingestion, explained ranking, commute routing, WebSocket push, notification
email delivery, URL import and data export. (Verification and password-reset email *is* in scope; see
"Email links" below.) They are not reachable by a user in this release; see
`docs/backend/traceability.md`.

### Frontend coverage in 3.x

The backend implements all 56 endpoints, but the browser currently ships the search dashboard, listing detail, guest comparison
and the account pages. A case whose journey needs a page that does not exist yet is executed through
`/docs` (Swagger UI) against the same API and recorded as **API pass**; the UI part is recorded as
**Blocked** and stays open until the page lands. A major release that claims the page must make its
UI case pass.

| Route | State in 3.x | UAT cases |
| --- | --- | --- |
| `/` | available | UAT-UI-01, UAT-SEA-01 to 06 |
| `/sign-up`, `/sign-in` | available | UAT-AUTH-01 to 06 |
| `/verify-email`, `/forgot-password`, `/reset-password` | available | UAT-AUTH-11 to 16 |
| `/listings/[id]` | available | UAT-LST-05, UAT-UI-02, UAT-UI-09 |
| `/compare` | guest preview available; save/share not built | UAT-CMP-01 to 03, UAT-UI-03 |
| `/groups` | not built | UAT-GRP-01 to 14, UAT-UI-04 (API pass, UI blocked) |
| `/notifications` | not built | UAT-NOT-01 to 06, UAT-UI-05 (API pass, UI blocked) |

## 2. Environment and data

Run the candidate build, not an old dev server:

```sh
script/run.sh --dev          # Postgres :5433, API :8000, frontend :3000
script/seed.sh --reset       # resets the development database and loads the demo world
```

- App: <http://localhost:3000>
- API reference: <http://127.0.0.1:8000/docs>
- Health: <http://127.0.0.1:8000/health> must report `{"status": "ok", "database": "postgres"}`.

`script/seed.sh --reset` deletes every row in the development database. Never point it at production.
Run it once before the session, then do not reseed between cases unless a case says so; several
cases depend on data created by earlier ones.

### Accounts

All demo passwords are `roomly1234`. Seeded accounts are already email-verified; accounts a tester
registers are not until they open the emailed link.

### Email links

Sign-up and password reset send a link by email. On a development stack the mail client only logs the
link (`ROOMLY_MAIL=log`), so find it in the backend log: `grep "mail verify_email" ` or
`"mail reset_password"` on the `script/run.sh` output, and open the URL it prints. On a deployed
environment, send to an address under `@roomly.bid` and read it at `https://mail.roomly.bid/`.

| Account | Role in the demo world |
| --- | --- |
| `maya@roomly.test` | Owner of "Bushwick crew", member of nothing else; the main persona |
| `alex@roomly.test` | Member of "Bushwick crew" |
| `sam@roomly.test` | Member of "Bushwick crew" |
| `priya@roomly.test` | Owner of "Astoria search"; has invited Maya |
| `admin@roomly.test` | Administrator; cannot be a group member |
| `jordan@example.com` | Invited to "Bushwick crew"; no account |

### Seeded data

- Listings: *Sunny 2BR near the Jefferson L* (Brooklyn, $3,200, 2BR, 850 sq ft, no broker fee,
  dishwasher + laundry), *Astoria studio* (Queens, $2,100, Unknown bathrooms/area/move-in),
  *560 W 144th St* (Manhattan, $4,150, 3BR, 1,100 sq ft, no coordinates), and a held duplicate of
  the Harlem address at $4,050 with different bathrooms/area.
- "Bushwick crew" has Maya (owner), Alex and Sam; three messages, two reactions, one open poll with
  votes 2/1/0, a comparison shared with the group, and a pending invitation to Jordan.
- "Astoria search" has Priya and a pending invitation to Maya.
- Maya has six notifications total across the demo accounts (three of them, two unread), two saved
  searches, two commute destinations.
- Administration: two sources, one queued duplicate pair, one open report.

### API testing

In Swagger, sign in with `POST /auth/sign-in`, copy `token`, click **Authorize**, and paste it. Use
the seeded account that owns the data in the case; a case that says "as Alex" means sign in as Alex.
Record the HTTP status and the relevant response fields as evidence.

## 3. Severity and release criteria

| Severity | Meaning | Examples |
| --- | --- | --- |
| P1 | Blocks the release | Cannot sign in, data loss, a member can read another group, wrong money or address, an admin action available to a normal user |
| P2 | Major, must be fixed or accepted | Wrong count, missing validation message, notification not delivered, duplicate review leaves both listings merged |
| P3 | Minor | Wording, alignment, a label that says "Unknown" twice |

The release passes when:

- every P1 and P2 case has been executed;
- no P1 is open;
- every open P2 has a written acceptance from the release manager with a target version;
- every Blocked case has a linked issue;
- the results table below is signed.

## 4. Recording results

Use one row per case. Status is `Pass`, `Fail`, `Blocked` or `N/A`. Attach evidence to the release
ticket: a screenshot for UI cases, method + path + status + a short body excerpt for API cases.

| ID | Status | Evidence / defect | Notes |
| --- | --- | --- | --- |
| UAT-XXX-00 | | | |

A defect entry needs: case ID, expected, actual, account, request (if API), and severity. File a P1
immediately; do not continue past a P1 in the same area.

## 5. Cases

### A. Access and account

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-AUTH-01 | Guest | Open `/`. Do not sign in. Apply a rent filter and sort by price. | Results load without a token. The header shows **Sign in**. Filter changes trigger a new search only on **Apply**, not per keystroke. |
| UAT-AUTH-02 | Guest | Open `/sign-up`. Register `uat1+<date>@example.com` with an 8-character password and a display name. Open the emailed link, then sign in. | Sign-up shows "Check your email" and creates **no** session (201 `{email, verification_sent: true}`). The link confirms the address; signing in then redirects to `/`. Header shows the display name. Reload keeps the session. A new tab is signed out (`sessionStorage` is per tab). |
| UAT-AUTH-03 | Guest | Try to register with `not-an-email`, a 7-character password, and an existing email. | Each attempt is rejected with a readable validation message; the duplicate email answers 409 "An account with this email already exists." No account is created. |
| UAT-AUTH-04 | Guest | Sign in with a wrong password, an unknown email, and the correct password with the email in upper case. | The first two answer 401 with the same "Invalid email or password." message. The third answers 200 (email is normalized) and lands on `/`. |
| UAT-AUTH-05 | Signed in | Reload the page, then click **Sign out**. | Reload restores the account through `GET /me`. Sign out answers 204; the header returns to **Sign in**; the old token answers 401. |
| UAT-AUTH-06 | Signed in | In the browser, open devtools > Application > Session storage > `roomly.session`, set `expires_at` to 30 seconds from now, reload, and wait. | After 30 seconds the app clears the session, shows "Your session has expired. Please sign in again.", and the header returns to **Sign in**. |
| UAT-AUTH-07 | Signed in | `DELETE /me` with a wrong password. | 401 "Invalid password."; the account still works. |
| UAT-AUTH-08 | Owner with members | As Maya, `DELETE /me` with the correct password. | 409 "Transfer ownership of your groups before deleting the account."; the account still works. |
| UAT-AUTH-09 | Member | Register and confirm `uat-delete+<date>@example.com`, have Maya invite it to "Bushwick crew", accept, post one message, then `DELETE /me` with the correct password. | 204. `GET /me` answers 401; the message in "Bushwick crew" now shows **Deleted user**; the account is gone from the member list; its sessions, inbox, saved searches and personal comparisons are gone. |
| UAT-AUTH-10 | Deleted user | Sign in as the disposable account from UAT-AUTH-09. | 401, with no indication that the account ever existed. |
| UAT-AUTH-11 | Guest | Register `uat2+<date>@example.com`, do not open the link, and sign in with the right password. Then sign in with a wrong password. | The right password answers 403 `email_not_verified` and the page offers "Send the link again". The wrong password answers 401 (the 403 is never shown to someone who does not know the password). |
| UAT-AUTH-12 | Guest | Open the confirmation link, then open the same link again. Request a link, wait 24 hours (or set `auth_token.expires_at` in the past), open it. | The first use confirms the address (204 / "Your email is confirmed"); the second and the expired one answer 422 `invalid_token` with a readable message. The address bar no longer shows `?token=` after the page loads. |
| UAT-AUTH-13 | Guest | On the unverified account use **Send the link again** twice within a minute, then four times within an hour. Also request it for an address that has no account. | Every request looks identical to the user (the page says "if … a new link is on its way"). Within the cooldown and after three links in an hour nothing new is sent. A link the mail service rejected does not count toward the limit. |
| UAT-AUTH-14 | Guest | Open `/forgot-password` for a real account and for an unknown address. | Both show the same "If an account exists…" message (202). Only the real account receives a reset link. |
| UAT-AUTH-15 | Signed in on two tabs | Use the reset link from UAT-AUTH-14 to choose a new password (7 characters first, then 8+). Reload both tabs, sign in with the old and the new password. | 7 characters is rejected and the link still works. After a valid reset both old sessions answer 401, the old password answers 401, the new one works, and the link cannot be used twice. A reset link older than 30 minutes answers 422. |
| UAT-AUTH-16 | Guest | Reset the password of an account that never confirmed its email. | The reset succeeds and the account can sign in afterwards (reading the mailbox proved the address). |
| UAT-AUTH-11 | Any | `GET /health` and `GET /openapi.json`. | 200, database reported, and the OpenAPI document lists all 56 endpoints plus `/health`. |

### B. Groups

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-GRP-01 | Signed in | `POST /groups` with `{"name": "UAT crew"}`. Use this group for the rest of section B unless a case names another. | 201; `my_role` is `owner`; exactly one member, the caller. It appears once in `GET /groups` with `member_count` 1. |
| UAT-GRP-02 | Non-member | As the new owner, get the group id. As Priya, `GET /groups/{id}` and `GET /groups/{id}/invitations`. | 403 on both. The group does not appear in Priya's `GET /groups`. |
| UAT-GRP-03 | Owner | `POST /groups/{id}/invitations` with Priya's email. As Priya, `GET /invitations`. | 201 with state `pending`; the invitee sees group name, inviter and expiry (7 days). |
| UAT-GRP-04 | Owner | Send the same invitation again. | 409; still exactly one pending invitation. |
| UAT-GRP-05 | Owner | Invite an existing member (Maya invites Alex to "Bushwick crew"), then invite `admin@roomly.test`. | 409 for the member; 403 for the administrator ("Administrators cannot join groups."). |
| UAT-GRP-06 | Invitee | `POST /invitations/{id}/accept`; call it a second time. | 201 both times; one membership row; `my_role` is `member`; the member list grows by exactly one. |
| UAT-GRP-07 | Invitee | Decline a different invitation, then try to accept it. | 204; then 409. The invitation list shows `declined`. |
| UAT-GRP-08 | Wrong person / expired | Create an invitation for `uat-wrong+<date>@example.com`; accept or decline it as Priya. Create another invitation for a disposable account, set its `expires_at` in the past (`UPDATE group_invitation ...`), then accept it. | 404 for the wrong person, so the invitation's existence is not confirmed. 409 "This invitation has expired." for the expired one; the invitee does not join. |
| UAT-GRP-09 | Owner | Fill "UAT crew" to six members using disposable accounts, then invite a seventh. | The invite answers 409 "A group has at most 6 members." If an invitation was already pending, accepting it also answers 409. |
| UAT-GRP-10 | Owner | With two or more members, `POST /groups/{id}/leave` as the owner. | 409; ownership must be transferred first. |
| UAT-GRP-11 | Owner | `POST /groups/{id}/transfer` to another member. As the new owner, read the group; as the old owner, read it. | 200; `my_role` is `member` for the old owner and `owner` for the new one; exactly one owner in the member list. |
| UAT-GRP-12 | Owner | `DELETE /groups/{id}/members/{user_id}` for a disposable member (not one of the seeded personas); then for the owner themselves. | 204 for the member, who then gets 403 on the group. 409 when the owner targets themselves. |
| UAT-GRP-13 | Sole owner | Create a group alone and leave it. | 204; `GET /groups/{id}` answers 404; the group is gone from `GET /groups`; its messages, polls and comparisons are gone. |
| UAT-GRP-14 | Member | `GET /groups`. | Every group shows the caller's role, current member count and creation time; dissolved or left groups are absent. |

### C. Listings

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-LST-01 | Signed in | `POST /listings` with address 10 UAT Street, unit 2A, Brooklyn 11201, rent 300000, 2 bedrooms, 1 bathroom, 600 sq ft, min lease 365, amenities `["dishwasher"]`. | 201, status `searchable`. The card shows rent, borough, price per sq ft 500 with its formula, one **Manual entry** source, and a price-history point. |
| UAT-LST-02 | Guest | Submit a listing with only address and rent; open its card. | 201. The response carries `null` for unknown values and lists them in `unknown`, including `coordinates`; the UI labels them **Unknown**, never zero or "no". |
| UAT-LST-03 | Signed in | Submit 11 Out Of Scope Street (no borough), then 12 Out Of Scope Street with `min_lease_days: 7`. Search with no filters. | Both are stored with status `excluded`; neither appears in search results; both cards remain readable. |
| UAT-LST-04 | Signed in | Submit 10 UAT Street, unit 2A, Brooklyn 11201 again with a different rent and bathroom count. | 201 with status `under_review`; it is not searchable; `GET /admin/duplicates?status=queued` includes a pair for 10 UAT Street showing the original `searchable` and the newcomer `under_review`. |
| UAT-LST-05 | Guest | Open `/listings/{id}` for the seeded Knickerbocker listing. | Card shows title, address, rent, net rent, lease term, broker fee, fees, beds/baths/area, move-in, amenities, availability, sources with timestamps, conflicts, price history and price per sq ft. |
| UAT-LST-06 | Signed in | `POST /listings/{id}/reports` with reason `wrong_value` and details. | 201, status `open`; the report appears in `GET /admin/reports` for an administrator. |
| UAT-LST-07 | Signed in | Submit latitude without longitude; net rent without a lease term; an invalid ZIP; an invalid URL. | 422 for each, located at the right field; nothing is stored. |
| UAT-LST-08 | Signed in | Submit a searchable listing with a rent, then open its card. | Exactly one price-history point and no duplicate source record on repeated reads. |

### D. Administration

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-ADM-01 | Non-admin | As Maya, call every `/admin/*` route, including a write. | 403 on all; no data changes. |
| UAT-ADM-02 | Admin | `GET /admin/sources`; create `UAT Feed`; create it again; patch it to `enabled: false`; patch its name and `config`. | 200 with the two seeded sources; 201 for the new one; 409 for the duplicate name; 200 and `enabled` false after the first patch; the name and config changes are returned and survive a re-read. |
| UAT-ADM-03 | Admin | `GET /admin/duplicates?status=queued`; open the pair for 560 W 144th St. | The queue includes the seeded pair and any pair created by UAT-LST-04; both sides show record id, collection time, listing summary and status. Filtering by `merged` or `separate` shows the reviewed pairs. |
| UAT-ADM-04 | Admin | Merge the pair whose newcomer is titled "3BR in Harlem". Then open the surviving 560 W 144th St card. | 200, status `merged`. The survivor keeps its own known values, fills any Unknown value from the other record, lists both source records, and records disagreements under `conflicts`. The other listing now has status `merged` and points at the survivor. |
| UAT-ADM-05 | Admin | Split the merged pair. | 200, status `separate`. The previously merged listing is `searchable` (or `excluded` if out of scope), has no merge pointer, and the survivor no longer lists the pair's conflicts. |
| UAT-ADM-06 | Admin | Submit another duplicate of a searchable address, then `keep-separate` it. | 200, status `separate`; the held listing becomes `searchable` and appears in search. |
| UAT-ADM-07 | Admin | `GET /admin/reports?status=open`; resolve the seeded report; resolve it again. Submit a second report as a user and dismiss it; filter `resolved` and `dismissed`. | The open report is listed; 200 with status `resolved`; 409 on the second attempt; the second report is `dismissed`; the filters return each report once. |

### E. Search and saved inputs

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-SEA-01 | Guest | Search with `min_rent_cents=200000&max_rent_cents=350000`. | The Queens, 10 UAT Street and seeded Brooklyn listings; the Manhattan listing is excluded. Boundary values are inclusive. |
| UAT-SEA-02 | Guest | Search `borough=brooklyn`, then `borough=brooklyn&borough=queens`; search `min_bedrooms=3`; `min_area_sqft=1000`; `move_in_from=2027-01-01`. | Two, three, one (Manhattan), one (Manhattan), one (Manhattan) respectively. Listings with an Unknown value for an active constraint are excluded. |
| UAT-SEA-03 | Guest | Search `amenity=dishwasher`, `amenity=dishwasher&amenity=laundry_in_building`, `no_broker_fee=true`. | Two, one (the seeded Brooklyn listing), and one (the same listing) respectively. A listing with an Unknown broker fee fails `no_broker_fee`. |
| UAT-SEA-04 | Guest | Search with a viewport around north Brooklyn; then give only `south` and `west`. | The viewport returns the seeded Brooklyn and Queens listings; the Manhattan and 10 UAT Street listings have no coordinates and are excluded. An incomplete viewport answers 422. |
| UAT-SEA-05 | Guest | Search `sort=rent_asc`, `rent_desc`, `newest`; use `limit=1&offset=1`; read `total`. | Ascending is Queens, 10 UAT Street, seeded Brooklyn, Manhattan; descending is the reverse. `total` is the unpaged count, `items` respects limit/offset. |
| UAT-SEA-06 | Guest | Search with `sort=cheapest`, `limit=0`, and `min_rent_cents=500&max_rent_cents=100`. | Each answers 422; the error location is the query parameter. |
| UAT-SEA-07 | Signed in | Create a saved search "UAT Brooklyn" with `boroughs: ["brooklyn"]`; list it; run it; delete it; run it again. As Priya, run Maya's search id. | 201; listed; the run returns the Brooklyn listings; 204 on delete; 404 on the second run; 404 for another account's search. |
| UAT-SEA-08 | Signed in | As the account registered and confirmed in UAT-AUTH-02 (no destinations yet), add three commute destinations; add a fourth; delete one; delete it again. | Three 201s; the fourth answers 409; 204 on delete; 404 on the second delete. |
| UAT-SEA-09 | Signed in | Save a search with a bad rent range, then with 500-character name. | 422 at the offending field; nothing is stored. |

### F. Comparison

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-CMP-01 | Guest | `POST /comparisons/preview` with the Brooklyn and Queens listing ids. | 200; two summary columns and nine rows (rent, net rent, broker fee, price/sq ft, borough, bedrooms, area, move-in, commute). Rent marks the Queens listing **best**; price per sq ft and broker fee have only one known value each, so no cell is best there; commute is Unknown for all and the note says commute estimates are unavailable. |
| UAT-CMP-02 | Guest | Preview the Queens and Manhattan listings, then only one listing, then five listings, then the same id twice. | No row marks a best cell unless at least two values are known, and a tie never marks a cell best. One, five and duplicate ids each answer 422. |
| UAT-CMP-03 | Signed in | Save a comparison of Brooklyn and Queens. As Priya, read it. | 201 with the table, `changes` all `unchanged`, `stale` false. It appears in `GET /comparisons` for its owner. Priya gets 403. |
| UAT-CMP-04 | Signed in | Share the saved comparison with "Bushwick crew"; share it again; as Sam, `GET /groups/{id}/comparisons`. | 200 with `group_id` and `shared_at`; the second share answers 409; Sam sees it in the group list and can open it. |
| UAT-CMP-05 | Signed in | Change the saved Brooklyn listing's advertised rent directly (`UPDATE listing SET advertised_rent_cents = ...`), then reopen the comparison. | `stale` is true; the changed listing reports state `changed` with `advertised_rent_cents` and `price_per_sqft_cents`; the saved snapshot is not silently replaced. |
| UAT-CMP-06 | Signed in | Share a comparison to a group the caller is not in. | 403; nothing is shared. |
| UAT-CMP-07 | Signed in | As the owner of a personal comparison, `GET /comparisons/{id}`; as a different account, do the same. | 200 for the owner; 403 for the other account. |

### G. Group room

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-ROOM-01 | Non-member | As Priya, read and post messages, create a poll, vote and close for "Bushwick crew". | 403 on every action; nothing is created. |
| UAT-ROOM-02 | Member | `POST /groups/{id}/messages` with `{"body": "UAT hello"}`; list messages. | 201; the message appears first (newest first) with the author, time and empty reactions. `limit` and `before` page backwards without duplicates. |
| UAT-ROOM-03 | Member | Post a message with `listing_id`; list with that filter. Post one with `comparison_id`; list with that filter. Then, as Priya, save a comparison in "Astoria search", and as Maya try to post it in "Bushwick crew". | Each thread returns only its messages; the cross-group comparison answers 404. |
| UAT-ROOM-04 | Member | React with 🎉; react again with 👍; read the counts; remove the reaction. | One reaction per member: the second replaces the first. Counts and `mine` are correct for the viewer. Removing leaves no row for that member. |
| UAT-ROOM-05 | Member | Create a poll with two options, then with one, then with five, then with two identical options. List the group's polls and open the new poll. | 201 for two; 422 for one, five and duplicates. The list contains the new poll once and `GET /polls/{id}` returns its options and zero votes. |
| UAT-ROOM-06 | Member | Vote for option A; change to option B; read the poll. | 200 both times; totals move from A to B; `my_vote` follows the member; only current members' votes count. |
| UAT-ROOM-07 | Member / owner | As Sam, close a poll Maya created; as Maya, close it. Then vote again. | 403 for Sam; 200 and `state: closed` for Maya; voting after close answers 409. |
| UAT-ROOM-08 | Member | Read a poll as a non-member and as a member of the group. | 403 for the non-member; 200 with totals for the member. |

### H. Notifications

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-NOT-01 | Member | As Maya, post a message in "Bushwick crew". As Alex, `GET /notifications`. | Alex has an unread `message` notification naming the group and the author; `total` and `unread` match the list. The author does not receive one for their own message. |
| UAT-NOT-02 | Signed in | Mark one notification read; read it again; mark another user's notification read. | 200 with `read: true` both times; the unread count drops once; the foreign notification answers 404. |
| UAT-NOT-03 | Signed in | Read `GET /notifications?unread=true`; `POST /notifications/read-all`; read the inbox again and the unread filter. | The unread filter returns only unread items; `{"marked": n}` matches that number; the next inbox has `unread: 0`; calling read-all again marks 0. |
| UAT-NOT-04 | Signed in | Read the settings; turn off `message`, email and digest; post a group message; read the inbox. | 200 and the settings echo back; the unread count does not grow and no new message notification arrives. Turn `message` back on and confirm delivery resumes. |
| UAT-NOT-05 | Signed in | `PUT /me/notification-settings` with only `quiet_start`, then with both quiet hours. | 422 for the single value; 200 for the pair; `GET` returns the saved pair. |
| UAT-NOT-06 | Signed in | Open a `message` notification. | It names the group, the author, the listing when the message belongs to one, and the time; it never exposes another group's content. |

### I. Pages and navigation

| ID | Role | Steps | Expected |
| --- | --- | --- | --- |
| UAT-UI-01 | Guest / signed in | Use every header link and the account area on a 1280px and a 390px viewport. | Search works for guests; signing in updates the header without a reload; sign-out restores **Sign in**; the layout is usable at both widths. |
| UAT-UI-02 | Guest | Open a listing from the search results. | The detail page renders the card with sources, conflicts, price history and price per sq ft, and a back link. Null values read Unknown; zero fees display $0.00; merged listings link to the survivor. |
| UAT-UI-03 | Guest / signed in | Select 2–4 listings from search or details, open `/compare`, remove listings and clear selection. | Preview works without authentication. Selection survives route changes and reloads. A fifth selection is disabled. Unknown values and API best-value indicators render correctly. Saving/sharing remains API-only. |
| UAT-UI-04 | Signed in | Open `/groups`, create a group, invite, accept, transfer, leave. | In 3.x the route is **Blocked**; execute UAT-GRP-01 to 14 through `/docs`. |
| UAT-UI-05 | Signed in | Open `/notifications`, mark one read, mark all read, open the settings. | In 3.x the route is **Blocked**; execute UAT-NOT-01 to 06 through `/docs`. |
| UAT-UI-06 | Any | While signed out, open a group or notification page directly. | The app asks the user to sign in instead of showing data or a server error. Until the pages exist this is **Blocked**. |
| UAT-UI-07 | Keyboard / screen reader | Tab through `/` and `/sign-in`: filters, apply, sort, cards, submit. | Focus is visible, every field has a label, the header and auth messages use `role="status"` / `role="alert"`, and the form can be completed without a mouse. |
| UAT-UI-08 | Any | Stop the backend and reload `/`. | The dashboard shows "Could not load listings. Is the backend running on :8000?" and does not blank the page; restarting and reloading recovers. |

Listing detail checks (UAT-UI-09): on desktop and mobile, open a seeded listing and an unknown ID;
verify sources, timestamps, conflicts, empty history, and the missing-listing message. Stop the API,
reload the detail page, restart the API and use Try again. As a guest, check the report sign-in prompt;
as a signed-in user, submit each report reason with optional details and verify the confirmation and
created report. Check pending submission, API failure, expired-session handling and keyboard access.

Guest comparison checks: open `/compare` with zero and one selection; confirm no preview is requested.
Select four listings across searches, verify a fifth cannot be added, then remove one and add another.
Check cents, zero fees, tied values (no Best badge), and Unknowns. Change selection during a slow
request; the old result must not replace the new selection. Stop the API and retry after restarting.
Confirm a missing listing can be removed using the selection bar. Test at 390px and with keyboard
navigation, including horizontal table scrolling. Verify reload persistence and clear selection.

## 6. Traceability

| SSDS use case | Cases |
| --- | --- |
| §8.1.2.1 Login | UAT-AUTH-01 to 11, UAT-UI-01, UAT-UI-07 |
| §8.1.2.2 Group Management | UAT-GRP-01 to 14, UAT-UI-04 |
| §8.1.2.3 Listing Submission and cards | UAT-LST-01 to 08, UAT-UI-02 |
| §8.1.2.4 Listing Administration | UAT-ADM-01 to 07 |
| §8.1.2.5 Search and Ranking | UAT-SEA-01 to 09, UAT-UI-08 |
| §8.1.2.6 Comparison | UAT-CMP-01 to 07, UAT-UI-03 |
| §8.1.2.7 Group Discussion | UAT-ROOM-01 to 08 |
| §8.1.2.8 Notifications | UAT-NOT-01 to 06, UAT-UI-05 |
| Account deletion (R-1.4) | UAT-AUTH-09, UAT-AUTH-10 |
| Administrator only (R-2.4) | UAT-ADM-01 |

## 7. Release checklist

- [ ] Candidate built from the release branch; CI green (backend lint/test, frontend build).
- [ ] `script/seed.sh --reset` on the UAT database; `/health` returns `ok`.
- [ ] All P1 and P2 cases executed; results table filled with evidence.
- [ ] No open P1. Every open P2 accepted in writing by the release manager.
- [ ] Every Blocked case has a linked issue and a target version.
- [ ] Defects triaged into the next patch or minor release.
- [ ] Sign-off below completed; then tag `vX.0.0` with `script/release.sh`.

## 8. Sign-off

| | Name | Date | Result |
| --- | --- | --- | --- |
| Tested by | | | |
| Release manager | | | |
| Product owner | | | |

Notes:

```text
Open defects:
Accepted risks:
Blocked cases and issue links:
```
