export interface HexagramMeta {
  id: number;
  nameHanja: string;
  nameHangul: string;
  fullNameHangul: string; // 예: 수천수
  unicodeSymbol: string;
  upperTrigram: string; // 예: 坎 (水)
  lowerTrigram: string; // 예: 乾 (天)
  natureSummary: string; // 자연 상징: "하늘 위에 구름이 가득 찬 상"
  coreTheme: string; // 핵심 주제: "기다림, 내실 다지기, 때를 살핌"
  binary: string; // 초효 -> 상효 6자리 이진코드
}

export type LineValue = 6 | 7 | 8 | 9; // 6: 노음(동효), 7: 소양, 8: 소음, 9: 노양(동효)

export interface LineInfo {
  position: number; // 1 (초효) ~ 6 (상효)
  value: LineValue;
  isYang: boolean;
  isChanging: boolean;
}

export interface CastResult {
  originalHexId: number;
  transformedHexId: number;
  lines: LineInfo[];
  changingPositions: number[]; // 1-based index (e.g. [3, 5])
}

export type ConsultationStep =
  | 'intake'          // 고민 입력
  | 'casting'         // 괘 도출 애니메이션
  | 'revealed'        // 괘 결과 확인 및 해석 안내
  | 'counseling'      // 심층 질의응답 (멀티턴)
  | 'safety_redirect' // 위기 핫라인 안내
  | 'completed';      // 상담 종료 및 저널 요약

export interface GroundEvidence {
  sourceType: 'jeongjeon' | 'benui' | 'guasa' | 'sosang';
  sourceTitle: string; // 예: "정전(程傳) 괘사 해설", "주자 본의(本義)"
  content: string;
  quote?: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  followupQuestion?: string | null;
  evidences?: GroundEvidence[];
  isDuplicateAlert?: boolean;
}

export interface JournalSummary {
  clarifiedQuestion: string;
  hexagramSummary: string;
  keyInsights: string[];
  suggestedAction: string;
  createdAt: string;
}
