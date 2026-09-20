import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  FALLBACK_PUBLIC_CONFIG,
  ALLOWED_SERVICE_STAGES,
  parsePublicConfig,
  isFreeBetaActive,
  fetchPublicConfig,
} from '../publicConfig.ts';

describe('publicConfig - parsePublicConfig 엄격한 런타임 타입 검증', () => {
  const validPayload = {
    service_stage: 'free_beta',
    generation_enabled: true,
    purchase_enabled: false,
    policy_documents_draft: false,
    free_beta_ready: true,
    consultation_credit_cost: 10,
    welcome_credits: 50,
    legal_documents_version: '2026-09-12',
  };

  test('완전하고 정상적인 boolean/number payload는 정상 파싱되며 isFreeBetaActive=true', () => {
    const config = parsePublicConfig(validPayload);
    assert.equal(config.service_stage, 'free_beta');
    assert.equal(config.generation_enabled, true);
    assert.equal(config.purchase_enabled, false);
    assert.equal(config.policy_documents_draft, false);
    assert.equal(config.free_beta_ready, true);
    assert.equal(config.legal_documents_version, '2026-09-12');
    assert.equal(config.consultation_credit_cost, 10);
    assert.equal(config.welcome_credits, 50);
    assert.equal(isFreeBetaActive(config), true);
  });

  test('generation_enabled="false" (문자열)은 truthy 변환되지 않고 fail-safe FALLBACK 반환 (활성 false)', () => {
    const payload = { ...validPayload, generation_enabled: 'false' };
    const config = parsePublicConfig(payload);
    assert.deepEqual(config, FALLBACK_PUBLIC_CONFIG);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('generation_enabled="true" (문자열)도 계약 위반으로 fail-safe FALLBACK 반환', () => {
    const payload = { ...validPayload, generation_enabled: 'true' };
    const config = parsePublicConfig(payload);
    assert.deepEqual(config, FALLBACK_PUBLIC_CONFIG);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('purchase_enabled="false" 및 "true" (문자열)은 fail-safe FALLBACK 반환', () => {
    assert.deepEqual(parsePublicConfig({ ...validPayload, purchase_enabled: 'false' }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, purchase_enabled: 'true' }), FALLBACK_PUBLIC_CONFIG);
  });

  test('policy_documents_draft의 문자열/숫자/null/객체 변형은 fail-safe FALLBACK 반환', () => {
    assert.deepEqual(parsePublicConfig({ ...validPayload, policy_documents_draft: 'false' }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, policy_documents_draft: 0 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, policy_documents_draft: null }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, policy_documents_draft: {} }), FALLBACK_PUBLIC_CONFIG);
  });

  test('free_beta_ready의 문자열/숫자/null/객체 변형은 fail-safe FALLBACK 반환', () => {
    assert.deepEqual(parsePublicConfig({ ...validPayload, free_beta_ready: 'true' }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, free_beta_ready: 1 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, free_beta_ready: null }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, free_beta_ready: ['true'] }), FALLBACK_PUBLIC_CONFIG);
  });

  test('free_beta_ready가 undefined/누락된 경우 free_beta_ready=false로 파싱되어 활성 false', () => {
    const withoutReady = { ...validPayload };
    delete withoutReady.free_beta_ready;
    const config = parsePublicConfig(withoutReady);
    assert.equal(config.service_stage, 'free_beta');
    assert.equal(config.generation_enabled, true);
    assert.equal(config.free_beta_ready, false);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('legal_documents_version의 non-string 변형(숫자, boolean, null, 객체)은 fail-safe FALLBACK 반환', () => {
    assert.deepEqual(parsePublicConfig({ ...validPayload, legal_documents_version: 123 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, legal_documents_version: true }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, legal_documents_version: null }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, legal_documents_version: {} }), FALLBACK_PUBLIC_CONFIG);
  });

  test('legal_documents_version이 생략되거나 빈 문자열인 경우도 정상 파싱', () => {
    const withoutVer = { ...validPayload };
    delete withoutVer.legal_documents_version;
    assert.equal(parsePublicConfig(withoutVer).legal_documents_version, '');
    assert.equal(parsePublicConfig({ ...validPayload, legal_documents_version: '' }).legal_documents_version, '');
  });

  test('service_stage 미지원 값은 fail-safe FALLBACK 반환', () => {
    assert.deepEqual(parsePublicConfig({ ...validPayload, service_stage: 'unknown_stage' }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, service_stage: 'beta' }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, service_stage: '' }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, service_stage: 123 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, service_stage: null }), FALLBACK_PUBLIC_CONFIG);
  });

  test('service_stage allowlist 검증: free_beta, preparing, commercial 만 허용', () => {
    assert.deepEqual(ALLOWED_SERVICE_STAGES, ['free_beta', 'preparing', 'commercial']);
    const preparingConfig = parsePublicConfig({ ...validPayload, service_stage: 'preparing', policy_documents_draft: true });
    assert.equal(preparingConfig.service_stage, 'preparing');
    const commercialConfig = parsePublicConfig({ ...validPayload, service_stage: 'commercial', purchase_enabled: true });
    assert.equal(commercialConfig.service_stage, 'commercial');
  });

  test('credit 필드: NaN, Infinity, 음수, 소수, 문자열은 fail-safe FALLBACK 반환', () => {
    assert.deepEqual(parsePublicConfig({ ...validPayload, consultation_credit_cost: NaN }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, consultation_credit_cost: Infinity }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, consultation_credit_cost: -1 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, consultation_credit_cost: 10.5 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, consultation_credit_cost: '10' }), FALLBACK_PUBLIC_CONFIG);

    assert.deepEqual(parsePublicConfig({ ...validPayload, welcome_credits: NaN }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, welcome_credits: -50 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, welcome_credits: 50.1 }), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig({ ...validPayload, welcome_credits: '50' }), FALLBACK_PUBLIC_CONFIG);
  });

  test('non-object 입력(null, undefined, 배열, 원시값)은 fail-safe FALLBACK 반환', () => {
    assert.deepEqual(parsePublicConfig(null), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig(undefined), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig([]), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig('invalid string'), FALLBACK_PUBLIC_CONFIG);
    assert.deepEqual(parsePublicConfig(12345), FALLBACK_PUBLIC_CONFIG);
  });
});

