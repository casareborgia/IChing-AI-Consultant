/**
 * 크레딧 원장 및 멱등 처리(credit-operation-v1) 프런트엔드 클라이언트 계층
 *
 * 주요 기능:
 * 1. Idempotency-Key 생성 (crypto.randomUUID) 및 재시도 시 동일 키 보존
 * 2. 202 OPERATION_IN_PROGRESS 응답 시 retry_after_seconds 기반 Bounded Polling
 * 3. GET /api/counsel/operations/{operation_id} 상태 및 결과 조회
 * 4. GET /api/me/credits 서버 잔액 단일 출처 조회
 * 5. 정밀 에러 분류 (401, 402, 409, 429, 503, TIMEOUT)
 */

const BACKEND_API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8008');

export type OperationStatus = 'PROCESSING' | 'SUCCEEDED' | 'RELEASED' | 'REJECTED';

export interface OperationResponse {
  operation_id: string;
  operation_status: OperationStatus;
  credit_delta?: number;
  remaining_credits?: number;
  code?: string;
  error_code?: string;
  message?: string;
  retry_after_seconds?: number;
  result?: Record<string, unknown>;
}

export interface CreditsResponse {
  remaining_credits: number;
  welcome_granted: boolean;
}

export class CreditOperationError extends Error {
  code: string;
  status?: number;
  operationId?: string;
  remainingCredits?: number;
  retryAfterSeconds?: number;
  canRetrySameKey: boolean;

  constructor(
    message: string,
    options: {
      code: string;
      status?: number;
      operationId?: string;
      remainingCredits?: number;
      retryAfterSeconds?: number;
      canRetrySameKey?: boolean;
    }
  ) {
    super(message);
    this.name = 'CreditOperationError';
    this.code = options.code;
    this.status = options.status;
    this.operationId = options.operationId;
    this.remainingCredits = options.remainingCredits;
    this.retryAfterSeconds = options.retryAfterSeconds;
    this.canRetrySameKey = options.canRetrySameKey ?? true;
  }
}

/**
 * 새로운 멱등키를 발급합니다.
 * 사용자가 새로운 질문이나 턴을 전송할 때 최초 1회 생성합니다.
 */
export function createIdempotencyKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback for older environments
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * 서버 잔액 조회: GET /api/me/credits
 * Supabase profiles 테이블을 직조회하지 않고, 서버를 단일 진실 공급원(Single Source of Truth)으로 사용합니다.
 * 실패 시 50으로 대체하지 않고 null을 반환하거나 에러를 전파합니다.
 */
