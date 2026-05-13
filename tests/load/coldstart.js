// tests/load/coldstart.js
// ─────────────────────────
// k6 load test — async cold-start scaling.
//
// Each iteration: submit a cold-start job, then poll /jobs/{id} until completed.
// Records two custom Trends:
//   coldstart_submit_ms  — submit phase only (HTTP request to /coldstart)
//   coldstart_e2e_ms     — full time-to-result (submit + queue + worker + poll)
//
// Run with:
//   k6 run \
//     --out csv=tests/load/results/{N}workers/k6_raw.csv \
//     -e API_BASE=http://localhost:8000 \
//     -e SUPABASE_URL=https://<project>.supabase.co \
//     -e SUPABASE_ANON_KEY=<anon> \
//     -e ADMIN_EMAIL=admin@example.com \
//     -e ADMIN_PASSWORD=<password> \
//     tests/load/coldstart.js
//
// HTML dashboard:
//   K6_WEB_DASHBOARD=true K6_WEB_DASHBOARD_EXPORT=tests/load/results/{N}workers/k6_report.html

import http from 'k6/http';
import { check, sleep, fail } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// ── Config from env ────────────────────────────────────────────────────────
const API_BASE         = __ENV.API_BASE         || 'http://localhost:8000';
const SUPABASE_URL     = __ENV.SUPABASE_URL;
const SUPABASE_ANON    = __ENV.SUPABASE_ANON_KEY;
const POLL_INTERVAL_MS = 500;
const POLL_TIMEOUT_MS  = 60000;

// Admin account pool — created by scripts/create_admin_pool.py
// Each VU rotates through these accounts so the route's per-user dedup
// (single in-flight job per user_id) doesn't artificially serialize the load.
const ADMIN_POOL = JSON.parse(open('./admin_pool.json')).accounts;

// ── Custom metrics ─────────────────────────────────────────────────────────
const submitMs  = new Trend('coldstart_submit_ms');
const e2eMs     = new Trend('coldstart_e2e_ms');
const completed = new Counter('coldstart_completed');
const failed    = new Counter('coldstart_failed');
const timedOut  = new Counter('coldstart_timeout');
const pollOk    = new Rate('poll_success_rate');

// ── Test profile ───────────────────────────────────────────────────────────
export const options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '2m',  target: 10 },
    { duration: '30s', target: 50 },
    { duration: '2m',  target: 50 },
    { duration: '30s', target: 100 },
    { duration: '2m',  target: 100 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    'coldstart_submit_ms': ['p(95)<500'],
    'poll_success_rate':   ['rate>0.99'],
    'http_req_failed':     ['rate<0.01'],
  },
};

// ── Setup: login all admin accounts in the pool ────────────────────────────
export function setup() {
  if (!SUPABASE_URL || !SUPABASE_ANON) {
    fail('SUPABASE_URL and SUPABASE_ANON_KEY must be set');
  }
  if (!ADMIN_POOL || ADMIN_POOL.length === 0) {
    fail('admin_pool.json is missing or empty — run scripts/create_admin_pool.py first');
  }

  const tokens = [];
  for (const account of ADMIN_POOL) {
    const res = http.post(
      `${SUPABASE_URL}/auth/v1/token?grant_type=password`,
      JSON.stringify({ email: account.email, password: account.password }),
      {
        headers: {
          'Content-Type': 'application/json',
          'apikey': SUPABASE_ANON,
        },
      }
    );
    if (res.status !== 200) {
      fail(`Login failed for ${account.email}: ${res.status} ${res.body}`);
    }
    tokens.push(res.json('access_token'));
  }
  console.log(`[setup] logged in ${tokens.length} admin accounts`);
  return { tokens };
}

// ── Sample answers (a few presets to add a bit of variance) ────────────────
const ANSWER_PRESETS = [
  {
    q1_media_type: 'both',
    q2_genres: 'Action, Adventure',
    q3_title: 'Inception',
    q4_dark: 'fine with it',
    q5_familiar: 'something new',
  },
  {
    q1_media_type: 'movies',
    q2_genres: 'Drama, Mystery',
    q3_title: 'The Godfather',
    q4_dark: 'prefer lighter',
    q5_familiar: 'no preference',
  },
  {
    q1_media_type: 'shows',
    q2_genres: 'Sci-Fi, Thriller',
    q3_title: 'Breaking Bad',
    q4_dark: 'fine with it',
    q5_familiar: 'something familiar',
  },
];

// ── Default VU function ────────────────────────────────────────────────────
export default function (data) {
  // Round-robin tokens across VUs so per-user dedup doesn't serialize.
  const token = data.tokens[(__VU - 1) % data.tokens.length];
  const headers = {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  };

  const body = ANSWER_PRESETS[Math.floor(Math.random() * ANSWER_PRESETS.length)];

  // ── Submit ──────────────────────────────────────────────────────────────
  const t0 = Date.now();
  const submitRes = http.post(
    `${API_BASE}/recommend/coldstart`,
    JSON.stringify(body),
    { headers, tags: { name: 'submit' } }
  );
  const submitElapsed = Date.now() - t0;
  submitMs.add(submitElapsed);

  const submitOk = check(submitRes, {
    'submit status 200': (r) => r.status === 200,
    'submit returned job_id': (r) => r.json('job_id') !== undefined,
  });

  if (!submitOk) {
    failed.add(1);
    if (submitRes.status === 503) {
      console.warn(`[submit] 503 — queue unavailable`);
    } else if (submitRes.status === 429) {
      console.warn(`[submit] 429 — unexpected rate limit (admin should bypass)`);
    } else {
      console.warn(`[submit] ${submitRes.status} ${submitRes.body}`);
    }
    return;
  }

  const jobId = submitRes.json('job_id');

  // ── Poll until completed or timeout ─────────────────────────────────────
  const pollDeadline = t0 + POLL_TIMEOUT_MS;
  let status = 'pending';
  let pollAttempts = 0;

  while (Date.now() < pollDeadline) {
    sleep(POLL_INTERVAL_MS / 1000);
    pollAttempts += 1;

    const pollRes = http.get(`${API_BASE}/jobs/${jobId}`, {
      headers,
      tags: { name: 'poll' },
    });

    if (pollRes.status !== 200) {
      pollOk.add(false);
      continue;
    }
    pollOk.add(true);

    // When status === 'completed' the API returns the result shape (no `status` field)
    // identified by the `algorithm` key. When still in-flight it returns {id, status, ...}.
    const body = pollRes.json();
    if (body && body.algorithm) {
      const e2e = Date.now() - t0;
      e2eMs.add(e2e);
      completed.add(1);
      return;
    }
    status = body ? body.status : null;
    if (status === 'failed') {
      failed.add(1);
      console.warn(`[job ${jobId}] failed after ${pollAttempts} polls`);
      return;
    }
  }

  // Timeout
  timedOut.add(1);
  console.warn(`[job ${jobId}] still ${status} after ${POLL_TIMEOUT_MS}ms`);
}

// ── Teardown ───────────────────────────────────────────────────────────────
export function teardown(data) {
  console.log('[teardown] test complete');
}
