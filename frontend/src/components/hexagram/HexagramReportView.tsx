'use client';

import React from 'react';
import {
  CastResult,
  ChatMessage,
  AnyReportData,
  PreCounselingReportV2,
  HexagramReportData,
  reportSchemaVersion,
} from '../../types/iching';
import { HexagramReportViewV1 } from './HexagramReportViewV1';
import { HexagramReportViewV2 } from './HexagramReportViewV2';
import { HexagramReportFailureView } from './HexagramReportFailureView';

export interface HexagramReportViewProps {
  castResult: CastResult;
  userQuestion: string;
  firstMessage?: ChatMessage;
  reportData?: AnyReportData | null;
  reportStatus?: 'ready' | 'failed' | 'not_requested';
  reportErrorCode?: string | null;
  isLoggedIn?: boolean;
  onProceedToCounsel: () => void;
}

/**
 * 점괘 사전 분석 리포트 판본 분기 뷰 (Dispatcher)
 *
 * 분기 규칙 (인계 문서 §1):
 * 1. reportStatus === 'failed' -> 실패 화면 (오류 코드 안내, 상담은 그대로 연결)
 * 2. schema_version === '2.0' -> HexagramReportViewV2 렌더
 * 3. schema_version === undefined/null -> HexagramReportViewV1 (과거 v1 레거시 뷰)
 * 4. schema_version === 'unknown' (예: '3.0') -> 실패 화면 (legacy로 떨어뜨려 빈 리포트 방지)
 */
export const HexagramReportView: React.FC<HexagramReportViewProps> = ({
  castResult,
  userQuestion,
  firstMessage,
  reportData,
  reportStatus = 'ready',
  reportErrorCode,
  isLoggedIn = true,
  onProceedToCounsel,
}) => {
  // 1. 서버에서 명시적으로 실패 통보한 경우
  if (reportStatus === 'failed') {
    return (
      <HexagramReportFailureView
        errorCode={reportErrorCode}
        onProceedToCounsel={onProceedToCounsel}
      />
    );
  }

  // 2. 데이터가 없거나 비어 있는 경우
  if (!reportData) {
    return (
      <HexagramReportFailureView
        errorCode={reportErrorCode || 'REPORT_UNAVAILABLE'}
        onProceedToCounsel={onProceedToCounsel}
      />
    );
  }

  // 3. 판본 판별
  const version = reportSchemaVersion(reportData);

  // v2.0 정규 리포트
  if (version === '2.0') {
    return (
      <HexagramReportViewV2
        report={reportData as PreCounselingReportV2}
        isLoggedIn={isLoggedIn}
        onProceedToCounsel={onProceedToCounsel}
      />
    );
  }

  // 과거 v1 레거시 리포트 (판본 표기 없음)
  if (version === 'legacy') {
    return (
      <HexagramReportViewV1
        castResult={castResult}
        userQuestion={userQuestion}
        firstMessage={firstMessage}
        reportData={reportData as HexagramReportData}
        isLoggedIn={isLoggedIn}
        onProceedToCounsel={onProceedToCounsel}
      />
    );
  }

  // 알 수 없는 미지원 판본 ('unknown' / '3.0' 등) -> 모르는 판본을 legacy로 읽지 않고 실패 처리
  return (
    <HexagramReportFailureView
      errorCode="REPORT_UNAVAILABLE"
      onProceedToCounsel={onProceedToCounsel}
    />
  );
};
