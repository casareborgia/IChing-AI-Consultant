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

export type BodyUseType = 'EMPHASIZE_ORIGINAL' | 'EMPHASIZE_TRANSFORMED' | 'STANDARD';

export interface FocusRuleInfo {
  focusType: string;
  targetHexagramType: 'ORIGINAL' | 'TRANSFORMED' | 'BOTH';
  targetLineNumbers: number[];
  descriptionKo: string;
  bodyUseType?: BodyUseType;
  bodyUseNoteKo?: string | null;
}

export interface CastResult {
  originalHexId: number;
  transformedHexId: number;
  lines: LineInfo[];
  changingPositions: number[]; // 1-based index (e.g. [3, 5])
  focusRule?: FocusRuleInfo;
}

export type ConsultationStep =
  | 'intake'          // 고민 입력
  | 'casting'         // 괘 도출 애니메이션
  | 'revealed'        // 괘 결과 확인 및 안내
  | 'report'          // 괘 해석 리포트 (표준 마크다운 UI 템플릿)
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

export interface LineCastingItem {
  position: number;
  name: string;
  value: number;
  line_type_ko: string;
  symbol: string;
  is_changing: boolean;
  note: string;
}

export interface SectionItemSchema {
  title: string;
  target_name: string;
  hanja_text?: string | null;
  interpretation: string;
}

export interface HexagramReportData {
  question_setting: {
    question: string;
    mindset_rule: string;
  };
  hexagram_casting: {
    lines: LineCastingItem[];
    original_hex_id: number;
    original_name_full: string;
    original_name_hanja: string;
    original_upper_trigram: string;
    original_lower_trigram: string;
    original_summary: string;
    has_transformation: boolean;
    transformed_hex_id?: number | null;
    transformed_name_full?: string | null;
    transformed_name_hanja?: string | null;
    transformed_summary?: string | null;
  };
  focus_and_body_use: {
    changing_count: number;
    rule_description: string;
    primary_target_name: string;
    body_use_flow: string;
  };
  section1_diagnosis: SectionItemSchema;
  section2_action: SectionItemSchema;
  section3_warning: SectionItemSchema;
  section4_future: SectionItemSchema;
  final_summary: string;
}

export interface JournalSummary {
  clarifiedQuestion: string;
  hexagramSummary: string;
  keyInsights: string[];
  suggestedAction: string;
  createdAt: string;
  cardMarkdown?: string;
  cardData?: Record<string, unknown>;
  isCrisis?: boolean;
}

// ==========================================
// 점괘 사전 분석 리포트 v2 (PreCounselingReportV2) 계약
// 확정 JSON Schema: schemas/json/pre_counseling_report_v2.schema.json
// ==========================================

export type ReportSchemaVersion = 'legacy' | '2.0' | 'unknown';

export function reportSchemaVersion(data: unknown): ReportSchemaVersion | null {
  if (!data || typeof data !== 'object') return null;
  const declared = (data as { schema_version?: unknown }).schema_version;
  if (declared === undefined || declared === null) return 'legacy';
  if (declared === '2.0') return '2.0';
  return 'unknown';
}

export type ReportSourceRole =
  | 'primary'      // 초점 규칙이 지목한 주 근거
  | 'auxiliary'    // 함께 보는 보조 근거
  | 'background'   // 배경 (효사가 주 근거일 때의 본괘 괘사)
  | 'body_use'     // 체용 참작 — 근거를 고르지 않고 무게만 보탠다
  | 'supplement'   // 대상전 등 보충. 주 근거가 아니다
  | 'annotation';  // 검색된 고전 주석

export interface ReportSource {
  id: string;                          // /^E\d{1,3}$/
  role: ReportSourceRole;
  hexagram_id: number;                 // 1..64
  hexagram_name: string;
  line_number: number | null;          // 1..6, 7 = 용구/용육, null = 괘사
  classical_text: string;              // 원문. 항상 있다
  classical_translation: string | null;// 없으면 null — 지어내 채우지 말 것
  annotation: string | null;           // role === 'annotation'일 때의 본문
  annotation_source: string | null;
  locator: string | null;              // 확인된 원전 위치. 불명이면 null
}

