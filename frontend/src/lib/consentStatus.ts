// -*- coding: utf-8 -*-
/**
 * 법적 동의 상태 판정 로직 (순수 함수).
 *
 * 지시서(RECONSENT_UX_ORDER.md §2.1) 규칙:
 * 1. current가 없음                   -> 동의 필요 (신규 또는 미기록)
 * 2. action != 'GRANT'                -> 동의 필요 (철회됨)
 * 3. privacy_version != 서버 현재 버전 -> 동의 필요 (개정됨)
 * 4. terms_version != 서버 현재 버전   -> 동의 필요 (개정됨)
 * 5. 그 외                             -> 동의 유효 (Valid)
 */

import type { ConsentRecord } from './api';

export type ConsentStatus = 'VALID' | 'NEEDS_CONSENT';

export interface ConsentEvaluationResult {
  status: ConsentStatus;
  needsReconsent: boolean;
  reason: 'NO_RECORD' | 'WITHDRAWN' | 'VERSION_MISMATCH' | 'VALID';
  details?: string;
}

export function evaluateConsentStatus(
  currentRecord: ConsentRecord | null | undefined,
  expectedVersion: string
): ConsentEvaluationResult {
  const normalizedExpected = (expectedVersion || '').trim();

  // 1. 동의 기록이 아예 없는 경우
  if (!currentRecord) {
    return {
      status: 'NEEDS_CONSENT',
      needsReconsent: true,
      reason: 'NO_RECORD',
      details: '동의 이력이 존재하지 않습니다.',
    };
  }

  // 2. 최신 action이 GRANT가 아닌 경우 (예: WITHDRAW)
  if (currentRecord.action !== 'GRANT') {
    return {
      status: 'NEEDS_CONSENT',
      needsReconsent: true,
      reason: 'WITHDRAWN',
      details: `동의가 철회된 상태입니다 (action: ${currentRecord.action}).`,
    };
  }

  // 3. 서버 기대 버전이 없는 경우 (fail-closed)
  if (!normalizedExpected) {
    return {
      status: 'NEEDS_CONSENT',
      needsReconsent: true,
      reason: 'VERSION_MISMATCH',
      details: '서버의 정책 문서 버전이 설정되지 않았습니다.',
    };
  }

  // 4. 개인정보처리방침 또는 약관 버전이 서버 현재 버전과 다른 경우
  if (
    currentRecord.privacy_version !== normalizedExpected ||
    currentRecord.terms_version !== normalizedExpected
  ) {
    return {
      status: 'NEEDS_CONSENT',
      needsReconsent: true,
      reason: 'VERSION_MISMATCH',
      details: `동의 버전이 개정되었습니다 (기록: P=${currentRecord.privacy_version}, T=${currentRecord.terms_version} / 서버: ${normalizedExpected}).`,
    };
  }

  // 5. 모두 만족 시 동의 유효
  return {
    status: 'VALID',
    needsReconsent: false,
    reason: 'VALID',
  };
}
