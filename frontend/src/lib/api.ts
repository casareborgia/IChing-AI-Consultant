import { CastResult, ChatMessage, GroundEvidence, JournalSummary, LineInfo, LineValue, HexagramReportData } from '../types/iching';
import { HEXAGRAMS_META, HEXAGRAM_ID_TO_BINARY } from '../data/hexagramsData';
import { supabase } from './supabaseClient';

const BACKEND_API_BASE =
  process.env.NEXT_PUBLIC_API_URL ||
  (process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8008');

/**
 * 백엔드 hexagram_id와 changing_lines를 기반으로 프론트엔드 CastResult 구성
 */
function buildCastResultFromBackend(
  hexId: number,
  transformedHexId: number,
  changingLines: number[] = [],
  rawFocusRule?: {
    focus_type?: string;
    target_hexagram_type?: 'ORIGINAL' | 'TRANSFORMED' | 'BOTH';
    target_line_numbers?: number[];
    description_ko?: string;
    body_use_type?: 'EMPHASIZE_ORIGINAL' | 'EMPHASIZE_TRANSFORMED' | 'STANDARD';
    body_use_note_ko?: string | null;
  }
): CastResult {
  const binary = HEXAGRAM_ID_TO_BINARY[hexId] || '111111';
  const lines: LineInfo[] = [];

  for (let i = 0; i < 6; i++) {
    const position = i + 1; // 1 ~ 6
    const isYang = binary[i] === '1';
    const isChanging = changingLines.includes(position);

    let value: LineValue = 7;
    if (isYang) {
      value = isChanging ? 9 : 7; // 노양 / 소양
    } else {
      value = isChanging ? 6 : 8; // 노음 / 소음
    }

    lines.push({
      position,
      value,
      isYang,
      isChanging,
    });
  }

  const focusRule = rawFocusRule
    ? {
        focusType: rawFocusRule.focus_type || 'ORIGINAL_JUDGMENT',
        targetHexagramType: rawFocusRule.target_hexagram_type || 'ORIGINAL',
        targetLineNumbers: rawFocusRule.target_line_numbers || [],
        descriptionKo: rawFocusRule.description_ko || '',
        bodyUseType: rawFocusRule.body_use_type || 'STANDARD',
        bodyUseNoteKo: rawFocusRule.body_use_note_ko || null,
      }
    : undefined;

  return {
    originalHexId: hexId,
    transformedHexId: transformedHexId || hexId,
    lines,
    changingPositions: changingLines,
    focusRule,
  };
}

/** 백엔드가 내려준 근거를 화면 표시용으로 옮긴다.
 *
 * 예전에는 이 자리에서 정적 표(HEXAGRAMS_META)로 근거를 조립했다. "정전(程傳) 및
 * 본의(本義) 주석"이라는 제목을 달았지만 정전을 한 번도 거치지 않은 템플릿 문장이었고,
 * "괘사"라고 표시한 것도 괘사가 아니라 natureSummary(정적 요약)였다. 2,536건 인덱스를
 * 쌓아두고 화면에 나가는 근거는 그중 한 건도 아니었다.
 *
 * 이제는 백엔드가 "답변을 만들 때 프롬프트에 실제로 들어간 청크"만 내려준다.
 * 근거가 없는 턴이면 빈 배열이고, 그때는 패널 자체가 뜨지 않는다 — 없는 근거를
 * 있는 것처럼 채우지 않는다.
 */
function mapEvidences(raw: unknown): GroundEvidence[] | undefined {
  if (!Array.isArray(raw) || raw.length === 0) return undefined;

  return raw
    .map((item) => {
      const e = item as {
        source_type?: string;
        source_title?: string;
        content?: string;
      };
      const sourceType: GroundEvidence['sourceType'] = e.source_type?.startsWith('benui')
        ? 'benui'
        : e.source_type?.startsWith('sosang')
          ? 'sosang'
          : e.source_type === 'guasa_comm'
            ? 'guasa'
            : 'jeongjeon';

      return {
        sourceType,
        sourceTitle: e.source_title || '해설',
        content: (e.content || '').trim(),
      };
    })
    .filter((e) => e.content.length > 0);
}

import { CrisisResourceItem } from '../components/safety/CrisisSupportCard';

export async function fetchCrisisResourcesApi(context?: string): Promise<CrisisResourceItem[]> {
  try {
    const url = context
      ? `${BACKEND_API_BASE}/api/safety/resources?context=${encodeURIComponent(context)}`
      : `${BACKEND_API_BASE}/api/safety/resources`;
    const res = await fetch(url);
    if (!res.ok) return [];
    const data = await res.json();
    return data.resources || [];
  } catch (e) {
    console.error('위기 리소스 조회 실패:', e);
    return [];
  }
}

import {
  createIdempotencyKey,
  pollOperationUntilDone,
  parseHttpErrorResponse,
  OperationStatus,
} from './creditOperation';
import { AnyReportData } from '../types/iching';

export type ReportErrorCode =
  | 'REPORT_EVIDENCE_INVALID'
  | 'REPORT_NARRATIVE_INVALID'
  | 'REPORT_MODEL_FAILED'
  | 'REPORT_UNAVAILABLE';

export function getReportErrorMessage(code?: string | null): string {
  switch (code) {
    case 'REPORT_EVIDENCE_INVALID':
      return '점서 근거를 확정하는 과정에서 정합성이 맞지 않아 리포트 생성을 건너뛰었습니다.';
    case 'REPORT_NARRATIVE_INVALID':
      return '해석 서술 검증 기준을 충족하지 못해 리포트를 발행하지 않았습니다.';
    case 'REPORT_MODEL_FAILED':
      return 'AI 분석 모델의 일시적 응답 지연으로 리포트가 생성되지 못했습니다.';
    case 'REPORT_UNAVAILABLE':
    default:
      return '리포트를 일시적으로 불러올 수 없습니다. 괘 도출 결과는 정상이며 상담 대화는 바로 이어가실 수 있습니다.';
  }
}

export interface StartConsultationResult {
  sessionId: string;
  isCrisis: boolean;
  crisisResources?: CrisisResourceItem[];
  isDuplicate: boolean;
  castResult?: CastResult;
  firstMessage?: ChatMessage;
  remainingCredits?: number;
  creditDelta?: number;
  operationId?: string;
  operationStatus?: OperationStatus;
  reportData?: AnyReportData;
  reportStatus?: 'ready' | 'failed' | 'not_requested';
  reportErrorCode?: string;
}

export async function startConsultationApi(
  question: string,
  _userId?: string,
  options: {
    idempotencyKey?: string;
  } = {}
): Promise<StartConsultationResult> {
  const idempotencyKey = options.idempotencyKey || createIdempotencyKey();

  const { data: { session } } = await supabase.auth.getSession();
  let token = session?.access_token;
  if (!token && process.env.NODE_ENV !== 'production') {
    token = 'dev-token';
  }

  if (!token) {
    throw new Error('로그인이 필요한 서비스입니다. 먼저 로그인해 주세요.');
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND_API_BASE}/api/counsel/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({
        question,
      }),
    });
  } catch (netErr: unknown) {
    const msg = netErr instanceof Error ? netErr.message : '네트워크 통신 오류가 발생했습니다.';
    throw new Error(`서버에 연결할 수 없습니다 (${msg}). 인터넷 상태를 확인해 주세요.`);
  }

  let data: Record<string, unknown>;

  // 202 OPERATION_IN_PROGRESS 수신 시 Bounded Polling 수행
  if (res.status === 202) {
    const progressData = await res.json().catch(() => ({}));
    const operationId = progressData.operation_id;
    if (!operationId) {
      throw new Error('서버에서 작업 식별자(operation_id)를 받지 못했습니다.');
    }

    const completedOp = await pollOperationUntilDone(operationId, token, {
      initialRetryAfterSeconds: progressData.retry_after_seconds,
    });

    if (completedOp.operation_status === 'REJECTED') {
      throw new Error(completedOp.message || '상담 요청이 거부되었습니다.');
    }

    data = (completedOp.result || {}) as Record<string, unknown>;
    data.operation_id = completedOp.operation_id;
    data.operation_status = completedOp.operation_status;
    data.credit_delta = completedOp.credit_delta;
    data.remaining_credits = completedOp.remaining_credits;
  } else if (!res.ok) {
    const parsedErr = await parseHttpErrorResponse(res);
    throw parsedErr;
  } else {
    data = await res.json();
  }

  if (data.is_crisis) {
    return {
      sessionId: (data.session_id as string) || `crisis-${Date.now()}`,
      isCrisis: true,
      crisisResources: (data.crisis_resources as CrisisResourceItem[]) || [],
      isDuplicate: false,
      remainingCredits: typeof data.remaining_credits === 'number' ? data.remaining_credits : undefined,
      creditDelta: typeof data.credit_delta === 'number' ? data.credit_delta : 0,
      operationId: (data.operation_id as string) || undefined,
      operationStatus: (data.operation_status as OperationStatus) || 'RELEASED',
    };
  }

  const hexId = (data.hexagram_id as number) || 1;
  const transHexId = (data.transformed_hexagram_id as number) || hexId;
  const changingLines = (data.changing_lines as number[]) || [];

  const castResult = buildCastResultFromBackend(
    hexId,
    transHexId,
    changingLines,
    data.focus_rule as Parameters<typeof buildCastResultFromBackend>[3]
  );

  const firstMessage: ChatMessage = {
    id: `msg-${Date.now()}`,
    sender: 'assistant',
    content: (data.user_facing_message as string) || '',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    isDuplicateAlert: Boolean(data.is_duplicate),
    evidences: mapEvidences(data.evidences),
  };

  return {
    sessionId: data.session_id as string,
    isCrisis: false,
    isDuplicate: Boolean(data.is_duplicate),
    castResult,
    firstMessage,
    remainingCredits: typeof data.remaining_credits === 'number' ? data.remaining_credits : undefined,
    creditDelta: typeof data.credit_delta === 'number' ? data.credit_delta : undefined,
    operationId: (data.operation_id as string) || undefined,
    operationStatus: (data.operation_status as OperationStatus) || undefined,
    reportData: data.report_data as AnyReportData | undefined,
    reportStatus: data.report_status as 'ready' | 'failed' | 'not_requested' | undefined,
    reportErrorCode: data.report_error_code as string | undefined,
  };
}

