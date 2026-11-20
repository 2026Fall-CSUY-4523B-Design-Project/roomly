# Endpoints

The behavior of each endpoint, from the SSDS. Every route is implemented; validation (422) and
authentication (401) run before the service. "Guest" means no token is needed; every other route
takes `Authorization: Bearer <token>` from sign-up or sign-in. Request and response schemas are in
`/openapi.json`.

## Login (§8.1.2.1)
| | |
| --- | --- |
| `POST /auth/sign-up` | guest · create an account and email a confirmation link; answers `201 {email, verification_sent}` and **no session** (`verification_sent` is false when the mail service was down; resend) |
| `POST /auth/verify-email` | guest · `{token}` from the emailed link → `204`; a link works once and lasts 24 hours; invalid or used → `422` with `detail.code = "invalid_token"` |
| `POST /auth/verify-email/resend` | guest · `{email}` → `202` always, whether or not the address needs confirming |
| `POST /auth/forgot-password` | guest · `{email}` → `202` always; mails a reset link when the account exists |
| `POST /auth/reset-password` | guest · `{token, password}` → `204`; sets the password, signs the account out everywhere and spends its other reset links; a link works once and lasts 30 minutes |
| `POST /auth/sign-in` | guest · sign in with email and password; an unconfirmed address gets `403` with `detail.code = "email_not_verified"` (only after the password matched) |
| `POST /auth/sign-out` | invalidate this session |
| `GET /me` | the signed-in account |
| `DELETE /me` | delete the account (the password confirms it); shared content then shows "Deleted user" |

Emailed links: one per minute and three per hour per account and kind, counted from `auth_token`
rows; a request over the limit still answers `202` and sends nothing. A link that the mail service
rejected is discarded and does not count. Only the SHA-256 of a token is stored. A successful reset
also confirms the address, because the person just proved they read that mailbox. Errors that a
client may branch on carry `detail: {"code", "message"}` instead of a plain string.

Mail is sent by the Cloudflare Worker in `mail/` (`ROOMLY_MAIL=http`); in development the links are
written to the backend log (`ROOMLY_MAIL=log`).

## Group Management (§8.1.2.2)
| | |
| --- | --- |
| `POST /groups` | create a group; you become its owner |
| `GET /groups` | your current groups |
| `GET /groups/{id}` | a group and its current members |
| `POST /groups/{id}/invitations` | owner · invite by email |
| `GET /groups/{id}/invitations` | invitations the group has sent |
| `POST /groups/{id}/leave` | leave; an owner transfers ownership first, and a sole member leaving dissolves the group |
| `POST /groups/{id}/transfer` | owner · hand ownership to another member |
| `DELETE /groups/{id}/members/{user_id}` | owner · remove a member |
| `GET /invitations` | pending invitations addressed to you |
| `POST /invitations/{id}/accept` · `/decline` | respond to an invitation |

## Listing Submission and cards (§8.1.2.3)
| | |
| --- | --- |
| `POST /listings` | submit by manual entry; possible duplicates are held for review |
| `GET /listings/{id}` | guest · the full card with sources, conflicts, price history and price per sq ft (with its formula) |
| `POST /listings/{id}/reports` | report wrong data or a wrong merge |

## Listing Administration (§8.1.2.4), administrators only
| | |
| --- | --- |
| `GET /admin/sources` · `POST /admin/sources` · `PATCH /admin/sources/{id}` | listing sources |
| `GET /admin/duplicates` | the duplicate review queue |
| `POST /admin/duplicates/{id}/merge` · `/keep-separate` · `/split` | decide a candidate pair, or undo a merge |
| `GET /admin/reports` · `POST /admin/reports/{id}/resolve` | user data reports |

## Search and Ranking (§8.1.2.5)
| | |
| --- | --- |
| `GET /search` | guest · hard constraints only (rent, borough, bedrooms, area, move-in, amenities, no broker fee, viewport). Repeat `borough` or `amenity` to pass several values. An Unknown value fails any active constraint on it. |
| `GET /saved-searches` · `POST /saved-searches` · `DELETE /saved-searches/{id}` | saved criteria |
| `GET /saved-searches/{id}/results` | re-run a saved search |
| `GET /me/commute-destinations` · `POST` · `DELETE /{id}` | up to three destinations |

## Comparison (§8.1.2.6)
| | |
| --- | --- |
| `POST /comparisons/preview` | guest · compare 2–4 listings without saving. Best value is highlighted only among at least two known, untied values. |
| `POST /comparisons` · `GET /comparisons` · `GET /comparisons/{id}` | save, list and open comparisons; a saved one flags the values that changed since it was saved instead of replacing them |
| `POST /comparisons/{id}/share` · `GET /groups/{id}/comparisons` | share with a group |

## Group Discussion (§8.1.2.7)
| | |
| --- | --- |
| `GET /groups/{id}/messages?before=...` · `POST` | room messages, newest first, with cursor paging |
| `PUT /messages/{id}/reaction` · `DELETE` | one reaction per member |
| `POST /groups/{id}/polls` · `GET` · `GET /polls/{id}` | polls with 2–4 options |
| `PUT /polls/{id}/vote` · `POST /polls/{id}/close` | vote or change a vote; the creator or the owner closes the poll |

## Notifications (§8.1.2.8)
| | |
| --- | --- |
| `GET /notifications` | your notifications with unread count |
| `POST /notifications/{id}/read` · `/read-all` | mark as read |
| `GET /me/notification-settings` · `PUT` | kinds, email, digest, quiet hours |

Plus `GET /health`, which reports the engine in use and is not part of the SSDS surface.
