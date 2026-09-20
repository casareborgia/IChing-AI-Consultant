import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '../..');
const fixturesDir = path.join(rootDir, 'tests/fixtures/report_v2');

// TS 컴파일된 마크다운 렌더러와 이스케이프 함수를 import하거나, 순수 JS 로직을 직접 검증
// frontend/src/components/hexagram/reportMarkdown.ts의 순수 함수와 동등한 JS 모듈 검증
const MD_SPECIAL = ['\\', '`', '*', '_', '[', ']', '|'];

function escapeReportText(text) {
  if (!text) return '';
  let out = String(text).split(/\s+/).filter(Boolean).join(' ');
  out = out.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  for (const ch of MD_SPECIAL) {
    out = out.split(ch).join('\\' + ch);
  }
  return out;
}

function reportSchemaVersion(data) {
  if (!data || typeof data !== 'object') return null;
  const declared = data.schema_version;
  if (declared === undefined || declared === null) return 'legacy';
  if (declared === '2.0') return '2.0';
  return 'unknown';
}

const POSITION_NAMES = {
  1: '초효',
  2: '2효',
  3: '3효',
  4: '4효',
  5: '5효',
  6: '상효',
};

const ROLE_LABELS = {
  primary: '주 근거',
  auxiliary: '보조 근거',
  background: '배경',
  body_use: '체용 참작',
  supplement: '보충 (대상전)',
  annotation: '고전 주석',
};

function getLineLabel(source) {
  if (source.role === 'supplement') return '대상전';
  if (source.line_number === null) return '괘사';
  if (source.line_number === 7) return '용구/용육';
  return `${source.line_number}효`;
}

