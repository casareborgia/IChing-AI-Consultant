/**
 * 공개 서비스 설정 소비 계층 (Public Config Consumer)
 *
 * Claude fa9b038 계약 기반 (GET /api/public/config):
 * - service_stage: 'free_beta' | 'commercial' | 'preparing'
 * - purchase_enabled: boolean
 * - generation_enabled: boolean
 * - consultation_credit_cost: number
 * - welcome_credits: number
 * - policy_documents_draft: boolean
 *
 * Fail-safe 원칙: 서버 연결 실패, 미구현(404), 또는 네트워크 에러 발생 시
 * 무조건 "준비 중 / 정책 초안 / 구매 불가 / 생성 비활성" 안전 기본값을 반환합니다.
 */

import { useEffect, useState } from 'react';

export const ALLOWED_SERVICE_STAGES = ['free_beta', 'preparing', 'commercial'] as const;
export type ServiceStage = (typeof ALLOWED_SERVICE_STAGES)[number];

export interface PublicConfig {
  service_stage: ServiceStage;
  purchase_enabled: boolean;
  generation_enabled: boolean;
  consultation_credit_cost: number;
  welcome_credits: number;
  policy_documents_draft: boolean;
  free_beta_ready?: boolean;
  legal_documents_version?: string;
  free_beta_refill_credits?: number;
  free_beta_refill_hours?: number;
}

export const FALLBACK_PUBLIC_CONFIG: PublicConfig = {
  service_stage: 'preparing',
  purchase_enabled: false,
  generation_enabled: false,
  consultation_credit_cost: 10,
  welcome_credits: 50,
  policy_documents_draft: true,
  free_beta_ready: false,
  legal_documents_version: '',
  free_beta_refill_credits: 50,
  free_beta_refill_hours: 12,
};

const BACKEND_API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8008');

/**
 * 런타임 응답 데이터를 unknown에서 시작해 엄격하게 파싱하고 유효성을 검증합니다.
 * truthy 변환(Boolean(x) 등)을 절대 사용하지 않으며, 단 하나의 필드라도 타입 또는 제약조건을 위반하면
 * 즉시 안전 기본값(FALLBACK_PUBLIC_CONFIG)을 반환하여 잘못된 활성 상태 승격을 차단합니다.
 */
export function parsePublicConfig(raw: unknown): PublicConfig {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return FALLBACK_PUBLIC_CONFIG;
  }

  const record = raw as Record<string, unknown>;

  // 1. service_stage: allowlist 문자열만 허용
  const stage = record.service_stage;
  if (
    typeof stage !== 'string' ||
    !ALLOWED_SERVICE_STAGES.includes(stage as ServiceStage)
  ) {
    return FALLBACK_PUBLIC_CONFIG;
  }

  // 2. boolean 필드: typeof value === 'boolean' 만 허용
  // 문자열 "true"/"false", 숫자 0/1, null, 배열, 객체 등은 계약 위반으로 fail-safe 처리
  if (typeof record.purchase_enabled !== 'boolean') {
    return FALLBACK_PUBLIC_CONFIG;
  }
  if (typeof record.generation_enabled !== 'boolean') {
    return FALLBACK_PUBLIC_CONFIG;
  }
  if (typeof record.policy_documents_draft !== 'boolean') {
    return FALLBACK_PUBLIC_CONFIG;
  }

  // free_beta_ready: 선택 필드이나, 존재할 경우 반드시 boolean이어야 함
  let freeBetaReady = false;
  if ('free_beta_ready' in record && record.free_beta_ready !== undefined) {
    if (typeof record.free_beta_ready !== 'boolean') {
      return FALLBACK_PUBLIC_CONFIG;
    }
    freeBetaReady = record.free_beta_ready;
  }

  // 3. credit 필드: 유한한 비음수 정수(finite non-negative integer)만 허용
  const consultCost = record.consultation_credit_cost;
  if (
    typeof consultCost !== 'number' ||
    !Number.isInteger(consultCost) ||
    consultCost < 0
  ) {
    return FALLBACK_PUBLIC_CONFIG;
  }

  const welcomeCredits = record.welcome_credits;
  if (
    typeof welcomeCredits !== 'number' ||
    !Number.isInteger(welcomeCredits) ||
    welcomeCredits < 0
  ) {
    return FALLBACK_PUBLIC_CONFIG;
  }

  // 4. legal_documents_version: 선택 필드이나, 존재할 경우 반드시 string이어야 함
  let legalDocumentsVersion = '';
  if ('legal_documents_version' in record && record.legal_documents_version !== undefined) {
    if (typeof record.legal_documents_version !== 'string') {
      return FALLBACK_PUBLIC_CONFIG;
    }
    legalDocumentsVersion = record.legal_documents_version;
  }

  // 5. 12시간 자동 충전 설정 (선택 필드, 기본 50C / 12시간)
  let refillCredits = 50;
  if ('free_beta_refill_credits' in record && typeof record.free_beta_refill_credits === 'number') {
    refillCredits = record.free_beta_refill_credits;
  }
  let refillHours = 12;
  if ('free_beta_refill_hours' in record && typeof record.free_beta_refill_hours === 'number') {
    refillHours = record.free_beta_refill_hours;
  }

  return {
    service_stage: stage as ServiceStage,
    purchase_enabled: record.purchase_enabled,
    generation_enabled: record.generation_enabled,
    policy_documents_draft: record.policy_documents_draft,
    free_beta_ready: freeBetaReady,
    legal_documents_version: legalDocumentsVersion,
    consultation_credit_cost: consultCost,
    welcome_credits: welcomeCredits,
    free_beta_refill_credits: refillCredits,
    free_beta_refill_hours: refillHours,
  };
}

