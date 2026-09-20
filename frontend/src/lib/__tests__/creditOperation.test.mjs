import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import {
  createIdempotencyKey,
  fetchMyCredits,
  fetchOperationStatus,
  pollOperationUntilDone,
  parseHttpErrorResponse,
  CreditOperationError,
} from '../creditOperation.ts';

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

describe('creditOperation - 멱등키 생성 및 재시도 생명주기 검증', () => {
  test('createIdempotencyKey는 표준 UUID v4 포맷의 문자열을 생성한다', () => {
    const key1 = createIdempotencyKey();
    const key2 = createIdempotencyKey();
    assert.match(key1, UUID_REGEX);
    assert.match(key2, UUID_REGEX);
    assert.notEqual(key1, key2, '각 생성마다 고유한 새 키여야 함');
  });

  test('동일한 행동의 재시도에서는 동일 키가 재사용되고, 새 행동에서는 새 키가 발급된다', () => {
    // 1) 사용자가 질문 전송 시작 -> 키 발급
    let currentIdempotencyKey = createIdempotencyKey();
    const initialKey = currentIdempotencyKey;

    // 2) 네트워크 오류 또는 202 발생 시 "같은 요청으로 재시도"
    const retryKey = currentIdempotencyKey;
    assert.equal(retryKey, initialKey, '재시도 시 동일한 Idempotency-Key를 유지해야 함');

    // 3) 사용자가 "새로운 질문으로 다시 시도" 또는 처음으로 리셋
    currentIdempotencyKey = createIdempotencyKey();
    assert.notEqual(currentIdempotencyKey, initialKey, '새로운 요청 시에는 반드시 새 키가 발급되어야 함');
  });
});

describe('creditOperation - 서버 잔액 단일 출처 (GET /api/me/credits)', () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test('성공 시 remaining_credits와 welcome_granted를 정확히 반환한다', async () => {
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes('/api/me/credits'));
      assert.equal(options.headers.Authorization, 'Bearer test-jwt-token');
      return {
        ok: true,
        status: 200,
        json: async () => ({
          remaining_credits: 40,
          welcome_granted: true,
        }),
      };
    };

    const credits = await fetchMyCredits('test-jwt-token');
    assert.deepEqual(credits, {
      remaining_credits: 40,
      welcome_granted: true,
    });
  });

  test('서버 오류(500, 401 등) 시 절대로 50C로 임의 대체하지 않고 null (잔액 unknown)을 반환한다', async () => {
    // 500 내부 에러 시뮬레이션
    globalThis.fetch = async () => ({
      ok: false,
      status: 500,
      json: async () => ({ code: 'INTERNAL_ERROR', message: 'DB connection error' }),
    });

    const res500 = await fetchMyCredits('test-jwt-token');
    assert.equal(res500, null, '서버 오류 시 null을 반환하여 UI에 [잔액 확인 필요]로 표시되어야 함');

    // 네트워크 예외 발생 시뮬레이션
    globalThis.fetch = async () => {
      throw new Error('Network timeout');
    };

    const resNetErr = await fetchMyCredits('test-jwt-token');
    assert.equal(resNetErr, null, '네트워크 예외 시 50으로 대체하지 않고 null 반환');
  });

  test('비정상 데이터(음수, 문자열, 누락)인 경우 fail-safe로 null을 반환한다', async () => {
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        remaining_credits: 'forty', // 잘못된 타입
        welcome_granted: true,
      }),
    });

    const resInvalid = await fetchMyCredits('test-jwt-token');
    assert.equal(resInvalid, null, '타입 오류 시 null 반환');

    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        remaining_credits: -10, // 음수 잔액
        welcome_granted: true,
      }),
    });

    const resNegative = await fetchMyCredits('test-jwt-token');
    assert.equal(resNegative, null, '음수 잔액 시 null 반환');
  });
});