function renderReportV2Markdown(report) {
  const n = report.narrative;
  const casting = report.academic_details.casting;
  const focus = report.academic_details.focus_rule;
  const academic = report.academic_details;

  const out = [
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

  // Academic details
  out.push('<details>');
  out.push('<summary><b>📜 고전 수리 검증 및 원전 근거 보기</b></summary>');
  out.push('');
  out.push('#### 1. 점서 예식 및 수리 도출');
  out.push('- **점서 예식**: 재삼독(再三瀆) 원칙에 따라 이 세션의 괘는 한 번 도출한 뒤 다시 뽑지 않습니다.');

  const numerals = casting.lines
    .map((l) => `${POSITION_NAMES[l.position] || `${l.position}효`}(${l.value})`)
    .join(' ➔ ');
  out.push(`- **도출 수리**: ${escapeReportText(numerals)}`);
  out.push(
    `- **본괘**: ${escapeReportText(casting.original_name)} (하괘 ${escapeReportText(casting.original_lower_trigram)}, 상괘 ${escapeReportText(casting.original_upper_trigram)})`
  );
  if (casting.has_transformation) {
    out.push(`- **지괘**: ${escapeReportText(casting.transformed_name)}`);
  } else {
    out.push('- **지괘**: 없음 (동효가 없는 불변괘입니다)');
  }

  out.push('');
  out.push('#### 2. 고변점(考變占) 판정 규칙');
  const changingLocStr = casting.changing_lines.length > 0
    ? ` (위치 ${escapeReportText(casting.changing_lines.map((p) => `${p}효`).join(', '))})`
    : ' (불변괘)';
  out.push(`- **변효 개수**: ${focus.changing_count}개${changingLocStr}`);
  out.push(`- **해석 원칙**: ${escapeReportText(focus.description_ko)}`);
  if (focus.body_use_note_ko) {
    out.push(`- **체용 참작**: ${escapeReportText(focus.body_use_note_ko)}`);
  }
  out.push(`- **규칙 판본**: ${escapeReportText(focus.rule_version)}`);

  out.push('');
  out.push('#### 3. 고전 원문 및 번역');
  out.push('');

  for (const source of academic.sources) {
    const roleLabel = ROLE_LABELS[source.role] || source.role;
    if (source.role === 'annotation') {
      out.push(
        `- **[${escapeReportText(ROLE_LABELS.annotation)}] ${escapeReportText(source.annotation_source || '출처 미상')}**`
      );
      out.push(`    - ${escapeReportText(source.annotation)}`);
      continue;
    }
    const head = `- **[${escapeReportText(roleLabel)}] ${escapeReportText(source.hexagram_name)} ${escapeReportText(getLineLabel(source))}**`;
    out.push(head);
    out.push(`    - 원문: ${escapeReportText(source.classical_text)}`);
    if (source.classical_translation) {
      out.push(`    - 번역: ${escapeReportText(source.classical_translation)}`);
    } else {
      out.push('    - 번역: (확인된 번역 없음)');
    }
    if (source.locator) {
      out.push(`    - 출처: ${escapeReportText(source.locator)}`);
    }
  }

  const meta = report.generation_metadata;
  out.push('');
  out.push('#### 4. 생성 정보');
  out.push(`- 생성 시각: ${escapeReportText(meta.generated_at)}`);
  out.push(`- 모델: ${escapeReportText(meta.model ? meta.model : '(미확인)')}`);
  out.push(`- 프롬프트 판본: ${escapeReportText(meta.prompt_version)}`);
  out.push(`- 근거 지문: ${escapeReportText(meta.evidence_snapshot_hash.slice(0, 16))}`);
  out.push('');
  out.push('</details>');
  out.push('');

  return out.join('\n');
}

test('1. 판본 분기 규칙: 2.0, legacy, unknown 분기 검증', () => {
  assert.equal(reportSchemaVersion({ schema_version: '2.0' }), '2.0');
  assert.equal(reportSchemaVersion({}), 'legacy');
  assert.equal(reportSchemaVersion({ schema_version: null }), 'legacy');
  assert.equal(reportSchemaVersion({ schema_version: undefined }), 'legacy');
  assert.equal(reportSchemaVersion({ schema_version: '3.0' }), 'unknown');
  assert.equal(reportSchemaVersion({ schema_version: 'random' }), 'unknown');
  assert.equal(reportSchemaVersion(null), null);
  assert.equal(reportSchemaVersion(undefined), null);
});

test('2. 이스케이프 함수: 줄바꿈 접기, HTML 엔티티(& 우선), 마크다운 인라인 문자', () => {
  // 줄바꿈 공백 접기
  assert.equal(escapeReportText('첫째 줄\n둘째 줄\r\n셋째 줄'), '첫째 줄 둘째 줄 셋째 줄');

  // & 먼저 이스케이프되어 이중 이스케이프 방지
  assert.equal(escapeReportText('A & B < C > D'), 'A &amp; B &lt; C &gt; D');

  // 마크다운 특수문자 이스케이프
  assert.equal(escapeReportText('`코드` *강조* _밑줄_ [링크] |파이프| \\역슬래시'), '\\`코드\\` \\*강조\\* \\_밑줄\\_ \\[링크\\] \\|파이프\\| \\\\역슬래시');
});

test('3. fixture 7종 파일 존재 및 역직렬화 검증', () => {
  const files = [
    'v2_invariant.json',
    'v2_single_changing.json',
    'v2_three_changing.json',
    'v2_multi_changing.json',
    'v2_missing_translation.json',
    'legacy_report.json',
    'report_failed_envelope.json',
  ];

  for (const f of files) {
    const p = path.join(fixturesDir, f);
    assert.ok(fs.existsSync(p), `Fixture file must exist: ${f}`);
    const content = JSON.parse(fs.readFileSync(p, 'utf8'));
    assert.ok(content, `JSON parsed: ${f}`);
  }
});

test('4. 불변괘(v2_invariant.json) 지괘 표기 검증: 본괘 중복 방지', () => {
  const data = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'v2_invariant.json'), 'utf8'));
  assert.equal(data.academic_details.casting.has_transformation, false);
  assert.equal(data.academic_details.casting.transformed_hexagram_id, null);
  assert.equal(data.academic_details.casting.transformed_name, null);

  const md = renderReportV2Markdown(data);
  assert.ok(md.includes('- **지괘**: 없음 (동효가 없는 불변괘입니다)'), '불변괘는 없음으로 표기');
  // 지괘 자리에 본괘 이름 반복 없음
  assert.ok(!md.includes('- **지괘**: 화뢰서합'), '본괘 이름이 지괘 자리에 나오면 안 됨');
});