/**
 * 실제 백엔드 API 호출: 상담 턴 진행
 * Supabase JWT(Bearer token)를 필수 첨부합니다.
 */
export interface SendConsultationTurnResult {
  replyMessage: ChatMessage;
  isFinal: boolean;
  journal?: JournalSummary;
  remainingCredits?: number;
  creditDelta?: number;
  operationId?: string;
  operationStatus?: OperationStatus;
}

export async function sendConsultationTurnApi(
  sessionId: string,
  userMessage: string,
  turnCount: number,
  castResult: CastResult,
  _userId?: string,
  options: {
    idempotencyKey?: string;
  } = {}
): Promise<SendConsultationTurnResult> {
  const idempotencyKey = options.idempotencyKey || createIdempotencyKey();

  const { data: { session } } = await supabase.auth.getSession();
  let token = session?.access_token;
  if (!token && process.env.NODE_ENV !== 'production') {
    token = 'dev-token';
  }

  if (!token) {
    throw new Error('로그인이 필요한 서비스입니다. 먼저 로그인해 주세요.');
  }

  let res: Response;
  try {
    res = await fetch(`${BACKEND_API_BASE}/api/counsel/turn`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        'Idempotency-Key': idempotencyKey,
      },
      body: JSON.stringify({
        session_id: sessionId,
        user_message: userMessage,
      }),
    });
  } catch (netErr: unknown) {
    const msg = netErr instanceof Error ? netErr.message : '네트워크 통신 오류가 발생했습니다.';
    throw new Error(`상담 서버에 연결할 수 없습니다 (${msg}). 잠시 후 다시 시도해 주세요.`);
  }

  let data: Record<string, unknown>;

  // 202 OPERATION_IN_PROGRESS 수신 시 Bounded Polling 수행
  if (res.status === 202) {
    const progressData = await res.json().catch(() => ({}));
    const operationId = progressData.operation_id;
    if (!operationId) {
      throw new Error('서버에서 작업 식별자(operation_id)를 받지 못했습니다.');
    }

    const completedOp = await pollOperationUntilDone(operationId, token, {
      initialRetryAfterSeconds: progressData.retry_after_seconds,
    });

    if (completedOp.operation_status === 'REJECTED') {
      throw new Error(completedOp.message || '상담 턴 처리가 거부되었습니다.');
    }

    data = (completedOp.result || {}) as Record<string, unknown>;
    data.operation_id = completedOp.operation_id;
    data.operation_status = completedOp.operation_status;
    data.credit_delta = completedOp.credit_delta;
    data.remaining_credits = completedOp.remaining_credits;
  } else if (!res.ok) {
    const parsedErr = await parseHttpErrorResponse(res);
    throw parsedErr;
  } else {
    data = await res.json();
  }

  const hexMeta = HEXAGRAMS_META[castResult.originalHexId];

  let journal: JournalSummary | undefined = undefined;
  if (data.is_final && (data.journal_summary || data.journal_data)) {
    const jData = data.journal_data as Record<string, unknown> | undefined;
    const cardData = jData?.card_data as Record<string, unknown> | undefined;
    const cardPayload = cardData?.card_payload as Record<string, unknown> | undefined;
    const actAction =
      (cardPayload?.client_action_pledge as string) ||
      (jData?.action_items as string) ||
      ((cardData?.psychological_engine as Record<string, unknown> | undefined)?.act_committed_action as string);
    const ahaMoment = cardPayload?.client_aha_moment as string;
    const reframing = cardPayload?.counselor_reframing as string;
    const universeTransition =
      (cardPayload?.universe_transition as string) ||
      (jData?.summary as string) ||
      (data.journal_summary as string);

    const insights: string[] = [];
    if (ahaMoment) {
      insights.push(`내려놓은 아집: ${ahaMoment}`);
    }
    if (reframing) {
      insights.push(`마음의 지지와 격려: ${reframing}`);
    }
    if (insights.length === 0 && (jData?.key_insights || data.journal_summary)) {
      insights.push((jData?.key_insights as string) || (data.journal_summary as string));
    }

    journal = {
      clarifiedQuestion: universeTransition || '주역 괘를 거울삼아 함께 나눈 성찰',
      hexagramSummary: `${hexMeta.fullNameHangul} (${hexMeta.nameHanja}) - ${hexMeta.coreTheme}`,
      keyInsights: insights,
      suggestedAction: actAction || '오늘 나눈 대화의 실마리를 마음에 품고, 조급함 없이 하루를 정돈해 보세요.',
      createdAt: new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' }),
      cardMarkdown: jData?.card_markdown as string | undefined,
      cardData: jData?.card_data as Record<string, unknown> | undefined,
      isCrisis: Boolean(jData?.is_crisis),
    };
  }

  return {
    replyMessage: {
      id: `msg-${Date.now()}`,
      sender: 'assistant',
      content: (data.user_facing_message as string) || '',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      evidences: mapEvidences(data.evidences),
      followupQuestion: data.needs_followup
        ? '마음에 떠오르는 생각이나 더 들여다보고 싶은 부분이 있다면 편안하게 말씀해 주세요.'
        : undefined,
    },
    isFinal: Boolean(data.is_final),
    journal,
    remainingCredits: typeof data.remaining_credits === 'number' ? data.remaining_credits : undefined,
    creditDelta: typeof data.credit_delta === 'number' ? data.credit_delta : undefined,
    operationId: (data.operation_id as string) || undefined,
    operationStatus: (data.operation_status as OperationStatus) || undefined,
  };
}

