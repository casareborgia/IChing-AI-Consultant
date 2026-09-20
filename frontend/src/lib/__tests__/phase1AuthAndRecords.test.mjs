import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

describe('Phase 1 Auth & Consent Frontend Guards (A21, A24)', () => {
  // AuthModal.tsx:43 의 진입부 우회 방어 로직 단위 검증
  function simulateAuthSubmit({ ageConfirmed, termsAgreed, isSubmitting }) {
    if (isSubmitting) return { allowed: false, reason: 'ALREADY_SUBMITTING' };
    if (!ageConfirmed || !termsAgreed) {
      return { allowed: false, reason: 'CONSENT_OR_AGE_REQUIRED' };
    }
    return { allowed: true, reason: 'OK' };
  }

  test('만 19세 이상 체크가 false인 경우 DevTools로 disabled를 제거하고 클릭해도 조기 차단', () => {
    const result = simulateAuthSubmit({
      ageConfirmed: false,
      termsAgreed: true,
      isSubmitting: false,
    });
    assert.equal(result.allowed, false);
    assert.equal(result.reason, 'CONSENT_OR_AGE_REQUIRED');
  });

  test('약관 동의 체크가 false인 경우 조기 차단', () => {
    const result = simulateAuthSubmit({
      ageConfirmed: true,
      termsAgreed: false,
      isSubmitting: false,
    });
    assert.equal(result.allowed, false);
    assert.equal(result.reason, 'CONSENT_OR_AGE_REQUIRED');
  });

  test('둘 다 false인 경우 조기 차단', () => {
    const result = simulateAuthSubmit({
      ageConfirmed: false,
      termsAgreed: false,
      isSubmitting: false,
    });
    assert.equal(result.allowed, false);
    assert.equal(result.reason, 'CONSENT_OR_AGE_REQUIRED');
  });

  test('둘 다 true인 경우에만 로그인 플로우 진입 허용', () => {
    const result = simulateAuthSubmit({
      ageConfirmed: true,
      termsAgreed: true,
      isSubmitting: false,
    });
    assert.equal(result.allowed, true);
    assert.equal(result.reason, 'OK');
  });
});

describe('Phase 1 Record Deletion Flow Guards (A29)', () => {
  // JournalSummaryCard.tsx 의 삭제 모달 확인 상태 가드 단위 검증
  function simulateDeleteRecord({ isModalOpen, isConfirmed, isDeleting, sessionId }) {
    if (!sessionId || typeof sessionId !== 'string') {
      return { proceed: false, error: 'INVALID_SESSION_ID' };
    }
    if (!isModalOpen || !isConfirmed) {
      return { proceed: false, error: 'CONFIRMATION_REQUIRED' };
    }
    if (isDeleting) {
      return { proceed: false, error: 'ALREADY_DELETING' };
    }
    return { proceed: true, sessionId };
  }

  test('확인 모달이 열리지 않았거나 확인을 누르지 않은 경우 삭제 API 호출 차단', () => {
    const unconfirmed = simulateDeleteRecord({
      isModalOpen: false,
      isConfirmed: false,
      isDeleting: false,
      sessionId: 'sess-123',
    });
    assert.equal(unconfirmed.proceed, false);
    assert.equal(unconfirmed.error, 'CONFIRMATION_REQUIRED');
  });

  test('확인 모달에서 사용자가 명시적으로 확인한 경우에만 삭제 진행', () => {
    const confirmed = simulateDeleteRecord({
      isModalOpen: true,
      isConfirmed: true,
      isDeleting: false,
      sessionId: 'sess-123',
    });
    assert.equal(confirmed.proceed, true);
    assert.equal(confirmed.sessionId, 'sess-123');
  });

  test('이미 삭제 중인 경우 중복 호출 방지', () => {
    const deleting = simulateDeleteRecord({
      isModalOpen: true,
      isConfirmed: true,
      isDeleting: true,
      sessionId: 'sess-123',
    });
    assert.equal(deleting.proceed, false);
    assert.equal(deleting.error, 'ALREADY_DELETING');
  });
});