test('5. 결측 번역(v2_missing_translation.json) 검증: (확인된 번역 없음) 표시', () => {
  const data = JSON.parse(fs.readFileSync(path.join(fixturesDir, 'v2_missing_translation.json'), 'utf8'));
  const missingSrc = data.academic_details.sources.find((s) => s.classical_translation === null && s.role !== 'annotation');
  assert.ok(missingSrc, 'classical_translation이 null인 소스 존재');

  const md = renderReportV2Markdown(data);
  assert.ok(md.includes('- 번역: (확인된 번역 없음)'), '번역 누락 시 안내 문구 출력');
});

test('6. narrative 본문 금지어 규칙 검증: 한자, 괘기호, 치료기법명, 학술용어 부재', () => {
  const v2Files = [
    'v2_invariant.json',
    'v2_single_changing.json',
    'v2_three_changing.json',
    'v2_multi_changing.json',
    'v2_missing_translation.json',
  ];

  const HANJA_REGEX = /[\u4E00-\u9FFF]/;
  const HEX_SYMBOL_REGEX = /[\u4DC0-\u4DFF]/;
  const FORBIDDEN_TERMS = [
    'EFT', 'MBCT', 'CBT', 'ACT', 'DBT',
    '탈융합', '헥사플렉스', '자동조종',
    '부중부정', '재삼독', '체용', '고변점',
  ];

  for (const f of v2Files) {
    const data = JSON.parse(fs.readFileSync(path.join(fixturesDir, f), 'utf8'));
    const n = data.narrative;
    const narrativeTexts = [
      n.headline_metaphor,
      n.emotional_context.validation,
      n.emotional_context.pattern_hypothesis || '',
      n.perspective.thought_observation || '',
      n.perspective.classical_reading,
      n.perspective.applied_reading,
      n.perspective.alternative_perspective,
      n.value_direction.proposed_value || '',
      n.value_direction.rationale,
      ...(n.value_direction.conditions_to_check || []),
      n.micro_action_task.title,
      n.micro_action_task.when,
      ...(n.micro_action_task.steps || []),
      n.micro_action_task.completion_criterion,
      n.micro_action_task.smaller_alternative || '',
    ].join(' ');

    assert.ok(!HANJA_REGEX.test(narrativeTexts), `${f} narrative에 한자가 없어야 함`);
    assert.ok(!HEX_SYMBOL_REGEX.test(narrativeTexts), `${f} narrative에 괘 기호가 없어야 함`);

    for (const term of FORBIDDEN_TERMS) {
      assert.ok(!narrativeTexts.includes(term), `${f} narrative에 금지어 [${term}]가 없어야 함`);
    }
  }
});

test('7. Python 참조 구현(core/report_markdown.py)과의 1:1 마크다운 정합성 검증', () => {
  const testFixture = path.join(fixturesDir, 'v2_single_changing.json');
  const data = JSON.parse(fs.readFileSync(testFixture, 'utf8'));

  // Python 참조 출력 실행 (.venv 파이썬 우선 사용)
  const venvPy = path.join(rootDir, '.venv/bin/python3');
  const pythonBin = fs.existsSync(venvPy) ? venvPy : 'python3';
  const pythonCmd = `"${pythonBin}" -c "import json, sys; from core.report_markdown import render_markdown_from_dict; print(render_markdown_from_dict(json.load(open('${testFixture}'))))"`;
  const pyOutput = execSync(pythonCmd, { cwd: rootDir, encoding: 'utf8' });

  const jsOutput = renderReportV2Markdown(data);

  assert.equal(jsOutput.trim(), pyOutput.trim(), 'JS 렌더러와 Python 참조 렌더러의 출력이 100% 동일해야 함');
});
