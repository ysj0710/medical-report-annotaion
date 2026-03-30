import http from 'k6/http';
import { check, group, sleep } from 'k6';
import exec from 'k6/execution';
import { Counter, Rate } from 'k6/metrics';

const BASE_URL = String(__ENV.BASE_URL || 'http://127.0.0.1:8088').replace(/\/+$/, '');

const TARGET_VUS = Number(__ENV.TARGET_VUS || '60');
const RAMP_UP = __ENV.RAMP_UP || '5m';
const STEADY = __ENV.STEADY || '20m';
const RAMP_DOWN = __ENV.RAMP_DOWN || '5m';
const THINK_TIME = Number(__ENV.THINK_TIME || '0.4');
const PAGE_SIZE = Number(__ENV.PAGE_SIZE || '20');
const DETAIL_SAMPLE_RATE = Number(__ENV.DETAIL_SAMPLE_RATE || '0.7');

const ENABLE_ADMIN_PROBE = String(__ENV.ENABLE_ADMIN_PROBE || 'true').toLowerCase() === 'true';
const ADMIN_VUS = Number(__ENV.ADMIN_VUS || '1');
const ADMIN_USERNAME = __ENV.ADMIN_USERNAME || 'admin';
const ADMIN_PASSWORD = __ENV.ADMIN_PASSWORD || 'admin123';

const ENABLE_DRAFT_WRITE = String(__ENV.ENABLE_DRAFT_WRITE || 'false').toLowerCase() === 'true';
const DRAFT_RATIO = Number(__ENV.DRAFT_RATIO || '0.15');

const DOCTOR_PASSWORD = __ENV.DOCTOR_PASSWORD || 'doctor123';
const DOCTOR_USERNAME = __ENV.DOCTOR_USERNAME || '';
const DOCTOR_CREDENTIALS_FILE = __ENV.DOCTOR_CREDENTIALS_FILE || '';
const DOCTOR_CREDENTIALS_JSON = __ENV.DOCTOR_CREDENTIALS_JSON || '';
const DOCTOR_USER_PREFIX = __ENV.DOCTOR_USER_PREFIX || '';
const DOCTOR_USER_START = Number(__ENV.DOCTOR_USER_START || '1');
const DOCTOR_USER_END = Number(__ENV.DOCTOR_USER_END || '0');
const DOCTOR_USER_PAD = Number(__ENV.DOCTOR_USER_PAD || '0');
const VALIDATE_CREDENTIALS = String(__ENV.VALIDATE_CREDENTIALS || 'true').toLowerCase() === 'true';
const REQUIRE_UNIQUE_USERS = String(__ENV.REQUIRE_UNIQUE_USERS || 'false').toLowerCase() === 'true';

const apiCheckFailure = new Rate('api_check_failure');
const loginFailures = new Counter('login_failures');
const endpointDoctorListReqs = new Counter('endpoint_doctor_list_reqs');
const endpointDoctorDetailReqs = new Counter('endpoint_doctor_detail_reqs');
const endpointDoctorDraftReqs = new Counter('endpoint_doctor_draft_reqs');

const vuSession = {
  token: '',
  username: '',
};