describe('publicConfig - isFreeBetaActive 4대 조건 검증', () => {
  const activeValidConfig = {
    service_stage: 'free_beta',
    generation_enabled: true,
    policy_documents_draft: false,
    free_beta_ready: true,
    purchase_enabled: false,
    consultation_credit_cost: 10,
    welcome_credits: 50,
  };

  test('4대 조건(service_stage=free_beta, generation_enabled=true, policy_documents_draft=false, free_beta_ready=true)을 모두 충족하면 true', () => {
    assert.equal(isFreeBetaActive(activeValidConfig), true);
  });

  test('free_beta_ready가 false이면 fail-safe로 false', () => {
    const config = { ...activeValidConfig, free_beta_ready: false };
    assert.equal(isFreeBetaActive(config), false);
  });

  test('free_beta_ready가 undefined/누락이면 fail-safe로 false', () => {
    const config = { ...activeValidConfig, free_beta_ready: undefined };
    assert.equal(isFreeBetaActive(config), false);
  });

  test('policy_documents_draft가 true이면 false', () => {
    const config = { ...activeValidConfig, policy_documents_draft: true };
    assert.equal(isFreeBetaActive(config), false);
  });

  test('generation_enabled가 false이면 false', () => {
    const config = { ...activeValidConfig, generation_enabled: false };
    assert.equal(isFreeBetaActive(config), false);
  });

  test('service_stage가 free_beta가 아니면 false (preparing, commercial 등)', () => {
    assert.equal(
      isFreeBetaActive({ ...activeValidConfig, service_stage: 'preparing' }),
      false
    );
    assert.equal(
      isFreeBetaActive({ ...activeValidConfig, service_stage: 'commercial' }),
      false
    );
  });

  test('null, undefined, 빈 객체에 대해 fail-safe로 false', () => {
    assert.equal(isFreeBetaActive(null), false);
    assert.equal(isFreeBetaActive(undefined), false);
    assert.equal(isFreeBetaActive({}), false);
  });

  test('FALLBACK_PUBLIC_CONFIG는 준비 중이며 isFreeBetaActive가 false', () => {
    assert.equal(FALLBACK_PUBLIC_CONFIG.service_stage, 'preparing');
    assert.equal(FALLBACK_PUBLIC_CONFIG.generation_enabled, false);
    assert.equal(FALLBACK_PUBLIC_CONFIG.policy_documents_draft, true);
    assert.equal(FALLBACK_PUBLIC_CONFIG.free_beta_ready, false);
    assert.equal(isFreeBetaActive(FALLBACK_PUBLIC_CONFIG), false);
  });
});