export async function fetchMyCredits(token: string): Promise<CreditsResponse | null> {
  try {
    const res = await fetch(`${BACKEND_API_BASE}/api/me/credits`, {
      method: 'GET',
      headers: {
        Accept: 'application/json',
        Authorization: `Bearer ${token}`,
      },
      cache: 'no-store',
    });

    if (!res.ok) {
      return null;
    }

    const data = await res.json();
    if (
      typeof data.remaining_credits === 'number' &&
      Number.isInteger(data.remaining_credits) &&
      data.remaining_credits >= 0
    ) {
      return {
        remaining_credits: data.remaining_credits,
        welcome_granted: Boolean(data.welcome_granted),
      };
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * 개별 operation의 상태 및 저장된 결과를 조회합니다: GET /api/counsel/operations/{operation_id}
 */
export async function fetchOperationStatus(
  operationId: string,
  token: string
): Promise<OperationResponse> {
  const res = await fetch(`${BACKEND_API_BASE}/api/counsel/operations/${encodeURIComponent(operationId)}`, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  });

  if (res.status === 404) {
    throw new CreditOperationError('요청 정보를 찾을 수 없거나 접근 권한이 없습니다.', {
      code: 'OPERATION_NOT_FOUND',
      operationId,
      canRetrySameKey: false,
    });
  }

  if (!res.ok) {
    throw new CreditOperationError(`작업 상태 조회 실패 (${res.status})`, {
      code: `HTTP_${res.status}`,
      operationId,
    });
  }

  const data = await res.json();
  return data as OperationResponse;
}

/**
 * 202 OPERATION_IN_PROGRESS 응답 시 지정된 제한 횟수 내에서 결과를 재조회합니다 (Bounded Polling).
 * 무한 루프를 방지하며, 한도 초과 시 복구 UI를 제공할 수 있도록 예외를 반환합니다.
 */
export async function pollOperationUntilDone(
  operationId: string,
  token: string,
  optionsOrMaxAttempts?:
    | number
    | {
        initialRetryAfterSeconds?: number;
        maxAttempts?: number;
        sleepFn?: (ms: number) => Promise<void>;
      },
  intervalSeconds?: number
): Promise<OperationResponse> {
  let maxAttempts = 8;
  let delaySec = 2;
  let sleep: (ms: number) => Promise<void> = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

  if (typeof optionsOrMaxAttempts === 'number') {
    maxAttempts = optionsOrMaxAttempts;
    if (typeof intervalSeconds === 'number' && intervalSeconds > 0) {
      delaySec = intervalSeconds;
    }
  } else if (optionsOrMaxAttempts && typeof optionsOrMaxAttempts === 'object') {
    if (typeof optionsOrMaxAttempts.maxAttempts === 'number') {
      maxAttempts = optionsOrMaxAttempts.maxAttempts;
    }
    if (typeof optionsOrMaxAttempts.initialRetryAfterSeconds === 'number' && optionsOrMaxAttempts.initialRetryAfterSeconds > 0) {
      delaySec = optionsOrMaxAttempts.initialRetryAfterSeconds;
    }
    if (typeof optionsOrMaxAttempts.sleepFn === 'function') {
      sleep = optionsOrMaxAttempts.sleepFn;
    }
  }

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    await sleep(delaySec * 1000);

    const op = await fetchOperationStatus(operationId, token);
    if (op.operation_status === 'REJECTED') {
      const errSnap = (op as { error_snapshot?: { code?: string; message?: string; remaining_credits?: number } }).error_snapshot || {};
      throw new CreditOperationError(
        errSnap.message || op.message || '요청이 거절되었습니다.',
        {
          code: errSnap.code || op.error_code || op.code || 'OPERATION_REJECTED',
          operationId,
          remainingCredits: typeof errSnap.remaining_credits === 'number' ? errSnap.remaining_credits : op.remaining_credits,
          canRetrySameKey: false,
        }
      );
    }

    if (op.operation_status === 'RELEASED' && !op.result) {
      throw new CreditOperationError(
        '이 요청은 답변을 제공하지 못해 종료되었습니다. 크레딧은 차감되지 않았습니다.',
        {
          code: op.error_code || op.code || 'OPERATION_RELEASED',
          operationId,
          remainingCredits: op.remaining_credits,
          canRetrySameKey: false,
        }
      );
    }

    if (op.operation_status === 'SUCCEEDED' && !op.result) {
      throw new CreditOperationError('완료된 상담 결과를 불러올 수 없습니다.', {
        code: 'OPERATION_RESULT_MISSING',
        operationId,
        remainingCredits: op.remaining_credits,
        canRetrySameKey: false,
      });
    }

    if (op.operation_status !== 'PROCESSING') {
      return op;
    }

    if (typeof op.retry_after_seconds === 'number' && op.retry_after_seconds > 0) {
      delaySec = op.retry_after_seconds;
    } else {
      delaySec = 2;
    }
  }

  throw new CreditOperationError(
    'AI 상담 응답 생성이 지연되고 있습니다. 아래 버튼을 눌러 처리 상태를 다시 확인해 주세요.',
    {
      code: 'POLLING_TIMEOUT',
      operationId,
      canRetrySameKey: true,
    }
  );
}

/**
 * HTTP 에러 응답을 정밀하게 분석하여 안전한 사용자 메시지와 함께 CreditOperationError로 매핑합니다.
 * Response 객체 또는 (status, body) 직접 입력을 모두 지원합니다.
 */
type ErrorResponseBody = {
  code?: string;
  message?: string;
  detail?: string | { code?: string; message?: string; error?: string } | Record<string, unknown>;
  operation_id?: string;
  remaining_credits?: number;
  retry_after_seconds?: number;
};

function resolveErrorMessage(errorData: ErrorResponseBody | Record<string, unknown> | null | undefined, fallback: string): string {
  if (errorData && typeof errorData.message === 'string' && errorData.message.trim()) {
    return errorData.message;
  }
  if (errorData && typeof errorData.detail === 'string' && errorData.detail.trim()) {
    return errorData.detail;
  }
  if (errorData && typeof errorData.detail === 'object' && errorData.detail !== null) {
    const detailObj = errorData.detail as Record<string, unknown>;
    if (typeof detailObj.message === 'string' && detailObj.message.trim()) {
      return detailObj.message;
    }
    if (typeof detailObj.error === 'string' && detailObj.error.trim()) {
      return detailObj.error;
    }
    if (Array.isArray(detailObj) && detailObj[0] && typeof (detailObj[0] as Record<string, unknown>).msg === 'string') {
      return String((detailObj[0] as Record<string, unknown>).msg);
    }
  }
  return fallback;
}

function buildHttpError(
  status: number,
  errorData: ErrorResponseBody,
  operationId?: string
): CreditOperationError {
  const finalOpId = errorData.operation_id || operationId;
  const remCredits = typeof errorData.remaining_credits === 'number' ? errorData.remaining_credits : undefined;

  if (status === 401) {
    return new CreditOperationError('로그인이 필요합니다. 다시 로그인해 주세요.', {
      code: errorData.code || 'UNAUTHORIZED',
      status,
      operationId: finalOpId,
      canRetrySameKey: false,
    });
  }

  if (status === 403) {
    return new CreditOperationError(
      resolveErrorMessage(errorData, '서비스 이용약관 동의가 필요합니다.'),
      {
        code: errorData.code || 'CONSENT_REQUIRED',
        status,
        operationId: finalOpId,
        canRetrySameKey: true,
      }
    );
  }

  if (status === 402) {
    return new CreditOperationError(
      resolveErrorMessage(errorData, '크레딧이 부족합니다. (상담 1회: 10 크레딧 필요)'),
      {
        code: errorData.code || 'INSUFFICIENT_CREDIT',
        status,
        operationId: finalOpId,
        remainingCredits: remCredits,
        canRetrySameKey: false,
      }
    );
  }

  if (status === 409) {
    return new CreditOperationError(
      '이미 다른 요청에 사용된 요청 식별자입니다. 새로운 질문을 작성해 주세요.',
      {
        code: errorData.code || 'IDEMPOTENCY_KEY_REUSED',
        status,
        operationId: finalOpId,
        canRetrySameKey: false,
      }
    );
  }

  if (status === 429) {
    return new CreditOperationError('단시간에 너무 많은 요청이 접수되었습니다. 잠시 후 다시 시도해 주세요.', {
      code: errorData.code || 'RATE_LIMITED',
      status,
      operationId: finalOpId,
      retryAfterSeconds: errorData.retry_after_seconds ?? 5,
      canRetrySameKey: true,
    });
  }

  if (status === 503) {
    const terminal = errorData.code === 'OPERATION_RECOVERED';
    return new CreditOperationError(
      resolveErrorMessage(errorData, '현재 서비스 준비 중이거나 점검 중입니다. 잠시 후 다시 이용해 주세요.'),
      {
        code: errorData.code || 'SERVICE_UNAVAILABLE',
        status,
        operationId: finalOpId,
        remainingCredits: remCredits,
        canRetrySameKey: !terminal,
      }
    );
  }

  if (status >= 500) {
    const terminal = errorData.code === 'PIPELINE_FAILED' || errorData.code === 'OPERATION_RECOVERED';
    return new CreditOperationError(
      '서버 처리 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
      {
        code: errorData.code || 'INTERNAL_ERROR',
        status,
        operationId: finalOpId,
        remainingCredits: remCredits,
        canRetrySameKey: !terminal,
      }
    );
  }

  return new CreditOperationError(
    resolveErrorMessage(errorData, '상담 처리 중 일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.'),
    {
      code: errorData.code || `HTTP_${status}`,
      status,
      operationId: finalOpId,
      remainingCredits: remCredits,
      canRetrySameKey: true,
    }
  );
}

export function parseHttpErrorResponse(
  status: number,
  body?: unknown,
  operationId?: string
): CreditOperationError;
export function parseHttpErrorResponse(
  response: Response,
  operationId?: string
): Promise<CreditOperationError>;
export function parseHttpErrorResponse(
  resOrStatus: Response | number,
  bodyOrOperationId?: unknown,
  maybeOperationId?: string
): CreditOperationError | Promise<CreditOperationError> {
  if (typeof resOrStatus === 'number') {
    let errorData: ErrorResponseBody = {};
    if (bodyOrOperationId && typeof bodyOrOperationId === 'object') {
      errorData = bodyOrOperationId as ErrorResponseBody;
    }
    const operationId = maybeOperationId || errorData.operation_id;
    return buildHttpError(resOrStatus, errorData, operationId);
  }

  const operationId = typeof bodyOrOperationId === 'string' ? bodyOrOperationId : undefined;
  return resOrStatus
    .json()
    .catch(() => ({}))
    .then((body) =>
      buildHttpError(
        resOrStatus.status,
        body && typeof body === 'object' ? (body as ErrorResponseBody) : {},
        operationId
      )
    );
}
