import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Counter, Rate } from 'k6/metrics';

const BASE_URL = String(__ENV.BASE_URL || 'http://127.0.0.1:8088').replace(/\/+$/, '');
const USERNAME = __ENV.USERNAME || 'admin';
const PASSWORD = __ENV.PASSWORD || 'admin123';

const THINK_TIME = Number(__ENV.THINK_TIME || '0.2');
const REPORT_PAGE_SIZE = Number(__ENV.REPORT_PAGE_SIZE || '20');
const REPORT_QUERY = __ENV.REPORT_QUERY || '';
const REPORT_STATUS = __ENV.REPORT_STATUS || '';

const INCLUDE_EXPORT = String(__ENV.INCLUDE_EXPORT || 'false').toLowerCase() === 'true';
const EXPORT_MODE = __ENV.EXPORT_MODE || 'multi_sheet';

const loginFailures = new Counter('login_failures');
const apiCheckFailure = new Rate('api_check_failure');
const endpointHealthReqs = new Counter('endpoint_health_reqs');
const endpointAdminReportsReqs = new Counter('endpoint_admin_reports_reqs');
const endpointDoctorReportsReqs = new Counter('endpoint_doctor_reports_reqs');

function parseStages(raw) {
  const fallback = [
    { duration: '30s', target: 5 },
    { duration: '2m', target: 20 },
    { duration: '30s', target: 0 },
  ];
  if (!raw || typeof raw !== 'string') return fallback;

  const stages = raw
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const [duration, target] = item.split(':').map((part) => part.trim());
      const targetVus = Number(target);
      if (!duration || !Number.isFinite(targetVus)) return null;
      return { duration, target: targetVus };
    })
    .filter(Boolean);

  return stages.length > 0 ? stages : fallback;
}

function buildScenarios() {
  const scenarios = {
    read_api: {
      executor: 'ramping-vus',
      startVUs: Number(__ENV.START_VUS || '1'),
      stages: parseStages(__ENV.STAGES),
      gracefulRampDown: '30s',
      exec: 'readJourney',
      tags: { scenario: 'read_api' },
    },
  };

  if (INCLUDE_EXPORT) {
    scenarios.export_api = {
      executor: 'constant-arrival-rate',
      exec: 'exportJourney',
      rate: Number(__ENV.EXPORT_RATE || '1'),
      timeUnit: '1m',
      duration: __ENV.EXPORT_DURATION || '2m',
      preAllocatedVUs: Number(__ENV.EXPORT_PRE_VUS || '2'),
      maxVUs: Number(__ENV.EXPORT_MAX_VUS || '10'),
      tags: { scenario: 'export_api' },
    };
  }

  return scenarios;
}

export const options = {
  scenarios: buildScenarios(),
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<1200', 'p(99)<2500'],
    // login 只在 setup 中执行一次，阈值不宜过严
    'http_req_duration{endpoint:login}': ['p(95)<3000'],
    'http_req_duration{endpoint:admin_reports}': ['p(95)<800'],
    'http_req_duration{endpoint:doctor_reports}': ['p(95)<1000'],
    api_check_failure: ['rate<0.02'],
    endpoint_health_reqs: ['count>0'],
    endpoint_admin_reports_reqs: ['count>0'],
    endpoint_doctor_reports_reqs: ['count>0'],
  },
};

function buildQuery(params) {
  const pairs = Object.entries(params)
    .filter(([, value]) => value !== null && value !== undefined && String(value) !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  return pairs.join('&');
}

function jsonHeaders(token) {
  return {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  };
}

function login() {
  const res = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ username: USERNAME, password: PASSWORD }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { endpoint: 'login' },
    },
  );

  const ok = check(res, {
    'login status is 200': (r) => r.status === 200,
    'login has token': (r) => {
      try {
        const body = r.json();
        return !!body.access_token;
      } catch (_e) {
        return false;
      }
    },
  });

  if (!ok) {
    loginFailures.add(1);
    apiCheckFailure.add(1);
    throw new Error(`login failed, status=${res.status}, body=${res.body}`);
  }

  return res.json().access_token;
}

function checkedGet(path, token, endpointTag, params = {}) {
  const finalParams = {
    ...params,
    ...jsonHeaders(token),
    tags: { endpoint: endpointTag },
  };
  const res = http.get(`${BASE_URL}${path}`, finalParams);
  const ok = check(res, {
    [`${endpointTag} status is 200`]: (r) => r.status === 200,
  });
  apiCheckFailure.add(ok ? 0 : 1);
  return res;
}

export function setup() {
  const token = login();
  return { token };
}

export function readJourney(data) {
  const token = data.token;

  group('health', () => {
    endpointHealthReqs.add(1);
    const res = http.get(`${BASE_URL}/api/health`, { tags: { endpoint: 'health' } });
    const ok = check(res, {
      'health status is 200': (r) => r.status === 200,
      'health body ok=true': (r) => {
        try {
          return r.json().ok === true;
        } catch (_e) {
          return false;
        }
      },
    });
    apiCheckFailure.add(ok ? 0 : 1);
  });

  let firstReportId = null;

  group('admin_reports', () => {
    const query = buildQuery({
      page: '1',
      page_size: String(REPORT_PAGE_SIZE),
      q: REPORT_QUERY,
      status: REPORT_STATUS,
    });
    endpointAdminReportsReqs.add(1);
    const res = checkedGet(`/api/reports?${query}`, token, 'admin_reports');
    if (res.status !== 200) return;

    const ok = check(res, {
      'admin_reports has items[]': (r) => {
        try {
          const body = r.json();
          return Array.isArray(body.items);
        } catch (_e) {
          return false;
        }
      },
    });
    apiCheckFailure.add(ok ? 0 : 1);

    try {
      const body = res.json();
      if (Array.isArray(body.items) && body.items.length > 0) {
        firstReportId = body.items[0].id;
      }
    } catch (_e) {
      // ignore JSON parse errors already counted by checks
    }
  });

  if (firstReportId !== null) {
    group('admin_report_detail', () => {
      checkedGet(`/api/reports/${firstReportId}`, token, 'admin_report_detail');
    });
  }

  group('users_doctors', () => {
    checkedGet('/api/users?role=doctor', token, 'users_doctors');
  });

  group('doctor_reports', () => {
    endpointDoctorReportsReqs.add(1);
    checkedGet('/api/doctor/reports?tab=all&page=1&page_size=20', token, 'doctor_reports');
  });

  sleep(THINK_TIME);
}

export function exportJourney(data) {
  const token = data.token;
  const res = http.get(`${BASE_URL}/api/reports/export/all?export_mode=${encodeURIComponent(EXPORT_MODE)}`, {
    headers: { Authorization: `Bearer ${token}` },
    responseType: 'none',
    tags: { endpoint: 'export_all' },
    timeout: __ENV.EXPORT_TIMEOUT || '180s',
  });

  const ok = check(res, {
    'export_all status is 200': (r) => r.status === 200,
    'export_all has content-disposition': (r) => !!r.headers['Content-Disposition'],
  });
  apiCheckFailure.add(ok ? 0 : 1);

  sleep(Math.max(0.1, THINK_TIME));
}