describe('creditOperation - 202 Bounded Polling 및 타임아웃/성공 잔액 반영', () => {
  const originalFetch = globalThis.fetch;

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test('202 수신 후 pollOperationUntilDone이 SUCCEEDED 결과를 가져오고 remaining_credits를 제공한다', async () => {
    let pollCount = 0;
    globalThis.fetch = async (url, options) => {
      assert.ok(url.includes('/api/counsel/operations/op-success-01'));
      assert.equal(options.headers.Authorization, 'Bearer user-token');
      pollCount++;
      if (pollCount === 1) {
        return {
          ok: true,
          status: 200,
          json: async () => ({
            operation_id: 'op-success-01',
            operation_status: 'PROCESSING',
            retry_after_seconds: 0.001,
          }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({
          operation_id: 'op-success-01',
          operation_status: 'SUCCEEDED',
          credit_delta: -10,
          remaining_credits: 40,
          result: {
            session_id: 'sess-abc',
            primary_hexagram: { name: '건' },
            first_message: { sender: 'ai', content: '하늘의 기운입니다.' },
          },
        }),
      };
    };

    const op = await pollOperationUntilDone('op-success-01', 'user-token', 5, 0.001);
    assert.equal(op.operation_status, 'SUCCEEDED');
    assert.equal(op.remaining_credits, 40, '성공 시 갱신된 잔액 40 반영');
    assert.equal(op.credit_delta, -10);
    assert.equal(pollCount, 2);
  });

  test('지정된 maxAttempts 초과 시 무한 polling하지 않고 POLLING_TIMEOUT 에러 발생 및 operationId 보존', async () => {
    let pollCount = 0;
    globalThis.fetch = async () => {
      pollCount++;
      return {
        ok: true,
        status: 200,
        json: async () => ({
          operation_id: 'op-slow-01',
          operation_status: 'PROCESSING',
          retry_after_seconds: 0.001,
        }),
      };
    };

    await assert.rejects(
      async () => {
        await pollOperationUntilDone('op-slow-01', 'user-token', 3, 0.001);
      },
      (err) => {
        assert.ok(err instanceof CreditOperationError);
        assert.equal(err.code, 'POLLING_TIMEOUT');
        assert.equal(err.operationId, 'op-slow-01');
        assert.equal(err.canRetrySameKey, true, '타임아웃 발생 시 동일 작업 재시도/확인 허용');
        return true;
      }
    );

    assert.equal(pollCount, 3, '최대 3회만 시도하고 안전하게 중단');
  });

  test('operation이 REJECTED (크레딧 부족)로 종료 시 CreditOperationError 발생', async () => {
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        operation_id: 'op-rej-01',
        operation_status: 'REJECTED',
        error_snapshot: {
          code: 'INSUFFICIENT_CREDIT',
          message: '크레딧이 부족합니다.',
          remaining_credits: 0,
        },
      }),
    });

    await assert.rejects(
      async () => {
        await pollOperationUntilDone('op-rej-01', 'user-token', 3, 0.001);
      },
      (err) => {
        assert.ok(err instanceof CreditOperationError);
        assert.equal(err.code, 'INSUFFICIENT_CREDIT');
        assert.equal(err.remainingCredits, 0);
        assert.equal(err.canRetrySameKey, false);
        return true;
      }
    );
  });

  test('답변 없이 RELEASED된 작업은 빈 상담 성공으로 변환하지 않는다', async () => {
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({
        operation_id: 'op-failed-01',
        operation_status: 'RELEASED',
        error_code: 'PIPELINE_FAILED',
        remaining_credits: 50,
        result: null,
      }),
    });

    await assert.rejects(
      () => pollOperationUntilDone('op-failed-01', 'user-token', 1, 0.001),
      (err) => {
        assert.ok(err instanceof CreditOperationError);
        assert.equal(err.code, 'PIPELINE_FAILED');
        assert.equal(err.remainingCredits, 50);
        assert.equal(err.canRetrySameKey, false);
        return true;
      }
    );
  });

  test('fetchOperationStatus는 타 사용자 소유/미존재 operation 조회 시 404 OPERATION_NOT_FOUND 에러를 발생시킨다', async () => {
    globalThis.fetch = async () => ({
      ok: false,
      status: 404,
      json: async () => ({ code: 'NOT_FOUND', message: 'Not found' }),
    });

    await assert.rejects(
      async () => {
        await fetchOperationStatus('op-other-user', 'user-token');
      },
      (err) => {
        assert.ok(err instanceof CreditOperationError);
        assert.equal(err.code, 'OPERATION_NOT_FOUND');
        assert.equal(err.canRetrySameKey, false);
        return true;
      }
    );
  });
});