/**
 * 서버 사이드 EXIF 세척 고화질 래스터화 카드 이미지 다운로드 API
 * CR-claude-007: localStorage/dev-token fallback을 사용하지 않고 Supabase 세션 토큰을 필수로 요구합니다.
 * 미인증 시 서버 호출을 차단하고 즉시 인증 필요 에러를 반환합니다.
 */
export async function exportCardImageApi(sessionId: string): Promise<Blob> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  if (!token) {
    throw new Error('카드 이미지를 생성하려면 로그인이 필요합니다. 로그인 후 다시 시도해 주세요.');
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/counsel/card/export`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ session_id: sessionId }),
  });

  if (!res.ok) {
    throw new Error('서버에서 카드 이미지를 생성하는 데 실패했습니다.');
  }

  return await res.blob();
}

/**
 * AG-1: 법적 동의 및 연령 확인 API
 */
export interface ConsentRecord {
  id?: string;
  terms_version: string;
  privacy_version: string;
  age_confirmed: boolean;
  action?: string;
  created_at?: string;
  recorded_at?: string;
}

export async function postConsentApi(
  termsVersion: string = '2026-09-12',
  privacyVersion: string = '2026-09-12',
  ageConfirmed: boolean = true
): Promise<{ recorded_at: string; terms_version: string; privacy_version: string }> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    throw new Error('동의를 기록하려면 로그인이 필요합니다.');
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/me/consent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      terms_version: termsVersion,
      privacy_version: privacyVersion,
      age_confirmed: ageConfirmed,
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || '동의 기록 저장에 실패했습니다.');
  }

  return await res.json();
}

export async function getConsentApi(): Promise<{ current: ConsentRecord | null }> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    return { current: null };
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/me/consent`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    throw new Error('동의 기록 조회에 실패했습니다.');
  }

  return await res.json();
}