describe('publicConfig - fetchPublicConfig 네트워크 및 런타임 fail-safe 처리', () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test('서버 404 Not Found 시 FALLBACK_PUBLIC_CONFIG 반환 및 비활성 판정', async () => {
    globalThis.fetch = async () =>
      new Response('Not Found', {
        status: 404,
        statusText: 'Not Found',
      });

    const config = await fetchPublicConfig(1000);
    assert.deepEqual(config, FALLBACK_PUBLIC_CONFIG);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('서버 500 Internal Error 시 FALLBACK_PUBLIC_CONFIG 반환', async () => {
    globalThis.fetch = async () =>
      new Response('Server Error', {
        status: 500,
        statusText: 'Internal Server Error',
      });

    const config = await fetchPublicConfig(1000);
    assert.deepEqual(config, FALLBACK_PUBLIC_CONFIG);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('유효하지 않은 JSON (invalid JSON) 응답 시 FALLBACK_PUBLIC_CONFIG 반환', async () => {
    globalThis.fetch = async () =>
      new Response('{ invalid json string ...', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });

    const config = await fetchPublicConfig(1000);
    assert.deepEqual(config, FALLBACK_PUBLIC_CONFIG);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('문자열 boolean이 포함된 비정상 응답 시 fail-safe FALLBACK 반환', async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          service_stage: 'free_beta',
          generation_enabled: 'false', // 문자열 "false"
          policy_documents_draft: false,
          free_beta_ready: true,
          purchase_enabled: false,
          consultation_credit_cost: 10,
          welcome_credits: 50,
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );

    const config = await fetchPublicConfig(1000);
    assert.deepEqual(config, FALLBACK_PUBLIC_CONFIG);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('타임아웃 발생 시 FALLBACK_PUBLIC_CONFIG 반환', async () => {
    globalThis.fetch = async (_url, options) => {
      return new Promise((_, reject) => {
        const signal = options?.signal;
        if (signal) {
          signal.addEventListener('abort', () => {
            const err = new Error('The operation was aborted');
            err.name = 'AbortError';
            reject(err);
          });
        }
      });
    };

    const startTime = Date.now();
    const config = await fetchPublicConfig(50);
    const elapsed = Date.now() - startTime;

    assert.ok(elapsed < 1000, '타임아웃이 1초 내에 정상 발동해야 함');
    assert.deepEqual(config, FALLBACK_PUBLIC_CONFIG);
    assert.equal(isFreeBetaActive(config), false);
  });

  test('모든 4대 조건이 갖춰진 정상 boolean/number 응답만 활성(true)', async () => {
    globalThis.fetch = async () =>
      new Response(
        JSON.stringify({
          service_stage: 'free_beta',
          generation_enabled: true,
          policy_documents_draft: false,
          free_beta_ready: true,
          purchase_enabled: false,
          consultation_credit_cost: 10,
          welcome_credits: 50,
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      );

    const config = await fetchPublicConfig(1000);
    assert.equal(config.service_stage, 'free_beta');
    assert.equal(config.generation_enabled, true);
    assert.equal(config.policy_documents_draft, false);
    assert.equal(config.free_beta_ready, true);
    assert.equal(isFreeBetaActive(config), true);
  });
});