function openDoctorCredentialsFile(pathValue) {
  const requested = String(pathValue || '').trim();
  const candidates = [];
  const pushCandidate = (candidate) => {
    if (!candidate) return;
    if (!candidates.includes(candidate)) candidates.push(candidate);
  };

  pushCandidate(requested);
  if (!requested.startsWith('/')) {
    if (requested.startsWith('./')) {
      pushCandidate(requested.slice(2));
    }
    pushCandidate(`../../${requested}`);
    const strippedScriptsPrefix = requested.replace(/^\.?\/?scripts\/k6\//, '');
    if (strippedScriptsPrefix !== requested) {
      pushCandidate(strippedScriptsPrefix);
    }
  }

  let lastError = '';
  for (let i = 0; i < candidates.length; i += 1) {
    const candidate = candidates[i];
    try {
      const raw = open(candidate);
      return { raw, loadedFrom: candidate };
    } catch (e) {
      lastError = String(e);
    }
  }

  throw new Error(
    `failed to read DOCTOR_CREDENTIALS_FILE=${requested}, tried=${candidates.join(', ')}, lastError=${lastError}`,
  );
}

function buildDoctorCredentials() {
  const configuredModes = [];
  if (DOCTOR_CREDENTIALS_FILE) configuredModes.push('file');
  if (DOCTOR_CREDENTIALS_JSON) configuredModes.push('json');
  if (DOCTOR_USERNAME) configuredModes.push('single');
  if (DOCTOR_USER_PREFIX) configuredModes.push('prefix');

  let selectedMode = 'none';
  let detail = '';
  if (DOCTOR_CREDENTIALS_FILE) {
    selectedMode = 'file';
    let raw = '';
    let loadedFrom = '';
    try {
      const opened = openDoctorCredentialsFile(DOCTOR_CREDENTIALS_FILE);
      raw = opened.raw;
      loadedFrom = opened.loadedFrom;
      detail = loadedFrom;
    } catch (e) {
      throw new Error(String(e));
    }

    try {
      const parsed = JSON.parse(String(raw || '').trim());
      if (!Array.isArray(parsed)) {
        throw new Error('credentials file JSON is not an array');
      }
      const normalized = parsed
        .map((item) => ({
          username: String(item?.username || '').trim(),
          password: String(item?.password || '').trim(),
        }))
        .filter((item) => item.username && item.password);
      if (normalized.length === 0) {
        throw new Error('credentials file has no valid {username,password} items');
      }
      return { creds: normalized, selectedMode, configuredModes, detail };
    } catch (e) {
      throw new Error(`failed to parse DOCTOR_CREDENTIALS_FILE=${DOCTOR_CREDENTIALS_FILE} (resolved=${loadedFrom}): ${String(e)}`);
    }
  }

  if (DOCTOR_CREDENTIALS_JSON) {
    selectedMode = 'json';
    try {
      const parsed = JSON.parse(DOCTOR_CREDENTIALS_JSON);
      if (!Array.isArray(parsed)) {
        throw new Error('DOCTOR_CREDENTIALS_JSON is not an array');
      }
      const normalized = parsed
        .map((item) => ({
          username: String(item?.username || '').trim(),
          password: String(item?.password || '').trim(),
        }))
        .filter((item) => item.username && item.password);
      if (normalized.length === 0) {
        throw new Error('DOCTOR_CREDENTIALS_JSON has no valid {username,password} items');
      }
      return { creds: normalized, selectedMode, configuredModes, detail };
    } catch (_e) {
      throw new Error(`invalid DOCTOR_CREDENTIALS_JSON: ${String(_e)}`);
    }
  }

  if (DOCTOR_USERNAME) {
    selectedMode = 'single';
    detail = DOCTOR_USERNAME;
    return { creds: [{ username: DOCTOR_USERNAME, password: DOCTOR_PASSWORD }], selectedMode, configuredModes, detail };
  }

  if (DOCTOR_USER_PREFIX) {
    selectedMode = 'prefix';
    if (!Number.isFinite(DOCTOR_USER_START) || !Number.isFinite(DOCTOR_USER_END) || DOCTOR_USER_END < DOCTOR_USER_START) {
      throw new Error(`invalid doctor prefix range: start=${DOCTOR_USER_START}, end=${DOCTOR_USER_END}`);
    }
    detail = `${DOCTOR_USER_PREFIX}[${DOCTOR_USER_START}-${DOCTOR_USER_END}]`;
    const creds = [];
    for (let i = DOCTOR_USER_START; i <= DOCTOR_USER_END; i += 1) {
      const idx = DOCTOR_USER_PAD > 0 ? String(i).padStart(DOCTOR_USER_PAD, '0') : String(i);
      creds.push({ username: `${DOCTOR_USER_PREFIX}${idx}`, password: DOCTOR_PASSWORD });
    }
    return { creds, selectedMode, configuredModes, detail };
  }

  return { creds: [], selectedMode, configuredModes, detail };
}

const doctorCredConfig = buildDoctorCredentials();
const DOCTOR_CREDS = doctorCredConfig.creds;
const DOCTOR_CRED_SELECTED_MODE = doctorCredConfig.selectedMode;
const DOCTOR_CRED_CONFIGURED_MODES = doctorCredConfig.configuredModes;
const DOCTOR_CRED_DETAIL = doctorCredConfig.detail;

function buildScenarios() {
  const scenarios = {
    doctor_concurrency: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: RAMP_UP, target: TARGET_VUS },
        { duration: STEADY, target: TARGET_VUS },
        { duration: RAMP_DOWN, target: 0 },
      ],
      gracefulRampDown: '1m',
      exec: 'doctorJourney',
      tags: { scenario: 'doctor_concurrency' },
    },
  };

  if (ENABLE_ADMIN_PROBE) {
    scenarios.admin_probe = {
      executor: 'constant-vus',
      vus: ADMIN_VUS,
      duration: `${Math.ceil((parseDurationSeconds(RAMP_UP) + parseDurationSeconds(STEADY) + parseDurationSeconds(RAMP_DOWN)))}s`,
      exec: 'adminProbeJourney',
      tags: { scenario: 'admin_probe' },
    };
  }

  return scenarios;
}