export async function withdrawConsentApi(): Promise<{
  withdrawn_at: string;
  terms_version: string;
  privacy_version: string;
}> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;
  if (!token) {
    throw new Error('동의를 철회하려면 로그인이 필요합니다.');
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/me/consent/withdraw`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || '동의 철회 처리에 실패했습니다.');
  }

  return await res.json();
}

export interface ConsultationRecordItem {
  session_id: string;
  raw_question: string;
  created_at: string | null;
  updated_at: string | null;
  status: string;
  report_status: string;
  topic_category: string | null;
  turn_count: number;
  has_journal: boolean;
  original_hexagram_id?: number | null;
  transformed_hexagram_id?: number | null;
  report_data?: HexagramReportData | null;
}

export interface RecordDetailTurn {
  turn_number: number;
  user_message: string;
  agent_response: string;
  original_hexagram_id?: number | null;
  transformed_hexagram_id?: number | null;
  changing_lines?: number[];
  created_at: string | null;
}

export interface RecordDetailJournal {
  summary: string;
  key_insights: string;
  action_items?: string | null;
  created_at: string | null;
}

export interface ConsultationRecordDetail {
  session_id: string;
  created_at: string | null;
  updated_at: string | null;
  status: string;
  report_status: string;
  raw_question: string;
  clarified_question?: string | null;
  topic_category?: string | null;
  report_data?: HexagramReportData | null;
  turns: RecordDetailTurn[];
  journal?: RecordDetailJournal | null;
}

/**
 * AG-3: 내 상담 기록 열람 및 삭제 API
 */
export async function fetchMyRecordsApi(limit = 20, cursor?: string): Promise<{
  records: ConsultationRecordItem[];
  next_cursor: string | null;
}> {
  const { data: { session } } = await supabase.auth.getSession();
  let token = session?.access_token;
  if (!token && process.env.NODE_ENV !== 'production') {
    token = 'dev-token';
  }
  if (!token) {
    throw new Error('상담 기록을 조회하려면 로그인이 필요합니다.');
  }

  const params = new URLSearchParams();
  params.set('limit', String(limit));
  if (cursor) params.set('cursor', cursor);

  const res = await fetch(`${BACKEND_API_BASE}/api/me/records?${params.toString()}`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    throw new Error('상담 기록 조회에 실패했습니다.');
  }

  return await res.json();
}

export const getRecordsApi = fetchMyRecordsApi;

export async function fetchRecordDetailApi(sessionId: string): Promise<ConsultationRecordDetail> {
  const { data: { session } } = await supabase.auth.getSession();
  let token = session?.access_token;
  if (!token && process.env.NODE_ENV !== 'production') {
    token = 'dev-token';
  }
  if (!token) {
    throw new Error('상담 상세 기록을 조회하려면 로그인이 필요합니다.');
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/me/records/${sessionId}`, {
    method: 'GET',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    if (res.status === 404) throw new Error('상담 기록을 찾을 수 없습니다.');
    throw new Error('상담 상세 기록 조회에 실패했습니다.');
  }

  return await res.json();
}

