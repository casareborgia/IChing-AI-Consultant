import { CastResult, ChatMessage, JournalSummary, LineInfo, LineValue } from '../types/iching';
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

/**
 * 실제 백엔드 API 호출: 상담 시작 (안전 스크리닝 -> 접수 -> 괘 도출 -> 1턴 응답)
 */
export async function startConsultationApi(question: string): Promise<{
  sessionId: string;
  isCrisis: boolean;
  isDuplicate: boolean;
  castResult?: CastResult;
  firstMessage?: ChatMessage;
}> {
  try {
    const res = await fetch(`${BACKEND_API_BASE}/api/counsel/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question,
      }),
    });

    if (!res.ok) {
      throw new Error(`서버 응답 오류: ${res.status}`);
    }

    const data = await res.json();

    if (data.is_crisis || data.safety_category === 'BLOCK_CRISIS') {
      return {
        sessionId: data.session_id || `crisis-${Date.now()}`,
        isCrisis: true,
        isDuplicate: false,
      };
    }

    const hexId = data.hexagram_id || 1;
    const transHexId = data.transformed_hexagram_id || hexId;
    const changingLines = data.changing_lines || [];

    const castResult = buildCastResultFromBackend(hexId, transHexId, changingLines, data.focus_rule);
    const hexMeta = HEXAGRAMS_META[hexId];

    const firstMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      sender: 'assistant',
      content: data.user_facing_message,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      isDuplicateAlert: data.is_duplicate,
      evidences: [
        {
          sourceType: 'guasa',
          sourceTitle: `『주역』 ${hexMeta.fullNameHangul} 괘사`,
          content: `${hexMeta.fullNameHangul} (${hexMeta.nameHanja}) - ${hexMeta.natureSummary}`,
        },
        {
          sourceType: 'jeongjeon',
          sourceTitle: '정전(程傳) 및 본의(本義) 주석',
          content: `${hexMeta.coreTheme}의 관점에서 지금 상황의 중심을 살핍니다.`,
        },
      ],
    };

    return {
      sessionId: data.session_id,
      isCrisis: false,
      isDuplicate: data.is_duplicate,
      castResult,
      firstMessage,
    };
  } catch (error) {
    console.error('백엔드 API 호출 실패:', error);
    throw error;
  }
}

/**
 * 실제 백엔드 API 호출: 상담 턴 진행
 */
export async function sendConsultationTurnApi(
  sessionId: string,
  userMessage: string,
  turnCount: number,
  castResult: CastResult
): Promise<{
  replyMessage: ChatMessage;
  isFinal: boolean;
  journal?: JournalSummary;
}> {
  try {
    const res = await fetch(`${BACKEND_API_BASE}/api/counsel/turn`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: sessionId,
        user_message: userMessage,
      }),
    });

    if (!res.ok) {
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