function parseDurationSeconds(value) {
  const raw = String(value || '').trim();
  const matched = raw.match(/^(\d+)(ms|s|m|h)$/i);
  if (!matched) return 0;
  const n = Number(matched[1]);
  const unit = matched[2].toLowerCase();
  if (unit === 'ms') return n / 1000;
  if (unit === 's') return n;
  if (unit === 'm') return n * 60;
  if (unit === 'h') return n * 3600;
  return 0;
}

function requiredDoctorCredentials(creds, targetVus) {
  if (!Array.isArray(creds) || creds.length === 0) return [];
  if (REQUIRE_UNIQUE_USERS) {
    const need = Math.min(targetVus, creds.length);
    return creds.slice(0, need);
  }
  // 复用账号模式下，至少检查全部提供账号，避免错配跑到一半才暴露问题。
  return creds;
}

export const options = {
  scenarios: buildScenarios(),
  thresholds: {
    http_req_failed: ['rate<0.01'],
    api_check_failure: ['rate<0.02'],
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    'http_req_duration{endpoint:doctor_list_unannotated}': ['p(95)<1000'],
    'http_req_duration{endpoint:doctor_list_all}': ['p(95)<1200'],
    'http_req_duration{endpoint:doctor_detail}': ['p(95)<1200'],
    'http_req_duration{endpoint:doctor_save_draft}': ['p(95)<1500'],
    endpoint_doctor_list_reqs: ['count>0'],
    endpoint_doctor_detail_reqs: ['count>0'],
  },
};