export const getRecordDetailApi = fetchRecordDetailApi;

export async function deleteRecordApi(sessionId: string): Promise<{
  session_id: string;
  deleted: boolean;
  turns_deleted: number;
  journal_deleted: number;
  operation_snapshots_scrubbed: number;
}> {
  const { data: { session } } = await supabase.auth.getSession();
  let token = session?.access_token;
  if (!token && process.env.NODE_ENV !== 'production') {
    token = 'dev-token';
  }
  if (!token) {
    throw new Error('상담 기록을 삭제하려면 로그인이 필요합니다.');
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/me/records/${sessionId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    if (res.status === 404) throw new Error('삭제할 상담 기록이 존재하지 않거나 권한이 없습니다.');
    throw new Error('상담 기록 삭제에 실패했습니다.');
  }

  return await res.json();
}

/**
 * AG-4: 고객지원 문의 접수 API
 */
export async function submitSupportInquiryApi(payload: {
  category: string;
  email: string;
  message: string;
  order_id?: string;
}): Promise<{
  ticket_no: string;
  status: string;
  created_at: string;
}> {
  const { data: { session } } = await supabase.auth.getSession();
  const token = session?.access_token;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/support/inquiries`, {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || '문의 접수에 실패했습니다.');
  }

  return await res.json();
}

/**
 * 기간별 방문 지표. new + returning 이 unique 와 정확히 일치하지는 않는다 —
 * 같은 기간에 첫 방문과 재방문을 모두 한 사람은 양쪽에 잡힌다.
 */
export interface VisitorPeriodStats {
  visits: number;
  unique_visitors: number;
  new_visitors: number;
  returning_visitors: number;
  revisit_rate_pct: number;
}

/**
 * 운영 대시보드 방문자·재방문 지표 (자체 1st-party 방문 로그 기준).
 * enabled 가 false 이면 reason 만 온다 — 수집 스위치가 꺼져 있다는 뜻이다.
 */
export interface VisitorStats {
  enabled: boolean;
  reason?: string;
  timezone?: string;
  today?: VisitorPeriodStats;
  last_7d?: VisitorPeriodStats;
  last_30d?: VisitorPeriodStats;
  total?: {
    visits: number;
    unique_visitors: number;
    avg_visits_per_visitor: number;
    max_visits_per_visitor?: number;
  };
  revisit_buckets?: Array<{ label: string; visitors: number }>;
  member_visits?: number;
  anonymous_visits?: number;
  trend?: Array<{ date: string; visits: number; unique_visitors: number; new_visitors: number }>;
  top_referrers?: Array<{ host: string; visits: number }>;
  devices?: Array<{ device: string; visits: number }>;
}

/**
 * 방문 1건 기록 (익명 허용).
 *
 * 인증이 없어도 호출된다. 토큰이 있으면 회원 방문으로 집계된다.
 * status 가 'recorded' 가 아니면 호출부는 방문자 식별자를 저장하지 않는다 —
 * 서버 수집이 꺼진 상태에서 브라우저에 식별자만 남기지 않기 위한 계약이다.
 */
export async function postVisitPingApi(
  visitorId: string,
  payload: { path?: string; referrer?: string; device?: string },
  token?: string | null
): Promise<{ status: string; visit_index?: number; is_returning?: boolean }> {
  // 백엔드가 닫혀 있거나(로컬 개발, 배포 중단) 확장 프로그램이 요청을 막으면
  // fetch 자체가 reject 된다. 그 경우까지 여기서 삼킨다 — 통계 ping 하나가
  // 이용자 콘솔에 unhandled rejection 으로 남으면 안 된다.
  try {
    const res = await fetch(`${BACKEND_API_BASE}/api/telemetry/visit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        visitor_id: visitorId,
        path: payload.path ?? null,
        referrer: payload.referrer ?? null,
        device: payload.device ?? null,
      }),
      // 페이지를 떠나도 전송이 끊기지 않게 한다. 진입 직후 이탈하는 방문이
      // 통계에서 빠지면 신규 방문자수가 실제보다 낮게 잡힌다.
      keepalive: true,
    });
    if (!res.ok) {
      return { status: 'error' };
    }
    return await res.json();
  } catch {
    return { status: 'error' };
  }
}

