import { CastResult, ChatMessage, GroundEvidence, JournalSummary, LineInfo, LineValue } from '../types/iching';
import { HEXAGRAMS_META, HEXAGRAM_ID_TO_BINARY } from '../data/hexagramsData';

const BACKEND_API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8008';

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

import { supabase } from './supabaseClient';

/**
 * 실제 백엔드 API 호출: 상담 시작 (안전 스크리닝 -> 접수 -> 괘 도출 -> 1턴 응답)
 * Supabase JWT(Bearer token)를 필수 첨부합니다.
 */
export async function startConsultationApi(
  question: string,
  _userId?: string
): Promise<{
  sessionId: string;
  isCrisis: boolean;
  crisisResources?: CrisisResourceItem[];
  isDuplicate: boolean;
  castResult?: CastResult;
  firstMessage?: ChatMessage;
  remainingCredits?: number;
}> {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;

    if (!token) {
      throw new Error('로그인이 필요한 서비스입니다. 먼저 로그인해 주세요.');
    }

    const res = await fetch(`${BACKEND_API_BASE}/api/counsel/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        question,
      }),
    });

    if (!res.ok) {
      if (res.status === 401) {
        throw new Error('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.');
      }
      if (res.status === 402) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || '크레딧이 부족합니다. 충전 후 이용해 주세요.');
      }
      throw new Error(`서버 응답 오류: ${res.status}`);
    }

    const data = await res.json();

    if (data.is_crisis) {
      return {
        sessionId: data.session_id || `crisis-${Date.now()}`,
        isCrisis: true,
        crisisResources: data.crisis_resources || [],
        isDuplicate: false,
        remainingCredits: data.remaining_credits,
      };
    }

    const hexId = data.hexagram_id || 1;
    const transHexId = data.transformed_hexagram_id || hexId;
    const changingLines = data.changing_lines || [];

    const castResult = buildCastResultFromBackend(hexId, transHexId, changingLines, data.focus_rule);

    const firstMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'assistant',
      content: data.user_facing_message,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isDuplicateAlert: data.is_duplicate,
      evidences: mapEvidences(data.evidences),
    };

    return {
      sessionId: data.session_id,
      isCrisis: false,
      isDuplicate: data.is_duplicate,
      castResult,
      firstMessage,
      remainingCredits: data.remaining_credits,
    };

  } catch (error) {
    console.error('백엔드 API 호출 실패:', error);
    throw error;
  }
}

/**
 * 실제 백엔드 API 호출: 상담 턴 진행
 * Supabase JWT(Bearer token)를 필수 첨부합니다.
 */
export async function sendConsultationTurnApi(
  sessionId: string,
  userMessage: string,
  turnCount: number,
  castResult: CastResult,
  _userId?: string
): Promise<{
  replyMessage: ChatMessage;
  isFinal: boolean;
  journal?: JournalSummary;
}> {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    const token = session?.access_token;

    if (!token) {
      throw new Error('로그인이 필요한 서비스입니다. 먼저 로그인해 주세요.');
    }

    const res = await fetch(`${BACKEND_API_BASE}/api/counsel/turn`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        session_id: sessionId,
        user_message: userMessage,
      }),
    });

    if (!res.ok) {
      if (res.status === 401) {
        throw new Error('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.');
      }
      if (res.status === 403) {
        throw new Error('세션 접근 권한이 없습니다.');
      }
      throw new Error(`상담 턴 응답 오류: ${res.status}`);
    }

    const data = await res.json();
    const hexMeta = HEXAGRAMS_META[castResult.originalHexId];

    let journal: JournalSummary | undefined = undefined;
    if (data.is_final && data.journal_summary) {
      journal = {
        clarifiedQuestion: '주역 괘를 거울삼아 함께 나눈 성찰',
        hexagramSummary: `${hexMeta.fullNameHangul} (${hexMeta.nameHanja}) - ${hexMeta.coreTheme}`,
        keyInsights: [data.journal_summary],
        suggestedAction: '오늘 나눈 대화의 실마리를 마음에 품고, 조급함 없이 하루를 정돈해 보세요.',
        createdAt: new Date().toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' }),
      };
    }

    return {
      replyMessage: {
        id: `msg-${Date.now()}`,
        sender: 'assistant',
        content: data.user_facing_message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        evidences: mapEvidences(data.evidences),
        followupQuestion: data.needs_followup ? '마음에 떠오르는 생각이나 더 들여다보고 싶은 부분이 있다면 편안하게 말씀해 주세요.' : undefined,
      },
      isFinal: data.is_final,
      journal,
    };
  } catch (error) {
    console.error('상담 턴 처리 실패:', error);
    throw error;
  }
}
