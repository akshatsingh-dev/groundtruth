# Getting a CourtListener API token

Checked live on 2026-08-05. You are **not** currently signed in to CourtListener in Chrome —
visiting the token page redirects to the sign-in wall, so you need to register or sign in first.

## Steps

1. Go to https://www.courtlistener.com/profile/api-token/. If you are signed out you land on
   `https://www.courtlistener.com/sign-in/?next=/profile/api-token/`.
2. If you already have an account, sign in there with your username and password. Skip to step 6.
3. If you do not have an account, click **Need to register?** at the bottom left of the sign-in
   box. That goes to `https://www.courtlistener.com/register/?next=/profile/api-token/`.
4. Fill in the registration form. All fields are required: User Name, Email Address, Password,
   Confirm Password, First Name, Last Name. Then tick the consent checkbox and solve the hCaptcha
   ("I am human"). Click **Register**.
5. CourtListener sends a confirmation email. Click the link in it to verify the address. In
   practice the mail arrives within a minute or two; check spam if it does not.
6. You are returned to https://www.courtlistener.com/profile/api-token/. The token is already
   there — every CourtListener account gets one at signup. There is no application, approval, or
   waiting period for the free tier, and the token works immediately.
7. Copy the token from the box on that page and put it in `.env` as the CourtListener key. Do not
   paste it into chat, a commit, or a log.

The token is a 40-character lowercase hex string (CourtListener uses Django REST Framework's
`TokenAuthentication`). Send it as an HTTP header, not a query parameter:

```
Authorization: Token <your-token-here>
```

Forgetting the literal word `Token` is the most common mistake; the request then counts as
anonymous and gets throttled much sooner.

Related pages: https://www.courtlistener.com/profile/api-usage/ shows your recent usage against
the limits.

## Resetting the token

The same page has a **Reset API Token** button. Clicking it shows a confirmation page with your
token's usage over the last five minutes, then asks for your password before it takes effect.
Resetting is immediate and irreversible, and it breaks anything still using the old token, so
only do it if the key leaks.

## Rate limits

The documented free-tier limits are confirmed: **5 requests per minute, 50 per hour, 125 per day**
for an authenticated account.

- All three throttles apply at once; whichever is most restrictive given recent traffic is what
  blocks the next request.
- They are rolling windows, not calendar-day resets. Budget naturally refills as older requests
  age out.
- Over the limit you get `HTTP 429` with a `Retry-After` header giving the seconds to wait. That
  value can be large — tens of thousands of seconds once the daily cap is hit.
- Creating extra accounts to widen the limit violates CourtListener's terms.

One caveat on timing: Free Law Project is running a promotion that doubles free-tier API access
through **August 6, 2026** — so right now the account will behave as 10/min, 100/hr, 250/day. That
expires tomorrow and drops back to 5/50/125. Size everything against 125/day, not the promo
numbers.

### What this means for us

125 requests a day is very tight, which is exactly why the ingest layer caches responses to disk
with a 7-day TTL. Practical consequences:

- Treat a cache miss as expensive. A full uncached sweep must stay well under 125 calls or it
  will not finish in a day.
- Keep the 5/min ceiling in mind too — serial requests need roughly 12 seconds of spacing, and
  bursty parallel fetching will trip the per-minute throttle long before the daily one.
- Handle `429` by reading `Retry-After` and backing off rather than retrying immediately.
- Never clear the cache casually; a cold cache costs real quota.

## Paid tiers

A Free Law Project membership raises the limits. Individual tiers, monthly or yearly:

| Tier | Price | API limits |
|---|---|---|
| Free | $0 | 5/min, 50/hr, 125/day |
| Tier 1 | $10/mo or $100/yr | 10/min, 75/hr, 300/day |
| Tier 2 | $25/mo or $250/yr | 15/min, 150/hr, 600/day |
| Tier 3 | $50/mo or $500/yr | 20/min, 250/hr, 1,000/day |
| Tier 4 | $100/mo or $1,000/yr | 25/min, 300/hr, 1,400/day |

Membership API access is intended for small firms, small government bodies, legal services
organizations, small media, academics, and pre-revenue organizations — not large or funded ones.
Group plans and free EDU memberships (valid `.edu` address) also exist. Details at
https://free.law/membership/.

Tier 1 at $10/month would take us from 125 to 300 requests a day, which is the cheapest thing that
meaningfully loosens the constraint if the cache stops being enough.
