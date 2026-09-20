import {
  PreCounselingReportV2,
  ReportSource,
  ReportSourceRole,
} from '../../types/iching';

const MD_SPECIAL = ['\\', '`', '*', '_', '[', ']', '|'];

/**
 * 본문에 넣어도 마크다운/HTML 구조를 바꾸지 못하게 이스케이프한다.
 * 인계 문서 §5 및 core/report_markdown.py와 100% 동일한 순수 함수.
 */
export function escapeReportText(text: string | null | undefined): string {
  if (!text) return '';
  // 1. 줄바꿈을 공백으로 접는다 — 값 하나가 새 블록(제목·목록·표)을 열 수 없게.
  let out = String(text).split(/\s+/).filter(Boolean).join(' ');
  // 2. HTML 특수문자. **`&`를 먼저** 바꾼다 (나중에 만든 엔티티가 다시 바뀌지 않게).
  out = out.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  // 3. 마크다운 인라인 특수문자.
  for (const ch of MD_SPECIAL) {
    out = out.split(ch).join('\\' + ch);
  }
  return out;
}

const POSITION_NAMES: Record<number, string> = {
  1: '초효',
  2: '2효',
  3: '3효',
  4: '4효',
  5: '5효',
  6: '상효',
};

const ROLE_LABELS: Record<ReportSourceRole, string> = {
  primary: '주 근거',
  auxiliary: '보조 근거',
  background: '배경',
  body_use: '체용 참작',
  supplement: '보충 (대상전)',
  annotation: '고전 주석',
};

function getLineLabel(source: ReportSource): string {
  if (source.role === 'supplement') {
    // 대상전을 "괘사"라고 부르면 보충이 주 근거처럼 읽힌다.
    return '대상전';
  }
  if (source.line_number === null) {
    return '괘사';
  }
  if (source.line_number === 7) {
    return '용구/용육';
  }
  return `${source.line_number}효`;
}

function buildAcademicBlock(report: PreCounselingReportV2): string[] {
  const academic = report.academic_details;
  const casting = academic.casting;
  const focus = academic.focus_rule;

  const lines: string[] = [
    '<details>',
    '<summary><b>📜 고전 수리 검증 및 원전 근거 보기</b></summary>',
    '',
    '#### 1. 점서 예식 및 수리 도출',
    '- **점서 예식**: 재삼독(再三瀆) 원칙에 따라 이 세션의 괘는 한 번 도출한 뒤 다시 뽑지 않습니다.',
  ];

  const numerals = casting.lines
    .map((l) => `${POSITION_NAMES[l.position] || `${l.position}효`}(${l.value})`)
    .join(' ➔ ');
  lines.push(`- **도출 수리**: ${escapeReportText(numerals)}`);
  lines.push(
    `- **본괘**: ${escapeReportText(casting.original_name)} (하괘 ${escapeReportText(casting.original_lower_trigram)}, 상괘 ${escapeReportText(casting.original_upper_trigram)})`
  );
  if (casting.has_transformation) {
    lines.push(`- **지괘**: ${escapeReportText(casting.transformed_name)}`);
  } else {
    lines.push('- **지괘**: 없음 (동효가 없는 불변괘입니다)');
  }

  lines.push('');
  lines.push('#### 2. 고변점(考變占) 판정 규칙');
  const changingLocStr = casting.changing_lines.length > 0
    ? ` (위치 ${escapeReportText(casting.changing_lines.map((p) => `${p}효`).join(', '))})`
    : ' (불변괘)';
  lines.push(`- **변효 개수**: ${focus.changing_count}개${changingLocStr}`);
  lines.push(`- **해석 원칙**: ${escapeReportText(focus.description_ko)}`);
  if (focus.body_use_note_ko) {
    lines.push(`- **체용 참작**: ${escapeReportText(focus.body_use_note_ko)}`);
  }
  lines.push(`- **규칙 판본**: ${escapeReportText(focus.rule_version)}`);

  lines.push('');
  lines.push('#### 3. 고전 원문 및 번역');
  lines.push('');

  for (const source of academic.sources) {
    const roleLabel = ROLE_LABELS[source.role] || source.role;
    if (source.role === 'annotation') {
      lines.push(
        `- **[${escapeReportText(ROLE_LABELS.annotation)}] ${escapeReportText(source.annotation_source || '출처 미상')}**`
      );
      lines.push(`    - ${escapeReportText(source.annotation)}`);
      continue;
    }
    const head = `- **[${escapeReportText(roleLabel)}] ${escapeReportText(source.hexagram_name)} ${escapeReportText(getLineLabel(source))}**`;
    lines.push(head);
    lines.push(`    - 원문: ${escapeReportText(source.classical_text)}`);
    if (source.classical_translation) {
      lines.push(`    - 번역: ${escapeReportText(source.classical_translation)}`);
    } else {
      // 없는 번역을 지어내지 않는다. 누락은 누락으로 보인다.
      lines.push('    - 번역: (확인된 번역 없음)');
    }
    if (source.locator) {
      lines.push(`    - 출처: ${escapeReportText(source.locator)}`);
    }
  }

  const meta = report.generation_metadata;
  lines.push('');
  lines.push('#### 4. 생성 정보');
  lines.push(`- 생성 시각: ${escapeReportText(meta.generated_at)}`);
  lines.push(`- 모델: ${escapeReportText(meta.model ? meta.model : '(미확인)')}`);
  lines.push(`- 프롬프트 판본: ${escapeReportText(meta.prompt_version)}`);
  lines.push(`- 근거 지문: ${escapeReportText(meta.evidence_snapshot_hash.slice(0, 16))}`);
  lines.push('');
  lines.push('</details>');

  return lines;
}