function login(username, password, tag = 'login') {
  const res = http.post(
    `${BASE_URL}/api/auth/login`,
    JSON.stringify({ username, password }),
    {
      headers: { 'Content-Type': 'application/json' },
      tags: { endpoint: tag },
      timeout: '30s',
    },
  );

  const ok = check(res, {
    [`${tag} status is 200`]: (r) => r.status === 200,
    [`${tag} has token`]: (r) => {
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
    return '';
  }

  try {
    return res.json().access_token || '';
  } catch (_e) {
    apiCheckFailure.add(1);
    return '';
  }
}

function authHeaders(token) {
  return {
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
}

function checkedGet(path, token, endpointTag) {
  const res = http.get(`${BASE_URL}${path}`, {
    ...authHeaders(token),
    tags: { endpoint: endpointTag },
    timeout: '30s',
  });
  const ok = check(res, {
    [`${endpointTag} status is 200`]: (r) => r.status === 200,
  });
  apiCheckFailure.add(ok ? 0 : 1);
  return res;
}

function checkedPost(path, token, payload, endpointTag) {
  const res = http.post(`${BASE_URL}${path}`, JSON.stringify(payload), {
    ...authHeaders(token),
    tags: { endpoint: endpointTag },
    timeout: '30s',
  });
  const ok = check(res, {
    [`${endpointTag} status is 200`]: (r) => r.status === 200,
  });
  apiCheckFailure.add(ok ? 0 : 1);
  return res;
}

function credentialForCurrentVu() {
  if (!DOCTOR_CREDS.length) return null;
  const vuId = exec.vu.idInTest || 1;
  return DOCTOR_CREDS[(vuId - 1) % DOCTOR_CREDS.length];
}

function ensureDoctorSession() {
  if (vuSession.token) return vuSession.token;

  const cred = credentialForCurrentVu();
  if (!cred) {
    throw new Error('No doctor credentials found. Set DOCTOR_CREDENTIALS_FILE / DOCTOR_CREDENTIALS_JSON / DOCTOR_USERNAME+DOCTOR_PASSWORD / DOCTOR_USER_PREFIX range.');
  }

  const token = login(cred.username, cred.password, 'doctor_login');
  if (!token) {
    throw new Error(`doctor login failed for user=${cred.username}`);
  }

  vuSession.token = token;
  vuSession.username = cred.username;
  return vuSession.token;
}

function pickReportId(unannotatedResponse, allResponse) {
  let fromUnannotated = [];
  let fromAll = [];

  try {
    fromUnannotated = unannotatedResponse.status === 200 ? (unannotatedResponse.json().items || []) : [];
  } catch (_e) {
    fromUnannotated = [];
  }
  try {
    fromAll = allResponse.status === 200 ? (allResponse.json().items || []) : [];
  } catch (_e) {
    fromAll = [];
  }

  const source = fromUnannotated.length > 0 ? fromUnannotated : fromAll;
  if (!source.length) return null;

  const idx = Math.floor(Math.random() * source.length);
  return source[idx]?.id ?? null;
}

function maybeDraftSave(token, reportDetailResponse) {
  if (!ENABLE_DRAFT_WRITE) return;
  if (Math.random() > DRAFT_RATIO) return;

  let report = null;
  try {
    report = reportDetailResponse.json();
  } catch (_e) {
    return;
  }

  const status = String(report?.status || '');
  const editable = ['ASSIGNED', 'IN_PROGRESS', 'REVIEW_ASSIGNED', 'REVIEW_IN_PROGRESS'].includes(status);
  if (!editable || !report?.id) return;

  endpointDoctorDraftReqs.add(1);
  checkedPost(
    `/api/doctor/reports/${report.id}/annotation/draft`,
    token,
    {
      data: {
        no_error: true,
        error_items: [],
        note: 'k6 draft save for concurrency test',
      },
    },
    'doctor_save_draft',
  );
}

export function setup() {
  const health = http.get(`${BASE_URL}/api/health`, { tags: { endpoint: 'health' } });
  const healthOk = check(health, {
    'health status is 200': (r) => r.status === 200,
  });
  if (!healthOk) {
    throw new Error(`health check failed: status=${health.status}, body=${health.body}`);
  }

  const modeList = DOCTOR_CRED_CONFIGURED_MODES.length > 0 ? DOCTOR_CRED_CONFIGURED_MODES.join(',') : 'none';
  const detail = DOCTOR_CRED_DETAIL ? `, detail=${DOCTOR_CRED_DETAIL}` : '';
  console.log(
    `doctor credentials mode selected=${DOCTOR_CRED_SELECTED_MODE}, configured=${modeList}, total=${DOCTOR_CREDS.length}, targetVUs=${TARGET_VUS}, unique=${REQUIRE_UNIQUE_USERS}${detail}`,
  );
  if (DOCTOR_CRED_CONFIGURED_MODES.length > 1) {
    console.log('multiple doctor credential modes detected; precedence is file > json > single > prefix');
  }

  if (ENABLE_ADMIN_PROBE) {
    const adminToken = login(ADMIN_USERNAME, ADMIN_PASSWORD, 'admin_login');
    if (!adminToken) {
      throw new Error('admin login failed in setup');
    }
    if (VALIDATE_CREDENTIALS) {
      const needed = requiredDoctorCredentials(DOCTOR_CREDS, TARGET_VUS);
      if (needed.length === 0) {
        throw new Error('no doctor credentials configured');
      }
      if (REQUIRE_UNIQUE_USERS && DOCTOR_CREDS.length < TARGET_VUS) {
        throw new Error(`doctor credentials not enough for unique users: have=${DOCTOR_CREDS.length}, need=${TARGET_VUS}`);
      }

      const failedUsers = [];
      for (let i = 0; i < needed.length; i += 1) {
        const c = needed[i];
        const t = login(c.username, c.password, 'doctor_login_validate');
        if (!t) failedUsers.push(c.username);
      }
      if (failedUsers.length > 0) {
        const preview = failedUsers.slice(0, 10).join(', ');
        const suffix = failedUsers.length > 10 ? ' ...' : '';
        throw new Error(`doctor credential validation failed (${failedUsers.length}/${needed.length}): ${preview}${suffix}`);
      }
      console.log(`doctor credential validation passed: ${needed.length} users`);
    }
    return { adminToken };
  }

  if (VALIDATE_CREDENTIALS) {
    const needed = requiredDoctorCredentials(DOCTOR_CREDS, TARGET_VUS);
    if (needed.length === 0) {
      throw new Error('no doctor credentials configured');
    }
    if (REQUIRE_UNIQUE_USERS && DOCTOR_CREDS.length < TARGET_VUS) {
      throw new Error(`doctor credentials not enough for unique users: have=${DOCTOR_CREDS.length}, need=${TARGET_VUS}`);
    }
    const failedUsers = [];
    for (let i = 0; i < needed.length; i += 1) {
      const c = needed[i];
      const t = login(c.username, c.password, 'doctor_login_validate');
      if (!t) failedUsers.push(c.username);
    }
    if (failedUsers.length > 0) {
      const preview = failedUsers.slice(0, 10).join(', ');
      const suffix = failedUsers.length > 10 ? ' ...' : '';
      throw new Error(`doctor credential validation failed (${failedUsers.length}/${needed.length}): ${preview}${suffix}`);
    }
    console.log(`doctor credential validation passed: ${needed.length} users`);
  }

  return {};
}

export function doctorJourney() {
  const token = ensureDoctorSession();

  let resUnannotated;
  let resAll;

  group('doctor_list', () => {
    endpointDoctorListReqs.add(1);
    resUnannotated = checkedGet(`/api/doctor/reports?tab=unannotated&page=1&page_size=${PAGE_SIZE}`, token, 'doctor_list_unannotated');
    resAll = checkedGet(`/api/doctor/reports?tab=all&page=1&page_size=${PAGE_SIZE}`, token, 'doctor_list_all');
  });

  if (Math.random() <= DETAIL_SAMPLE_RATE) {
    const reportId = pickReportId(resUnannotated, resAll);
    if (reportId !== null && reportId !== undefined) {
      group('doctor_detail', () => {
        endpointDoctorDetailReqs.add(1);
        const detail = checkedGet(`/api/doctor/reports/${reportId}`, token, 'doctor_detail');
        maybeDraftSave(token, detail);
      });
    }
  }

  sleep(THINK_TIME);
}

export function adminProbeJourney(data) {
  const token = data.adminToken;
  checkedGet('/api/reports?page=1&page_size=20', token, 'admin_reports_probe');
  checkedGet('/api/users?role=doctor', token, 'admin_users_probe');
  sleep(Math.max(0.5, THINK_TIME));
}
