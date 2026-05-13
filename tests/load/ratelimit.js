// tests/load/ratelimit.js
// ────────────────────────
// k6 rate-limit verification — proves the cold-start 429 response under burst.
//
// Submits 8 jobs as a single REGULAR user. Asserts:
//   • Submits 1..5 → 200, with job_id present
//   • Submits 6..8 → 429, with structured detail body
//     { code, message, limit, used, remaining, reset_at }
//
// Run with:
//   k6 run \
//     --out csv=tests/load/results/ratelimit/k6_raw.csv \
//     -e API_BASE=http://localhost:8000 \
//     -e SUPABASE_URL=https://<project>.supabase.co \
//     -e SUPABASE_ANON_KEY=<anon> \
//     -e USER_EMAIL=loadtest@example.com \
//     -e USER_PASSWORD=<password> \
//     tests/load/ratelimit.js
//
// PREREQUISITE: the regular user must have <5 non-failed jobs in the last hour.
// If you've recently tested, wait or use a different account.

import http from 'k6/http';
import { check, sleep, fail } from 'k6';
import { Counter } from 'k6/metrics';

const API_BASE       = __ENV.API_BASE       || 'http://localhost:8000';
const SUPABASE_URL   = __ENV.SUPABASE_URL;
const SUPABASE_ANON  = __ENV.SUPABASE_ANON_KEY;
const USER_EMAIL     = __ENV.USER_EMAIL;
const USER_PASSWORD  = __ENV.USER_PASSWORD;

const accepted = new Counter('submits_accepted');
const blocked  = new Counter('submits_blocked');

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    'submits_accepted': ['count==5'],
    'submits_blocked':  ['count==3'],
  },
};

export function setup() {
  if (!SUPABASE_URL || !SUPABASE_ANON || !USER_EMAIL || !USER_PASSWORD) {
    fail('SUPABASE_URL, SUPABASE_ANON_KEY, USER_EMAIL, USER_PASSWORD must be set');
  }

  const res = http.post(
    `${SUPABASE_URL}/auth/v1/token?grant_type=password`,
    JSON.stringify({ email: USER_EMAIL, password: USER_PASSWORD }),
    {
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON,
      },
    }
  );
  if (res.status !== 200) {
    fail(`Supabase login failed: ${res.status} ${res.body}`);
  }

  // Also fetch current quota so we can fail fast if window already used
  const token = res.json('access_token');
  const quotaRes = http.get(`${API_BASE}/recommend/coldstart/quota`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const quota = quotaRes.json();
  if (quota.is_admin) {
    fail(`User ${USER_EMAIL} is admin — needs to be a regular user for this test`);
  }
  if (quota.remaining < 5) {
    fail(`User ${USER_EMAIL} has only ${quota.remaining} slots remaining — wait for window reset`);
  }

  console.log(`[setup] quota check OK — used=${quota.used}, remaining=${quota.remaining}`);
  return { token };
}

const ANSWERS = {
  q1_media_type: 'both',
  q2_genres: 'Action',
  q3_title: 'Inception',
  q4_dark: 'fine with it',
  q5_familiar: 'something new',
};

function waitForJobDone(headers, jobId) {
  // Poll until the job is no longer pending/running, so the next submit
  // sees a clean dedup state and actually counts toward the rate-limit quota.
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    sleep(0.5);
    const r = http.get(`${API_BASE}/jobs/${jobId}`, { headers });
    if (r.status !== 200) continue;
    const body = r.json();
    if (body && body.algorithm) return true;             // completed
    if (body && body.status === 'failed') return true;
  }
  return false;
}

export default function (data) {
  const headers = {
    Authorization: `Bearer ${data.token}`,
    'Content-Type': 'application/json',
  };

  // 5 valid submits, each waited to completion so dedup never short-circuits.
  for (let i = 1; i <= 5; i++) {
    const res = http.post(
      `${API_BASE}/recommend/coldstart`,
      JSON.stringify(ANSWERS),
      { headers, tags: { attempt: String(i) } }
    );
    const ok = check(res, {
      [`attempt ${i}: status 200`]: (r) => r.status === 200,
      [`attempt ${i}: has job_id`]: (r) => !!r.json('job_id'),
    });
    if (ok) accepted.add(1);
    const jobId = res.json('job_id');
    console.log(`[attempt ${i}] ${res.status} job=${jobId} status=${res.json('status')}`);
    waitForJobDone(headers, jobId);
  }

  // 3 more — these must all be 429 (no in-flight job, quota exhausted).
  for (let i = 6; i <= 8; i++) {
    const res = http.post(
      `${API_BASE}/recommend/coldstart`,
      JSON.stringify(ANSWERS),
      { headers, tags: { attempt: String(i) } }
    );
    const ok = check(res, {
      [`attempt ${i}: status 429`]: (r) => r.status === 429,
      [`attempt ${i}: has limit field`]: (r) => r.json('detail.limit') === 5,
      [`attempt ${i}: has reset_at`]: (r) => !!r.json('detail.reset_at'),
      [`attempt ${i}: has remaining=0`]: (r) => r.json('detail.remaining') === 0,
    });
    if (ok) blocked.add(1);
    console.log(`[attempt ${i}] ${res.status} body=${res.body}`);
    sleep(1);
  }
}