/**
 * PreCounselingReportV2 전체를 마크다운 문자열로 렌더링한다.
 * core/report_markdown.py의 render_markdown과 정확히 일치.
 */
export function renderReportV2Markdown(report: PreCounselingReportV2): string {
  const n = report.narrative;
  const casting = report.academic_details.casting;

  const out: string[] = [
    '# 💡 오늘 주역이 당신에게 건네는 통찰',
    '',
    `> **${escapeReportText(n.headline_metaphor)}**`,
    '',
    '---',
    '',
    `### 1. 당신이 지나가는 계절의 이름 (본괘: ${escapeReportText(casting.original_name)})`,
    '',
    escapeReportText(n.emotional_context.validation),
  ];

  if (n.emotional_context.pattern_hypothesis) {
    out.push('');
    out.push(`*함께 살펴볼 가설입니다 — ${escapeReportText(n.emotional_context.pattern_hypothesis)}*`);
  }

  out.push('');
  out.push('---');
  out.push('');
  out.push('### 2. 생각의 덫에서 벗어나기');
  out.push('');
  if (n.perspective.thought_observation) {
    out.push(escapeReportText(n.perspective.thought_observation));
    out.push('');
  }
  out.push(escapeReportText(n.perspective.classical_reading));
  out.push('');
  out.push(escapeReportText(n.perspective.applied_reading));
  out.push('');
  out.push(escapeReportText(n.perspective.alternative_perspective));

  out.push('');
  out.push('---');
  out.push('');
  out.push('### 3. 나아갈 삶의 가치와 경고등');
  out.push('');
  if (n.value_direction.proposed_value) {
    out.push(`**지켜볼 가치**: ${escapeReportText(n.value_direction.proposed_value)}`);
    out.push('');
  }
  out.push(escapeReportText(n.value_direction.rationale));
  out.push('');
  out.push('**선택할 때 점검할 조건**');
  out.push('');
  for (const c of n.value_direction.conditions_to_check) {
    out.push(`- ${escapeReportText(c)}`);
  }

  const task = n.micro_action_task;
  out.push('');
  out.push('---');
  out.push('');
  out.push(`### 4. 오늘 나를 구하는 ${task.duration_minutes}분 행동`);
  out.push('');
  out.push(`🎯 **${escapeReportText(task.title)}**`);
  out.push('');
  out.push(`- 언제: ${escapeReportText(task.when)}`);
  task.steps.forEach((step, idx) => {
    out.push(`- ${idx + 1}. ${escapeReportText(step)}`);
  });
  out.push(`- 끝난 것으로 볼 기준: ${escapeReportText(task.completion_criterion)}`);
  if (task.smaller_alternative) {
    out.push(`- 더 작게 하려면: ${escapeReportText(task.smaller_alternative)}`);
  }
  out.push('');
  out.push('*제안입니다. 하실지는 직접 정하시면 됩니다.*');

  out.push('');
  out.push('---');
  out.push('');
  out.push(...buildAcademicBlock(report));
  out.push('');

  return out.join('\n');
}