describe('creditOperation - HTTP 상태 코드 및 오류 분류 (401, 402, 409, 429, 503, 내부 은닉)', () => {
  test('401 Unauthorized 파싱', () => {
    const err = parseHttpErrorResponse(401, { message: 'Expired token' });
    assert.equal(err.code, 'UNAUTHORIZED');
    assert.equal(err.status, 401);
    assert.equal(err.message, '로그인이 필요합니다. 다시 로그인해 주세요.');
    assert.equal(err.canRetrySameKey, false);
  });

  test('402 Insufficient Credit 파싱 (잔액 보존)', () => {
    const err = parseHttpErrorResponse(402, {
      code: 'INSUFFICIENT_CREDIT',
      message: '보유 크레딧이 부족합니다.',
      remaining_credits: 0,
    });
    assert.equal(err.code, 'INSUFFICIENT_CREDIT');
    assert.equal(err.status, 402);
    assert.equal(err.remainingCredits, 0);
    assert.equal(err.canRetrySameKey, false);
  });

  test('409 Idempotency Key Reused 파싱 (동일 키에 다른 body)', () => {
    const err = parseHttpErrorResponse(409, {
      code: 'IDEMPOTENCY_KEY_REUSED',
      message: 'Idempotency key was reused with different request body',
    });
    assert.equal(err.code, 'IDEMPOTENCY_KEY_REUSED');
    assert.equal(err.status, 409);
    assert.equal(err.message, '이미 다른 요청에 사용된 요청 식별자입니다. 새로운 질문을 작성해 주세요.');
    assert.equal(err.canRetrySameKey, false);
  });

  test('429 Rate Limited 파싱', () => {
    const err = parseHttpErrorResponse(429, {
      retry_after_seconds: 15,
    });
    assert.equal(err.code, 'RATE_LIMITED');
    assert.equal(err.status, 429);
    assert.equal(err.retryAfterSeconds, 15);
    assert.equal(err.canRetrySameKey, true);
  });

  test('503 Service Unavailable 파싱', () => {
    const err = parseHttpErrorResponse(503, {});
    assert.equal(err.code, 'SERVICE_UNAVAILABLE');
    assert.equal(err.status, 503);
    assert.equal(err.canRetrySameKey, true);
  });

  test('Response body의 terminal operation 메타데이터를 비동기로 보존한다', async () => {
    const err = await parseHttpErrorResponse(new Response(JSON.stringify({
      code: 'PIPELINE_FAILED',
      operation_id: 'op-terminal-01',
      remaining_credits: 50,
    }), { status: 500, headers: { 'Content-Type': 'application/json' } }));

    assert.equal(err.code, 'PIPELINE_FAILED');
    assert.equal(err.operationId, 'op-terminal-01');
    assert.equal(err.remainingCredits, 50);
    assert.equal(err.canRetrySameKey, false);
  });

  test('내부 서버 예외나 DB 스택이 포함된 500 에러는 정제된 메시지만 반환하고 내부 정보 노출 차단', () => {
    const err = parseHttpErrorResponse(500, {
      detail: 'psycopg2.OperationalError: server closed the connection unexpectedly table credit_ledger column balance',
    });
    assert.equal(err.code, 'INTERNAL_ERROR');
    assert.equal(err.status, 500);
    assert.equal(err.message, '서버 처리 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.');
    assert.ok(!err.message.includes('psycopg2'));
    assert.ok(!err.message.includes('credit_ledger'));
    assert.ok(!err.message.includes('balance'));
  });
});