/**
 * 운영자 대시보드 종합 지표 데이터 인터페이스
 */
export interface AdminDashboardData {
  kpi: {
    total_users: number;
    total_sessions: number;
    total_turns: number;
    total_journals: number;
    total_credits_in_circulation: number;
    total_credits_consumed: number;
    budget: {
      daily_cost_usd: number;
      monthly_cost_usd: number;
      daily_limit_usd: number;
      monthly_limit_usd: number;
      daily_remaining_usd: number;
      monthly_remaining_usd: number;
      budget_enabled: boolean;
      total_recorded_calls?: number;
    };
  };
  visitors: VisitorStats;
  users: Array<{
    id: string;
    email: string | null;
    nickname: string | null;
    credit_balance: number;
    session_count: number;
    created_at: string | null;
    updated_at: string | null;
  }>;
  recent_sessions: Array<{
    id: string;
    user_id: string | null;
    user_email: string | null;
    raw_question: string;
    topic_category: string | null;
    status: string;
    turn_count: number;
    has_journal: boolean;
    created_at: string | null;
  }>;
  recent_ledger: Array<{
    id: string;
    user_id: string;
    user_email: string | null;
    amount: number;
    reason: string | null;
    event_type: string | null;
    created_at: string | null;
  }>;
}

/**
 * 운영자 대시보드 지표 조회
 */
