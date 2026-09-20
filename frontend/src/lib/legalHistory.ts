// -*- coding: utf-8 -*-
/**
 * 이용약관 및 개인정보처리방침 개정 이력 데이터 (단일 출처).
 *
 * 재동의 모달(ReconsentModal)과 정책 페이지(/privacy, /terms)가 이 데이터를 공유합니다.
 * 모달에 변경 내용을 직접 하드코딩하지 않고 여기서 참조하여 어긋남을 방지합니다.
 */

export interface LegalRevisionItem {
  version: string;
  effectiveDate: string;
  summary: string;
  changes: string[];
}

export const LEGAL_REVISIONS: LegalRevisionItem[] = [
  {
    version: '2026-09-12',
    effectiveDate: '2026-09-12',
    summary: '서비스 이용약관 및 개인정보처리방침 최초 제정',
    changes: [
      '서비스 이용약관 및 개인정보처리방침 최초 제정 및 시행',
      'AI 기반 주역 심층 성찰 상담 서비스 제공을 위한 필수 법적 고지',
    ],
  },
  {
    version: '2026-09-19',
    effectiveDate: '2026-09-19',
    summary: '방문 통계 가명처리 수집 고지 및 브라우저 저장소 이용 정책 명확화',
    changes: [
      '자체 방문 통계(site_visits) 수집 항목 추가 (진입 경로, 외부 유입 도메인, 기기 유형)',
      '방문 통계를 위한 브라우저 저장소(localStorage/sessionStorage) 이용 및 거부 방법 고지',
      '방문자 식별자를 서버 솔트(pepper)와 결합한 일방향 가명처리 정보로 성격 명확화',
    ],
  },
];

/**
 * 가장 최근 변경 항목 (재동의 모달에서 표시할 대상).
 */
export const LATEST_LEGAL_REVISION: LegalRevisionItem = LEGAL_REVISIONS[LEGAL_REVISIONS.length - 1];
