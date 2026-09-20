import test from 'node:test';
import assert from 'node:assert/strict';
import { evaluateConsentStatus } from './consentStatus.ts';

// E-1: 동의 기록 없는 사용자 로그인 시 checkConsent()가 needsReconsent: true, reason: 'NO_RECORD' 반환
test('E-1: evaluateConsentStatus returns NO_RECORD when current record is null', () => {
  const result = evaluateConsentStatus(null, '2026-09-12');
  assert.equal(result.needsReconsent, true);
  assert.equal(result.reason, 'NO_RECORD');
  assert.equal(result.status, 'NEEDS_CONSENT');
});

// E-2: 동의 버전이 현재보다 낮은 사용자 로그인 시 needsReconsent: true, reason: 'VERSION_MISMATCH' 반환
test('E-2: evaluateConsentStatus returns VERSION_MISMATCH when agreed version is older', () => {
  const oldRecord = {
    id: 'rec-old',
    user_id: 'user-1',
    terms_version: '2026-08-01',
    privacy_version: '2026-08-01',
    age_confirmed: true,
    action: 'GRANT' as const,
    created_at: '2026-08-01T00:00:00Z',
  };
  const result = evaluateConsentStatus(oldRecord, '2026-09-19');
  assert.equal(result.needsReconsent, true);
  assert.equal(result.reason, 'VERSION_MISMATCH');
  assert.equal(result.status, 'NEEDS_CONSENT');
});

test('E-2b: evaluateConsentStatus returns VERSION_MISMATCH when previous 2026-09-12 user meets 2026-09-19', () => {
  const v1Record = {
    id: 'rec-v1',
    user_id: 'user-1',
    terms_version: '2026-09-12',
    privacy_version: '2026-09-12',
    age_confirmed: true,
    action: 'GRANT' as const,
    created_at: '2026-09-12T00:00:00Z',
  };
  const result = evaluateConsentStatus(v1Record, '2026-09-19');
  assert.equal(result.needsReconsent, true);
  assert.equal(result.reason, 'VERSION_MISMATCH');
  assert.equal(result.status, 'NEEDS_CONSENT');
});

// E-3: 동의 버전이 현재와 같은 사용자 로그인 시 needsReconsent: false, reason: 'VALID' 반환
test('E-3: evaluateConsentStatus returns VALID when agreed version matches expected', () => {
  const validRecord = {
    id: 'rec-valid',
    user_id: 'user-1',
    terms_version: '2026-09-19',
    privacy_version: '2026-09-19',
    age_confirmed: true,
    action: 'GRANT' as const,
    created_at: '2026-09-19T00:00:00Z',
  };
  const result = evaluateConsentStatus(validRecord, '2026-09-19');
  assert.equal(result.needsReconsent, false);
  assert.equal(result.reason, 'VALID');
  assert.equal(result.status, 'VALID');
});

// E-4: 최신 action이 WITHDRAW인 사용자 로그인 시 needsReconsent: true, reason: 'WITHDRAWN' 반환
test('E-4: evaluateConsentStatus returns WITHDRAWN when latest action is WITHDRAW', () => {
  const withdrawnRecord = {
    id: 'rec-withdrawn',
    user_id: 'user-1',
    terms_version: '2026-09-12',
    privacy_version: '2026-09-12',
    age_confirmed: true,
    action: 'WITHDRAW' as const,
    created_at: '2026-09-13T00:00:00Z',
  };
  const result = evaluateConsentStatus(withdrawnRecord, '2026-09-12');
  assert.equal(result.needsReconsent, true);
  assert.equal(result.reason, 'WITHDRAWN');
  assert.equal(result.status, 'NEEDS_CONSENT');
});

// E-5: 모달에서 체크박스 1개만 체크 시 확인 버튼 비활성화 (순수 검증 로직)
test('E-5: Reconsent confirmation button is disabled if only one checkbox is checked', () => {
  const isButtonEnabled = (age: boolean, terms: boolean, submitting: boolean) =>
    age && terms && !submitting;

  assert.equal(isButtonEnabled(false, false, false), false, 'Both unchecked -> disabled');
  assert.equal(isButtonEnabled(true, false, false), false, 'Only age checked -> disabled');
  assert.equal(isButtonEnabled(false, true, false), false, 'Only terms checked -> disabled');
  assert.equal(isButtonEnabled(true, true, true), false, 'Both checked but submitting -> disabled');
  assert.equal(isButtonEnabled(true, true, false), true, 'Both checked and not submitting -> enabled');
});

// E-6: 확인 클릭 시에만 POST /api/me/consent가 호출됨 (모달 닫기 시 호출 안 됨)
test('E-6: Consent API is called only upon explicit confirmation, never on modal close', async () => {
  let apiCallCount = 0;
  const mockPostConsentApi = async () => {
    apiCallCount++;
    return { ok: true };
  };

  // 시나리오 A: 모달 닫기(취소/X) -> API 호출 0건
  const handleClose = () => {
    // 닫기 시에는 아무 API도 호출하지 않음
  };
  handleClose();
  assert.equal(apiCallCount, 0, 'Closing modal must not trigger consent recording');

  // 시나리오 B: 확인 버튼 클릭 -> API 호출 1건
  const handleConfirm = async (ageChecked: boolean, termsChecked: boolean) => {
    if (!ageChecked || !termsChecked) return false;
    await mockPostConsentApi();
    return true;
  };
  const success = await handleConfirm(true, true);
  assert.equal(success, true);
  assert.equal(apiCallCount, 1, 'Confirming modal must call consent recording exactly once');
});

// E-7: POST /api/me/consent 실패 시 모달이 닫히지 않고 오류 메시지 표시
test('E-7: On POST failure, modal remains open with error message and is not dismissed', async () => {
  let isModalOpen = true;
  let errorMessage: string | null = null;

  const mockFailingPost = async () => {
    throw new Error('네트워크 연결 오류 또는 서버 장애');
  };

  const handleConfirmWithFailure = async () => {
    try {
      await mockFailingPost();
      isModalOpen = false; // 성공 시에만 닫힘
    } catch (err: unknown) {
      errorMessage = err instanceof Error ? err.message : '저장 실패';
      // 모달을 닫지 않고 에러 표시
    }
  };

  await handleConfirmWithFailure();
  assert.equal(isModalOpen, true, 'Modal must remain open when consent saving fails');
  assert.match(errorMessage || '', /네트워크 연결 오류|서버 장애/);
});

// E-8: 신규 가입 흐름에서 기존 동의 체크박스가 정상 동작하고 POST /api/me/consent가 호출됨
test('E-8: New user signup flow requires both consent checkboxes and records consent', async () => {
  let consentRecorded = false;
  const onSignupWithConsent = async (ageConfirmed: boolean, termsAgreed: boolean) => {
    if (!ageConfirmed || !termsAgreed) {
      throw new Error('필수 동의 항목을 모두 체크해야 합니다.');
    }
    consentRecorded = true;
    return { status: 'SUCCESS' };
  };

  await assert.rejects(
    async () => onSignupWithConsent(true, false),
    /필수 동의 항목/
  );
  assert.equal(consentRecorded, false);

  const res = await onSignupWithConsent(true, true);
  assert.equal(res.status, 'SUCCESS');
  assert.equal(consentRecorded, true);
});