export interface ReportUserFact {
  id: string;                          // /^U\d{1,3}$/
  text: string;                        // 사용자가 실제로 쓴 문장의 발췌
}

export interface ReportCastingLine {
  position: number;                    // 1..6 (1 = 초효, 6 = 상효)
  value: 6 | 7 | 8 | 9;
  line_type_ko: string;                // 노음 | 소양 | 소음 | 노양
  is_changing: boolean;
}

export interface ReportCasting {
  lines: ReportCastingLine[];          // 정확히 6개, position 오름차순
  original_hexagram_id: number;
  original_name: string;
  original_lower_trigram: string;      // 예: "진(우레)"
  original_upper_trigram: string;      // 예: "리(불)"
  changing_lines: number[];            // 없으면 []
  has_transformation: boolean;
  transformed_hexagram_id: number | null;  // 불변괘면 null
  transformed_name: string | null;         // 불변괘면 null
}

export interface ReportFocusRule {
  changing_count: number;              // 0..6
  focus_type: string;                  // §3 표 참조
  target_hexagram_type: 'ORIGINAL' | 'TRANSFORMED' | 'BOTH';
  target_line_numbers: number[];
  description_ko: string;
  body_use_type: 'STANDARD' | 'EMPHASIZE_ORIGINAL' | 'EMPHASIZE_TRANSFORMED';
  body_use_note_ko: string | null;
  rule_version: string;
}

export interface ReportEmotionalContext {
  validation: string;                  // 10..800
  pattern_hypothesis: string | null;   // ..500 — **가설이다. 사실로 표시하지 말 것**
  user_fact_refs: string[];            // UserFact.id 참조, 최대 10
}

export interface ReportPerspective {
  thought_observation: string | null;  // ..500
  classical_reading: string;           // 10..500 — 고전이 말하는 바
  applied_reading: string;             // 10..800 — 이번 사연에 옮기면
  alternative_perspective: string;     // 10..800
  evidence_refs: string[];             // 1..10, ReportSource.id 참조
}

export interface ReportValueDirection {
  proposed_value: string | null;       // ..200
  rationale: string;                   // 10..800
  conditions_to_check: string[];       // 1..5, 각 항목 ..200
  evidence_refs: string[];             // 1..10
}

export interface ReportMicroActionTask {
  title: string;                       // 2..100
  duration_minutes: number;            // 1..15 (10이 기본 제안이지 고정값 아님)
  when: string;                        // 2..200
  steps: string[];                     // 1..3, 각 항목 ..200
  completion_criterion: string;        // 5..200
  smaller_alternative: string | null;  // ..200
}

export interface ReportNarrative {
  headline_metaphor: string;           // 5..200
  emotional_context: ReportEmotionalContext;
  perspective: ReportPerspective;
  value_direction: ReportValueDirection;
  micro_action_task: ReportMicroActionTask;
}

export interface ReportAcademicDetails {
  casting: ReportCasting;
  focus_rule: ReportFocusRule;
  sources: ReportSource[];             // 1..30
  user_facts: ReportUserFact[];        // 0..30
}

export interface ReportCounselingHandoff {
  working_hypotheses: string[];        // 0..5
  unconfirmed_points: string[];        // 0..5
  suggested_action_title: string;      // micro_action_task.title과 항상 같다
  opening_question: string;            // 5..200
}

export interface ReportGenerationMetadata {
  generated_at: string;                // 타임존 포함 ISO-8601
  provider: string | null;             // 미확인이면 null
  model: string | null;                // 미확인이면 null
  prompt_version: string;
  rule_version: string;
  evidence_snapshot_hash: string;      // sha256 hex
  repair_count: 0 | 1;
}

export interface PreCounselingReportV2 {
  schema_version: '2.0';
  report_id: string;                   // UUID v4
  session_id: string;                  // 응답의 session_id와 같다
  narrative: ReportNarrative;
  academic_details: ReportAcademicDetails;
  counseling_handoff: ReportCounselingHandoff;
  generation_metadata: ReportGenerationMetadata;
}

export type AnyReportData = HexagramReportData | PreCounselingReportV2;