export async function fetchAdminDashboardApi(token: string): Promise<AdminDashboardData> {
  const res = await fetch(`${BACKEND_API_BASE}/api/ops/dashboard`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    if (res.status === 404) {
      throw new Error('운영자 권한이 없거나 경로를 찾을 수 없습니다.');
    }
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '관리자 대시보드 데이터를 불러오지 못했습니다.');
  }
  return await res.json();
}

/**
 * 운영자 수동 크레딧 지급
 */
export async function postGrantCreditApi(
  token: string,
  targetUserId: string,
  amount: number,
  reason: string
): Promise<{
  status: string;
  target_user_id: string;
  user_email: string;
  granted_amount: number;
  new_balance: number;
  reason: string;
}> {
  const res = await fetch(`${BACKEND_API_BASE}/api/ops/credits/grant`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      target_user_id: targetUserId,
      amount,
      reason,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '크레딧 지급에 실패했습니다.');
  }
  return await res.json();
}

/**
 * 비회원 무료 괘 도출 및 리포트 조회
 */
export async function previewConsultationApi(question: string): Promise<{
  session_id: string;
  castResult: CastResult;
  report_data?: HexagramReportData | null;
  user_facing_message: string;
  is_crisis: boolean;
  crisis_resources?: Array<{ name: string; contact: string; description: string }>;
}> {
  const res = await fetch(`${BACKEND_API_BASE}/api/counsel/preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ question }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '주역 리포트를 생성하지 못했습니다.');
  }

  const data = await res.json();
  const castResult = buildCastResultFromBackend(
    data.hexagram_id,
    data.transformed_hexagram_id,
    data.changing_lines || [],
    data.focus_rule
  );

  return {
    session_id: data.session_id,
    castResult,
    report_data: data.report_data,
    user_facing_message: data.user_facing_message,
    is_crisis: data.is_crisis,
    crisis_resources: data.crisis_resources,
  };
}

export interface ClaimConsultationResult {
  sessionId: string;
  castResult: CastResult;
  firstMessage: ChatMessage;
  reportData?: HexagramReportData | null;
  remainingCredits?: number;
}

/**
 * 비회원 세션을 본인 계정으로 승계 및 1턴 상담 확정 (10C 차감)
 */
export async function claimAndStartConsultationApi(
  sessionId: string,
  _userId?: string,
  options: {
    idempotencyKey?: string;
  } = {}
): Promise<ClaimConsultationResult> {
  const idempotencyKey = options.idempotencyKey || createIdempotencyKey();

  const { data: { session } } = await supabase.auth.getSession();
  let token = session?.access_token;
  if (!token && process.env.NODE_ENV !== 'production') {
    token = 'dev-token';
  }

  if (!token) {
    throw new Error('로그인이 필요한 서비스입니다. 먼저 로그인해 주세요.');
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/counsel/claim`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({ session_id: sessionId }),
  });

  if (!res.ok) {
    const parsedErr = await parseHttpErrorResponse(res);
    throw parsedErr;
  }

  const data = await res.json();
  const hexId = (data.hexagram_id as number) || 1;
  const transHexId = (data.transformed_hexagram_id as number) || hexId;
  const changingLines = (data.changing_lines as number[]) || [];

  const castResult = buildCastResultFromBackend(
    hexId,
    transHexId,
    changingLines,
    data.focus_rule as Parameters<typeof buildCastResultFromBackend>[3]
  );

  const firstMessage: ChatMessage = {
    id: `msg-${Date.now()}`,
    sender: 'assistant',
    content: (data.user_facing_message as string) || '주역 심층 상담이 연결되었습니다.',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    evidences: mapEvidences(data.evidences),
  };

  return {
    sessionId: (data.session_id as string) || sessionId,
    castResult,
    firstMessage,
    reportData: data.report_data,
    remainingCredits: typeof data.remaining_credits === 'number' ? data.remaining_credits : undefined,
  };
}

/**
 * 회원 탈퇴 및 모든 개인 데이터 영구 파기
 */
export async function deleteMyAccountApi(explicitToken?: string): Promise<{ success: boolean; message: string; auth_account_deleted?: boolean }> {
  let token = explicitToken;
  if (!token) {
    const { data: { session } } = await supabase.auth.getSession();
    token = session?.access_token;
  }
  if (!token && process.env.NODE_ENV !== 'production') {
    token = 'dev-token';
  }
  if (!token) {
    throw new Error('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.');
  }

  const res = await fetch(`${BACKEND_API_BASE}/api/me/account`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || '회원 탈퇴 처리에 실패했습니다.');
  }

  return await res.json();
}