/**
 * 활성 무료 베타 여부를 판정합니다.
 *
 * 4대 필수 조건:
 * 1. service_stage === 'free_beta'
 * 2. generation_enabled === true
 * 3. policy_documents_draft === false
 * 4. free_beta_ready === true
 *
 * 4개 중 하나라도 미충족(또는 null/undefined/fail-safe)이면 false를 반환합니다.
 */
export function isFreeBetaActive(config: PublicConfig | null | undefined): boolean {
  if (!config) return false;
  return (
    config.service_stage === 'free_beta' &&
    config.generation_enabled === true &&
    config.policy_documents_draft === false &&
    config.free_beta_ready === true
  );
}

/**
 * 서버의 최소 공개 설정을 안전하게 조회합니다.
 * 타임아웃, 404, 네트워크 실패, 잘못된 JSON 파싱, 필드 누락 및 타입 오류 시 fail-safe로 FALLBACK_PUBLIC_CONFIG를 반환합니다.
 */
export async function fetchPublicConfig(timeoutMs: number = 4000): Promise<PublicConfig> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BACKEND_API_BASE}/api/public/config`, {
      method: 'GET',
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal: controller.signal,
    });

    if (!res.ok) {
      return FALLBACK_PUBLIC_CONFIG;
    }

    const data: unknown = await res.json();
    return parsePublicConfig(data);
  } catch {
    return FALLBACK_PUBLIC_CONFIG;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * 클라이언트 컴포넌트에서 공개 설정을 구독하는 리액트 훅
 */
export function usePublicConfig(): {
  config: PublicConfig;
  isLoading: boolean;
  isFallback: boolean;
  isFreeBetaActive: boolean;
} {
  const [config, setConfig] = useState<PublicConfig>(FALLBACK_PUBLIC_CONFIG);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isFallback, setIsFallback] = useState<boolean>(true);

  useEffect(() => {
    let isMounted = true;
    fetchPublicConfig().then((res) => {
      if (isMounted) {
        setConfig(res);
        setIsFallback(res === FALLBACK_PUBLIC_CONFIG);
        setIsLoading(false);
      }
    });
    return () => {
      isMounted = false;
    };
  }, []);

  return { config, isLoading, isFallback, isFreeBetaActive: isFreeBetaActive(config) };
}
