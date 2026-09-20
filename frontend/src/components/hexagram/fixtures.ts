// Auto-generated fixtures for client testing & verification
import { PreCounselingReportV2, HexagramReportData, AnyReportData } from '../../types/iching';

export const FIXTURE_V2_INVARIANT = {
  "academic_details": {
    "casting": {
      "changing_lines": [],
      "has_transformation": false,
      "lines": [
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 1,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 2,
          "value": 8
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 3,
          "value": 8
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 4,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 5,
          "value": 8
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 6,
          "value": 7
        }
      ],
      "original_hexagram_id": 21,
      "original_lower_trigram": "진(우레)",
      "original_name": "화뢰서합",
      "original_upper_trigram": "리(불)",
      "transformed_hexagram_id": null,
      "transformed_name": null
    },
    "focus_rule": {
      "body_use_note_ko": null,
      "body_use_type": "STANDARD",
      "changing_count": 0,
      "description_ko": "변효가 없으므로 본괘의 괘사(卦辭)를 주 해석으로 삼습니다.",
      "focus_type": "ORIGINAL_JUDGMENT",
      "rule_version": "zhuxi-gobyeonjeom-2026-08-30",
      "target_hexagram_type": "ORIGINAL",
      "target_line_numbers": []
    },
    "sources": [
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "噬嗑 亨 利用獄",
        "classical_translation": "서합은 형통하니, 옥사를 씀이 이롭다.",
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E1",
        "line_number": null,
        "locator": null,
        "role": "primary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "象曰 雷電噬嗑 先王以 明罰勅法",
        "classical_translation": "우레와 번개가 서합이니, 선왕이 이를 본받아 형벌을 밝히고 법령을 정돈하였다.",
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E2",
        "line_number": null,
        "locator": null,
        "role": "supplement"
      },
      {
        "annotation": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "annotation_source": "정전(程傳)",
        "classical_text": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "classical_translation": null,
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E3",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "annotation_source": "본의(本義)",
        "classical_text": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "classical_translation": null,
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E4",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      }
    ],
    "user_facts": [
      {
        "id": "U1",
        "text": "요즘 일이 막혀 있는 느낌입니다."
      },
      {
        "id": "U2",
        "text": "어디서부터 손을 대야 할까요?"
      }
    ]
  },
  "counseling_handoff": {
    "opening_question": "지금 걸려 있는 것 가운데 먼저 말씀하고 싶은 것은 무엇인가요?",
    "suggested_action_title": "걸린 것 하나만 적어 보기",
    "unconfirmed_points": [
      "실제로 조정할 수 있는 범위가 어디까지인지 아직 모릅니다."
    ],
    "working_hypotheses": [
      "한 번에 해결하려는 부담이 시작을 늦추고 있는지"
    ]
  },
  "generation_metadata": {
    "evidence_snapshot_hash": "cc9ab1bd575d3af165dcd891f8e9f9e2e299080579f738153a5ba45cbbf308a4",
    "generated_at": "2026-09-12T04:30:00+00:00",
    "model": "stub-model",
    "prompt_version": "v2.0.0+c3cd72c8",
    "provider": null,
    "repair_count": 0,
    "rule_version": "zhuxi-gobyeonjeom-2026-08-30"
  },
  "narrative": {
    "emotional_context": {
      "pattern_hypothesis": "한 번에 전부 해결하려다 손을 못 대는 흐름이 반복되는지 함께 살펴보면 좋겠습니다.",
      "user_fact_refs": [
        "U1"
      ],
      "validation": "말씀하신 상황에서 답답함이 쌓이는 것은 자연스러운 일입니다. 당장 풀리지 않는 일 앞에서 마음이 무거워지셨을 것 같습니다."
    },
    "headline_metaphor": "단단한 것을 한 번에 삼키려 하지 않고, 씹어 넘길 만큼만 떼어내는 자리입니다.",
    "micro_action_task": {
      "completion_criterion": "표시한 항목이 하나 생기면 끝난 것으로 봅니다.",
      "duration_minutes": 10,
      "smaller_alternative": "적기 어려우면 소리 내어 한 가지만 말해 봅니다.",
      "steps": [
        "지금 마음에 걸리는 일을 떠오르는 대로 적습니다.",
        "그중 가장 작아 보이는 것 하나에 표시합니다."
      ],
      "title": "걸린 것 하나만 적어 보기",
      "when": "오늘 중 조용히 앉을 수 있는 때"
    },
    "perspective": {
      "alternative_perspective": "막혀 있다는 느낌이 능력의 문제가 아니라 순서의 문제일 수 있다는 각도에서 볼 수도 있습니다.",
      "applied_reading": "이번 사연에 옮기면, 전부를 한꺼번에 처리하기보다 걸려 있는 것 하나를 먼저 떼어내는 쪽에 가깝습니다.",
      "classical_reading": "고전은 턱 사이에 낀 것을 깨물어 없애야 비로소 위아래가 맞물린다고 말합니다.",
      "evidence_refs": [
        "E1"
      ],
      "thought_observation": "지금 떠오르는 생각 가운데는 사실이 아니라 지나가는 걱정도 섞여 있을 수 있습니다."
    },
    "value_direction": {
      "conditions_to_check": [
        "지금 걸려 있는 것 가운데 오늘 손댈 수 있는 것이 무엇인지",
        "나누어 하는 방식이 이 상황에서 실제로 가능한지"
      ],
      "evidence_refs": [
        "E1"
      ],
      "proposed_value": "감당할 수 있는 크기로 나누어 다루기",
      "rationale": "한 번에 끝내려는 마음이 클수록 시작이 늦어지는 흐름이 있습니다. 작은 단위로 나누면 손을 댈 자리가 생깁니다."
    }
  },
  "report_id": "00000000-0000-4000-8000-000000000001",
  "schema_version": "2.0",
  "session_id": "fixture-session-0001"
};

export const FIXTURE_V2_SINGLE_CHANGING = {
  "academic_details": {
    "casting": {
      "changing_lines": [
        1
      ],
      "has_transformation": true,
      "lines": [
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 1,
          "value": 9
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 2,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 3,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 4,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 5,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 6,
          "value": 7
        }
      ],
      "original_hexagram_id": 1,
      "original_lower_trigram": "건(하늘)",
      "original_name": "제1괘",
      "original_upper_trigram": "건(하늘)",
      "transformed_hexagram_id": 44,
      "transformed_name": "제44괘"
    },
    "focus_rule": {
      "body_use_note_ko": null,
      "body_use_type": "STANDARD",
      "changing_count": 1,
      "description_ko": "1개의 변효가 있으므로 본괘 1효의 효사(爻辭)를 주 해석으로 삼습니다.",
      "focus_type": "SINGLE_LINE_STATEMENT",
      "rule_version": "zhuxi-gobyeonjeom-2026-08-30",
      "target_hexagram_type": "ORIGINAL",
      "target_line_numbers": [
        1
      ]
    },
    "sources": [
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "爻辭原文1-1",
        "classical_translation": "제1괘 1효의 효사 번역입니다.",
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E1",
        "line_number": 1,
        "locator": null,
        "role": "primary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "卦辭原文1",
        "classical_translation": "제1괘의 괘사 번역입니다.",
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E2",
        "line_number": null,
        "locator": null,
        "role": "background"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "象曰 大象原文1",
        "classical_translation": "제1괘 대상전 번역입니다.",
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E3",
        "line_number": null,
        "locator": null,
        "role": "supplement"
      },
      {
        "annotation": "그 자리에서 마땅함을 얻으면 허물이 없다고 하였다.",
        "annotation_source": "정전(程傳) 효사 주석",
        "classical_text": "그 자리에서 마땅함을 얻으면 허물이 없다고 하였다.",
        "classical_translation": null,
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E4",
        "line_number": 1,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "annotation_source": "정전(程傳)",
        "classical_text": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "classical_translation": null,
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E5",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "annotation_source": "본의(本義)",
        "classical_text": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "classical_translation": null,
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E6",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      }
    ],
    "user_facts": [
      {
        "id": "U1",
        "text": "요즘 일이 막혀 있는 느낌입니다."
      },
      {
        "id": "U2",
        "text": "어디서부터 손을 대야 할까요?"
      }
    ]
  },
  "counseling_handoff": {
    "opening_question": "지금 걸려 있는 것 가운데 먼저 말씀하고 싶은 것은 무엇인가요?",
    "suggested_action_title": "걸린 것 하나만 적어 보기",
    "unconfirmed_points": [
      "실제로 조정할 수 있는 범위가 어디까지인지 아직 모릅니다."
    ],
    "working_hypotheses": [
      "한 번에 해결하려는 부담이 시작을 늦추고 있는지"
    ]
  },
  "generation_metadata": {
    "evidence_snapshot_hash": "d37dcfc5c40937db0fc8bc0df23616f93b06584ad1fbb6248f24ffc6086c5508",
    "generated_at": "2026-09-12T04:30:00+00:00",
    "model": "stub-model",
    "prompt_version": "v2.0.0+c3cd72c8",
    "provider": null,
    "repair_count": 0,
    "rule_version": "zhuxi-gobyeonjeom-2026-08-30"
  },
  "narrative": {
    "emotional_context": {
      "pattern_hypothesis": "한 번에 전부 해결하려다 손을 못 대는 흐름이 반복되는지 함께 살펴보면 좋겠습니다.",
      "user_fact_refs": [
        "U1"
      ],
      "validation": "말씀하신 상황에서 답답함이 쌓이는 것은 자연스러운 일입니다. 당장 풀리지 않는 일 앞에서 마음이 무거워지셨을 것 같습니다."
    },
    "headline_metaphor": "단단한 것을 한 번에 삼키려 하지 않고, 씹어 넘길 만큼만 떼어내는 자리입니다.",
    "micro_action_task": {
      "completion_criterion": "표시한 항목이 하나 생기면 끝난 것으로 봅니다.",
      "duration_minutes": 10,
      "smaller_alternative": "적기 어려우면 소리 내어 한 가지만 말해 봅니다.",
      "steps": [
        "지금 마음에 걸리는 일을 떠오르는 대로 적습니다.",
        "그중 가장 작아 보이는 것 하나에 표시합니다."
      ],
      "title": "걸린 것 하나만 적어 보기",
      "when": "오늘 중 조용히 앉을 수 있는 때"
    },
    "perspective": {
      "alternative_perspective": "막혀 있다는 느낌이 능력의 문제가 아니라 순서의 문제일 수 있다는 각도에서 볼 수도 있습니다.",
      "applied_reading": "이번 사연에 옮기면, 전부를 한꺼번에 처리하기보다 걸려 있는 것 하나를 먼저 떼어내는 쪽에 가깝습니다.",
      "classical_reading": "고전은 턱 사이에 낀 것을 깨물어 없애야 비로소 위아래가 맞물린다고 말합니다.",
      "evidence_refs": [
        "E1"
      ],
      "thought_observation": "지금 떠오르는 생각 가운데는 사실이 아니라 지나가는 걱정도 섞여 있을 수 있습니다."
    },
    "value_direction": {
      "conditions_to_check": [
        "지금 걸려 있는 것 가운데 오늘 손댈 수 있는 것이 무엇인지",
        "나누어 하는 방식이 이 상황에서 실제로 가능한지"
      ],
      "evidence_refs": [
        "E1"
      ],
      "proposed_value": "감당할 수 있는 크기로 나누어 다루기",
      "rationale": "한 번에 끝내려는 마음이 클수록 시작이 늦어지는 흐름이 있습니다. 작은 단위로 나누면 손을 댈 자리가 생깁니다."
    }
  },
  "report_id": "00000000-0000-4000-8000-000000000001",
  "schema_version": "2.0",
  "session_id": "fixture-session-0001"
};

export const FIXTURE_V2_THREE_CHANGING = {
  "academic_details": {
    "casting": {
      "changing_lines": [
        1,
        3,
        5
      ],
      "has_transformation": true,
      "lines": [
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 1,
          "value": 9
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 2,
          "value": 8
        },
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 3,
          "value": 9
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 4,
          "value": 8
        },
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 5,
          "value": 9
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 6,
          "value": 8
        }
      ],
      "original_hexagram_id": 63,
      "original_lower_trigram": "리(불)",
      "original_name": "제63괘",
      "original_upper_trigram": "감(물)",
      "transformed_hexagram_id": 2,
      "transformed_name": "제2괘"
    },
    "focus_rule": {
      "body_use_note_ko": null,
      "body_use_type": "STANDARD",
      "changing_count": 3,
      "description_ko": "3개의 변효가 있으므로 본괘 괘사와 지괘 괘사를 함께 참작하되, 본괘 괘사를 위주로 합니다.",
      "focus_type": "BOTH_JUDGMENTS",
      "rule_version": "zhuxi-gobyeonjeom-2026-08-30",
      "target_hexagram_type": "BOTH",
      "target_line_numbers": []
    },
    "sources": [
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "卦辭原文63",
        "classical_translation": "제63괘의 괘사 번역입니다.",
        "hexagram_id": 63,
        "hexagram_name": "제63괘",
        "id": "E1",
        "line_number": null,
        "locator": null,
        "role": "primary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "卦辭原文2",
        "classical_translation": "제2괘의 괘사 번역입니다.",
        "hexagram_id": 2,
        "hexagram_name": "제2괘",
        "id": "E2",
        "line_number": null,
        "locator": null,
        "role": "auxiliary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "象曰 大象原文63",
        "classical_translation": "제63괘 대상전 번역입니다.",
        "hexagram_id": 63,
        "hexagram_name": "제63괘",
        "id": "E3",
        "line_number": null,
        "locator": null,
        "role": "supplement"
      },
      {
        "annotation": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "annotation_source": "정전(程傳)",
        "classical_text": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "classical_translation": null,
        "hexagram_id": 63,
        "hexagram_name": "제63괘",
        "id": "E4",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "annotation_source": "본의(本義)",
        "classical_text": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "classical_translation": null,
        "hexagram_id": 63,
        "hexagram_name": "제63괘",
        "id": "E5",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      }
    ],
    "user_facts": [
      {
        "id": "U1",
        "text": "요즘 일이 막혀 있는 느낌입니다."
      },
      {
        "id": "U2",
        "text": "어디서부터 손을 대야 할까요?"
      }
    ]
  },
  "counseling_handoff": {
    "opening_question": "지금 걸려 있는 것 가운데 먼저 말씀하고 싶은 것은 무엇인가요?",
    "suggested_action_title": "걸린 것 하나만 적어 보기",
    "unconfirmed_points": [
      "실제로 조정할 수 있는 범위가 어디까지인지 아직 모릅니다."
    ],
    "working_hypotheses": [
      "한 번에 해결하려는 부담이 시작을 늦추고 있는지"
    ]
  },
  "generation_metadata": {
    "evidence_snapshot_hash": "825beb5963d4ab5f5cf6a22768a19cc834acb7dc60ea910084995000b272728c",
    "generated_at": "2026-09-12T04:30:00+00:00",
    "model": "stub-model",
    "prompt_version": "v2.0.0+c3cd72c8",
    "provider": null,
    "repair_count": 0,
    "rule_version": "zhuxi-gobyeonjeom-2026-08-30"
  },
  "narrative": {
    "emotional_context": {
      "pattern_hypothesis": "한 번에 전부 해결하려다 손을 못 대는 흐름이 반복되는지 함께 살펴보면 좋겠습니다.",
      "user_fact_refs": [
        "U1"
      ],
      "validation": "말씀하신 상황에서 답답함이 쌓이는 것은 자연스러운 일입니다. 당장 풀리지 않는 일 앞에서 마음이 무거워지셨을 것 같습니다."
    },
    "headline_metaphor": "단단한 것을 한 번에 삼키려 하지 않고, 씹어 넘길 만큼만 떼어내는 자리입니다.",
    "micro_action_task": {
      "completion_criterion": "표시한 항목이 하나 생기면 끝난 것으로 봅니다.",
      "duration_minutes": 10,
      "smaller_alternative": "적기 어려우면 소리 내어 한 가지만 말해 봅니다.",
      "steps": [
        "지금 마음에 걸리는 일을 떠오르는 대로 적습니다.",
        "그중 가장 작아 보이는 것 하나에 표시합니다."
      ],
      "title": "걸린 것 하나만 적어 보기",
      "when": "오늘 중 조용히 앉을 수 있는 때"
    },
    "perspective": {
      "alternative_perspective": "막혀 있다는 느낌이 능력의 문제가 아니라 순서의 문제일 수 있다는 각도에서 볼 수도 있습니다.",
      "applied_reading": "이번 사연에 옮기면, 전부를 한꺼번에 처리하기보다 걸려 있는 것 하나를 먼저 떼어내는 쪽에 가깝습니다.",
      "classical_reading": "고전은 턱 사이에 낀 것을 깨물어 없애야 비로소 위아래가 맞물린다고 말합니다.",
      "evidence_refs": [
        "E1"
      ],
      "thought_observation": "지금 떠오르는 생각 가운데는 사실이 아니라 지나가는 걱정도 섞여 있을 수 있습니다."
    },
    "value_direction": {
      "conditions_to_check": [
        "지금 걸려 있는 것 가운데 오늘 손댈 수 있는 것이 무엇인지",
        "나누어 하는 방식이 이 상황에서 실제로 가능한지"
      ],
      "evidence_refs": [
        "E1"
      ],
      "proposed_value": "감당할 수 있는 크기로 나누어 다루기",
      "rationale": "한 번에 끝내려는 마음이 클수록 시작이 늦어지는 흐름이 있습니다. 작은 단위로 나누면 손을 댈 자리가 생깁니다."
    }
  },
  "report_id": "00000000-0000-4000-8000-000000000001",
  "schema_version": "2.0",
  "session_id": "fixture-session-0001"
};

export const FIXTURE_V2_MULTI_CHANGING = {
  "academic_details": {
    "casting": {
      "changing_lines": [
        1,
        2,
        3,
        4
      ],
      "has_transformation": true,
      "lines": [
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 1,
          "value": 9
        },
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 2,
          "value": 9
        },
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 3,
          "value": 9
        },
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 4,
          "value": 9
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 5,
          "value": 8
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 6,
          "value": 7
        }
      ],
      "original_hexagram_id": 14,
      "original_lower_trigram": "건(하늘)",
      "original_name": "제14괘",
      "original_upper_trigram": "리(불)",
      "transformed_hexagram_id": 23,
      "transformed_name": "제23괘"
    },
    "focus_rule": {
      "body_use_note_ko": null,
      "body_use_type": "STANDARD",
      "changing_count": 4,
      "description_ko": "4개의 변효가 있으므로 지괘에서 변하지 않은 두 효(5효, 6효)의 효사를 주 해석으로 삼으며, 아래쪽 효(5효)를 우선합니다.",
      "focus_type": "MULTIPLE_LINE_STATEMENTS",
      "rule_version": "zhuxi-gobyeonjeom-2026-08-30",
      "target_hexagram_type": "TRANSFORMED",
      "target_line_numbers": [
        5,
        6
      ]
    },
    "sources": [
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "爻辭原文23-5",
        "classical_translation": "제23괘 5효의 효사 번역입니다.",
        "hexagram_id": 23,
        "hexagram_name": "제23괘",
        "id": "E1",
        "line_number": 5,
        "locator": null,
        "role": "primary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "爻辭原文23-6",
        "classical_translation": "제23괘 6효의 효사 번역입니다.",
        "hexagram_id": 23,
        "hexagram_name": "제23괘",
        "id": "E2",
        "line_number": 6,
        "locator": null,
        "role": "auxiliary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "卦辭原文14",
        "classical_translation": "제14괘의 괘사 번역입니다.",
        "hexagram_id": 14,
        "hexagram_name": "제14괘",
        "id": "E3",
        "line_number": null,
        "locator": null,
        "role": "background"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "象曰 大象原文14",
        "classical_translation": "제14괘 대상전 번역입니다.",
        "hexagram_id": 14,
        "hexagram_name": "제14괘",
        "id": "E4",
        "line_number": null,
        "locator": null,
        "role": "supplement"
      },
      {
        "annotation": "그 자리에서 마땅함을 얻으면 허물이 없다고 하였다.",
        "annotation_source": "정전(程傳) 효사 주석",
        "classical_text": "그 자리에서 마땅함을 얻으면 허물이 없다고 하였다.",
        "classical_translation": null,
        "hexagram_id": 23,
        "hexagram_name": "제23괘",
        "id": "E5",
        "line_number": 5,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "annotation_source": "정전(程傳)",
        "classical_text": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "classical_translation": null,
        "hexagram_id": 14,
        "hexagram_name": "제14괘",
        "id": "E6",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "annotation_source": "본의(本義)",
        "classical_text": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "classical_translation": null,
        "hexagram_id": 14,
        "hexagram_name": "제14괘",
        "id": "E7",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      }
    ],
    "user_facts": [
      {
        "id": "U1",
        "text": "요즘 일이 막혀 있는 느낌입니다."
      },
      {
        "id": "U2",
        "text": "어디서부터 손을 대야 할까요?"
      }
    ]
  },
  "counseling_handoff": {
    "opening_question": "지금 걸려 있는 것 가운데 먼저 말씀하고 싶은 것은 무엇인가요?",
    "suggested_action_title": "걸린 것 하나만 적어 보기",
    "unconfirmed_points": [
      "실제로 조정할 수 있는 범위가 어디까지인지 아직 모릅니다."
    ],
    "working_hypotheses": [
      "한 번에 해결하려는 부담이 시작을 늦추고 있는지"
    ]
  },
  "generation_metadata": {
    "evidence_snapshot_hash": "cf6a7f4734b8e96957ae6403e5993ef4c466baa735bad0291beac1e56502d1ef",
    "generated_at": "2026-09-12T04:30:00+00:00",
    "model": "stub-model",
    "prompt_version": "v2.0.0+c3cd72c8",
    "provider": null,
    "repair_count": 0,
    "rule_version": "zhuxi-gobyeonjeom-2026-08-30"
  },
  "narrative": {
    "emotional_context": {
      "pattern_hypothesis": "한 번에 전부 해결하려다 손을 못 대는 흐름이 반복되는지 함께 살펴보면 좋겠습니다.",
      "user_fact_refs": [
        "U1"
      ],
      "validation": "말씀하신 상황에서 답답함이 쌓이는 것은 자연스러운 일입니다. 당장 풀리지 않는 일 앞에서 마음이 무거워지셨을 것 같습니다."
    },
    "headline_metaphor": "단단한 것을 한 번에 삼키려 하지 않고, 씹어 넘길 만큼만 떼어내는 자리입니다.",
    "micro_action_task": {
      "completion_criterion": "표시한 항목이 하나 생기면 끝난 것으로 봅니다.",
      "duration_minutes": 10,
      "smaller_alternative": "적기 어려우면 소리 내어 한 가지만 말해 봅니다.",
      "steps": [
        "지금 마음에 걸리는 일을 떠오르는 대로 적습니다.",
        "그중 가장 작아 보이는 것 하나에 표시합니다."
      ],
      "title": "걸린 것 하나만 적어 보기",
      "when": "오늘 중 조용히 앉을 수 있는 때"
    },
    "perspective": {
      "alternative_perspective": "막혀 있다는 느낌이 능력의 문제가 아니라 순서의 문제일 수 있다는 각도에서 볼 수도 있습니다.",
      "applied_reading": "이번 사연에 옮기면, 전부를 한꺼번에 처리하기보다 걸려 있는 것 하나를 먼저 떼어내는 쪽에 가깝습니다.",
      "classical_reading": "고전은 턱 사이에 낀 것을 깨물어 없애야 비로소 위아래가 맞물린다고 말합니다.",
      "evidence_refs": [
        "E1"
      ],
      "thought_observation": "지금 떠오르는 생각 가운데는 사실이 아니라 지나가는 걱정도 섞여 있을 수 있습니다."
    },
    "value_direction": {
      "conditions_to_check": [
        "지금 걸려 있는 것 가운데 오늘 손댈 수 있는 것이 무엇인지",
        "나누어 하는 방식이 이 상황에서 실제로 가능한지"
      ],
      "evidence_refs": [
        "E1"
      ],
      "proposed_value": "감당할 수 있는 크기로 나누어 다루기",
      "rationale": "한 번에 끝내려는 마음이 클수록 시작이 늦어지는 흐름이 있습니다. 작은 단위로 나누면 손을 댈 자리가 생깁니다."
    }
  },
  "report_id": "00000000-0000-4000-8000-000000000001",
  "schema_version": "2.0",
  "session_id": "fixture-session-0001"
};

export const FIXTURE_V2_MISSING_TRANSLATION = {
  "academic_details": {
    "casting": {
      "changing_lines": [
        1
      ],
      "has_transformation": true,
      "lines": [
        {
          "is_changing": true,
          "line_type_ko": "노양",
          "position": 1,
          "value": 9
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 2,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 3,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 4,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 5,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 6,
          "value": 7
        }
      ],
      "original_hexagram_id": 1,
      "original_lower_trigram": "건(하늘)",
      "original_name": "제1괘",
      "original_upper_trigram": "건(하늘)",
      "transformed_hexagram_id": 44,
      "transformed_name": "제44괘"
    },
    "focus_rule": {
      "body_use_note_ko": null,
      "body_use_type": "STANDARD",
      "changing_count": 1,
      "description_ko": "1개의 변효가 있으므로 본괘 1효의 효사(爻辭)를 주 해석으로 삼습니다.",
      "focus_type": "SINGLE_LINE_STATEMENT",
      "rule_version": "zhuxi-gobyeonjeom-2026-08-30",
      "target_hexagram_type": "ORIGINAL",
      "target_line_numbers": [
        1
      ]
    },
    "sources": [
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "爻辭原文1-1",
        "classical_translation": null,
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E1",
        "line_number": 1,
        "locator": null,
        "role": "primary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "卦辭原文1",
        "classical_translation": "제1괘의 괘사 번역입니다.",
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E2",
        "line_number": null,
        "locator": null,
        "role": "background"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "象曰 大象原文1",
        "classical_translation": "제1괘 대상전 번역입니다.",
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E3",
        "line_number": null,
        "locator": null,
        "role": "supplement"
      },
      {
        "annotation": "그 자리에서 마땅함을 얻으면 허물이 없다고 하였다.",
        "annotation_source": "정전(程傳) 효사 주석",
        "classical_text": "그 자리에서 마땅함을 얻으면 허물이 없다고 하였다.",
        "classical_translation": null,
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E4",
        "line_number": 1,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "annotation_source": "정전(程傳)",
        "classical_text": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "classical_translation": null,
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E5",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "annotation_source": "본의(本義)",
        "classical_text": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "classical_translation": null,
        "hexagram_id": 1,
        "hexagram_name": "제1괘",
        "id": "E6",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      }
    ],
    "user_facts": [
      {
        "id": "U1",
        "text": "요즘 일이 막혀 있는 느낌입니다."
      },
      {
        "id": "U2",
        "text": "어디서부터 손을 대야 할까요?"
      }
    ]
  },
  "counseling_handoff": {
    "opening_question": "지금 걸려 있는 것 가운데 먼저 말씀하고 싶은 것은 무엇인가요?",
    "suggested_action_title": "걸린 것 하나만 적어 보기",
    "unconfirmed_points": [
      "실제로 조정할 수 있는 범위가 어디까지인지 아직 모릅니다."
    ],
    "working_hypotheses": [
      "한 번에 해결하려는 부담이 시작을 늦추고 있는지"
    ]
  },
  "generation_metadata": {
    "evidence_snapshot_hash": "c4528099a06e9ba89c85a80329599e077f532d4f8d58358b984df0c3db43afe7",
    "generated_at": "2026-09-12T04:30:00+00:00",
    "model": "stub-model",
    "prompt_version": "v2.0.0+c3cd72c8",
    "provider": null,
    "repair_count": 0,
    "rule_version": "zhuxi-gobyeonjeom-2026-08-30"
  },
  "narrative": {
    "emotional_context": {
      "pattern_hypothesis": "한 번에 전부 해결하려다 손을 못 대는 흐름이 반복되는지 함께 살펴보면 좋겠습니다.",
      "user_fact_refs": [
        "U1"
      ],
      "validation": "말씀하신 상황에서 답답함이 쌓이는 것은 자연스러운 일입니다. 당장 풀리지 않는 일 앞에서 마음이 무거워지셨을 것 같습니다."
    },
    "headline_metaphor": "단단한 것을 한 번에 삼키려 하지 않고, 씹어 넘길 만큼만 떼어내는 자리입니다.",
    "micro_action_task": {
      "completion_criterion": "표시한 항목이 하나 생기면 끝난 것으로 봅니다.",
      "duration_minutes": 10,
      "smaller_alternative": "적기 어려우면 소리 내어 한 가지만 말해 봅니다.",
      "steps": [
        "지금 마음에 걸리는 일을 떠오르는 대로 적습니다.",
        "그중 가장 작아 보이는 것 하나에 표시합니다."
      ],
      "title": "걸린 것 하나만 적어 보기",
      "when": "오늘 중 조용히 앉을 수 있는 때"
    },
    "perspective": {
      "alternative_perspective": "막혀 있다는 느낌이 능력의 문제가 아니라 순서의 문제일 수 있다는 각도에서 볼 수도 있습니다.",
      "applied_reading": "이번 사연에 옮기면, 전부를 한꺼번에 처리하기보다 걸려 있는 것 하나를 먼저 떼어내는 쪽에 가깝습니다.",
      "classical_reading": "고전은 턱 사이에 낀 것을 깨물어 없애야 비로소 위아래가 맞물린다고 말합니다.",
      "evidence_refs": [
        "E1"
      ],
      "thought_observation": "지금 떠오르는 생각 가운데는 사실이 아니라 지나가는 걱정도 섞여 있을 수 있습니다."
    },
    "value_direction": {
      "conditions_to_check": [
        "지금 걸려 있는 것 가운데 오늘 손댈 수 있는 것이 무엇인지",
        "나누어 하는 방식이 이 상황에서 실제로 가능한지"
      ],
      "evidence_refs": [
        "E1"
      ],
      "proposed_value": "감당할 수 있는 크기로 나누어 다루기",
      "rationale": "한 번에 끝내려는 마음이 클수록 시작이 늦어지는 흐름이 있습니다. 작은 단위로 나누면 손을 댈 자리가 생깁니다."
    }
  },
  "report_id": "00000000-0000-4000-8000-000000000001",
  "schema_version": "2.0",
  "session_id": "fixture-session-0001"
};

export const FIXTURE_LEGACY_REPORT = {
  "final_summary": "작게 나누어 씹어 넘기는 것이 이번의 방법입니다.",
  "focus_and_body_use": {
    "body_use_flow": "동효가 없어 지괘가 없습니다. 체용(體用) 보완 규칙은 적용되지 않습니다.",
    "changing_count": 0,
    "primary_target_name": "화뢰서합 괘사",
    "rule_description": "변효가 없으므로 본괘의 괘사(卦辭)를 주 해석으로 삼습니다."
  },
  "hexagram_casting": {
    "has_transformation": false,
    "lines": [
      {
        "is_changing": false,
        "line_type_ko": "소양",
        "name": "1효 (초효)",
        "note": "변하지 않는 양효",
        "position": 1,
        "symbol": "⚊",
        "value": 7
      },
      {
        "is_changing": false,
        "line_type_ko": "소음",
        "name": "2효 (이효)",
        "note": "변하지 않는 음효",
        "position": 2,
        "symbol": "⚋",
        "value": 8
      },
      {
        "is_changing": false,
        "line_type_ko": "소음",
        "name": "3효 (삼효)",
        "note": "변하지 않는 음효",
        "position": 3,
        "symbol": "⚋",
        "value": 8
      },
      {
        "is_changing": false,
        "line_type_ko": "소양",
        "name": "4효 (사효)",
        "note": "변하지 않는 양효",
        "position": 4,
        "symbol": "⚊",
        "value": 7
      },
      {
        "is_changing": false,
        "line_type_ko": "소음",
        "name": "5효 (오효)",
        "note": "변하지 않는 음효",
        "position": 5,
        "symbol": "⚋",
        "value": 8
      },
      {
        "is_changing": false,
        "line_type_ko": "소양",
        "name": "6효 (상효)",
        "note": "변하지 않는 양효",
        "position": 6,
        "symbol": "⚊",
        "value": 7
      }
    ],
    "original_hex_id": 21,
    "original_lower_trigram": "진(우레)",
    "original_name_full": "화뢰서합",
    "original_name_hanja": "噬嗑",
    "original_summary": "서합은 형통하니, 옥사를 씀이 이롭다.",
    "original_upper_trigram": "리(불)",
    "transformed_hex_id": null,
    "transformed_name_full": null,
    "transformed_name_hanja": null,
    "transformed_summary": null
  },
  "question_setting": {
    "mindset_rule": "재삼독(再三瀆) 원칙에 따라 이 세션의 괘는 한 번 도출한 뒤 다시 뽑지 않고 그대로 이어집니다.",
    "question": "요즘 일이 막혀 있는 느낌입니다."
  },
  "section1_diagnosis": {
    "hanja_text": "噬嗑",
    "interpretation": "지금은 막힌 것을 다루어야 하는 자리입니다.",
    "target_name": "화뢰서합",
    "title": "① 현재 상황 진단 (본괘: 화뢰서합)"
  },
  "section2_action": {
    "hanja_text": "噬嗑 亨 利用獄",
    "interpretation": "걸려 있는 것을 하나씩 떼어내십시오.",
    "target_name": "화뢰서합 괘사",
    "title": "② 핵심 행동 지침 (주 해석 대상: 화뢰서합 괘사)"
  },
  "section3_warning": {
    "hanja_text": null,
    "interpretation": "한 번에 끝내려는 조급함을 경계하십시오.",
    "target_name": "경계 지침",
    "title": "③ 보조 경계 지침 (경계 지침)"
  },
  "section4_future": {
    "hanja_text": null,
    "interpretation": "지금의 국면이 이어집니다.",
    "target_name": "화뢰서합",
    "title": "④ 미래의 귀결 및 주의점 (본괘 유지)"
  }
};

export const FIXTURE_REPORT_FAILED_ENVELOPE = {
  "report_data": null,
  "report_error_code": "REPORT_NARRATIVE_INVALID",
  "report_status": "failed"
};

export const FIXTURE_V2_UNKNOWN = {
  "academic_details": {
    "casting": {
      "changing_lines": [],
      "has_transformation": false,
      "lines": [
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 1,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 2,
          "value": 8
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 3,
          "value": 8
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 4,
          "value": 7
        },
        {
          "is_changing": false,
          "line_type_ko": "소음",
          "position": 5,
          "value": 8
        },
        {
          "is_changing": false,
          "line_type_ko": "소양",
          "position": 6,
          "value": 7
        }
      ],
      "original_hexagram_id": 21,
      "original_lower_trigram": "진(우레)",
      "original_name": "화뢰서합",
      "original_upper_trigram": "리(불)",
      "transformed_hexagram_id": null,
      "transformed_name": null
    },
    "focus_rule": {
      "body_use_note_ko": null,
      "body_use_type": "STANDARD",
      "changing_count": 0,
      "description_ko": "변효가 없으므로 본괘의 괘사(卦辭)를 주 해석으로 삼습니다.",
      "focus_type": "ORIGINAL_JUDGMENT",
      "rule_version": "zhuxi-gobyeonjeom-2026-08-30",
      "target_hexagram_type": "ORIGINAL",
      "target_line_numbers": []
    },
    "sources": [
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "噬嗑 亨 利用獄",
        "classical_translation": "서합은 형통하니, 옥사를 씀이 이롭다.",
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E1",
        "line_number": null,
        "locator": null,
        "role": "primary"
      },
      {
        "annotation": null,
        "annotation_source": null,
        "classical_text": "象曰 雷電噬嗑 先王以 明罰勅法",
        "classical_translation": "우레와 번개가 서합이니, 선왕이 이를 본받아 형벌을 밝히고 법령을 정돈하였다.",
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E2",
        "line_number": null,
        "locator": null,
        "role": "supplement"
      },
      {
        "annotation": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "annotation_source": "정전(程傳)",
        "classical_text": "턱 사이에 물건이 있어 깨물어 없애야 합해지니, 깨물어 합하면 형통하다.",
        "classical_translation": null,
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E3",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      },
      {
        "annotation": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "annotation_source": "본의(本義)",
        "classical_text": "막힌 것을 깨물어 통하게 한다는 뜻을 취하였다.",
        "classical_translation": null,
        "hexagram_id": 21,
        "hexagram_name": "화뢰서합",
        "id": "E4",
        "line_number": null,
        "locator": null,
        "role": "annotation"
      }
    ],
    "user_facts": [
      {
        "id": "U1",
        "text": "요즘 일이 막혀 있는 느낌입니다."
      },
      {
        "id": "U2",
        "text": "어디서부터 손을 대야 할까요?"
      }
    ]
  },
  "counseling_handoff": {
    "opening_question": "지금 걸려 있는 것 가운데 먼저 말씀하고 싶은 것은 무엇인가요?",
    "suggested_action_title": "걸린 것 하나만 적어 보기",
    "unconfirmed_points": [
      "실제로 조정할 수 있는 범위가 어디까지인지 아직 모릅니다."
    ],
    "working_hypotheses": [
      "한 번에 해결하려는 부담이 시작을 늦추고 있는지"
    ]
  },
  "generation_metadata": {
    "evidence_snapshot_hash": "cc9ab1bd575d3af165dcd891f8e9f9e2e299080579f738153a5ba45cbbf308a4",
    "generated_at": "2026-09-12T04:30:00+00:00",
    "model": "stub-model",
    "prompt_version": "v2.0.0+c3cd72c8",
    "provider": null,
    "repair_count": 0,
    "rule_version": "zhuxi-gobyeonjeom-2026-08-30"
  },
  "narrative": {
    "emotional_context": {
      "pattern_hypothesis": "한 번에 전부 해결하려다 손을 못 대는 흐름이 반복되는지 함께 살펴보면 좋겠습니다.",
      "user_fact_refs": [
        "U1"
      ],
      "validation": "말씀하신 상황에서 답답함이 쌓이는 것은 자연스러운 일입니다. 당장 풀리지 않는 일 앞에서 마음이 무거워지셨을 것 같습니다."
    },
    "headline_metaphor": "단단한 것을 한 번에 삼키려 하지 않고, 씹어 넘길 만큼만 떼어내는 자리입니다.",
    "micro_action_task": {
      "completion_criterion": "표시한 항목이 하나 생기면 끝난 것으로 봅니다.",
      "duration_minutes": 10,
      "smaller_alternative": "적기 어려우면 소리 내어 한 가지만 말해 봅니다.",
      "steps": [
        "지금 마음에 걸리는 일을 떠오르는 대로 적습니다.",
        "그중 가장 작아 보이는 것 하나에 표시합니다."
      ],
      "title": "걸린 것 하나만 적어 보기",
      "when": "오늘 중 조용히 앉을 수 있는 때"
    },
    "perspective": {
      "alternative_perspective": "막혀 있다는 느낌이 능력의 문제가 아니라 순서의 문제일 수 있다는 각도에서 볼 수도 있습니다.",
      "applied_reading": "이번 사연에 옮기면, 전부를 한꺼번에 처리하기보다 걸려 있는 것 하나를 먼저 떼어내는 쪽에 가깝습니다.",
      "classical_reading": "고전은 턱 사이에 낀 것을 깨물어 없애야 비로소 위아래가 맞물린다고 말합니다.",
      "evidence_refs": [
        "E1"
      ],
      "thought_observation": "지금 떠오르는 생각 가운데는 사실이 아니라 지나가는 걱정도 섞여 있을 수 있습니다."
    },
    "value_direction": {
      "conditions_to_check": [
        "지금 걸려 있는 것 가운데 오늘 손댈 수 있는 것이 무엇인지",
        "나누어 하는 방식이 이 상황에서 실제로 가능한지"
      ],
      "evidence_refs": [
        "E1"
      ],
      "proposed_value": "감당할 수 있는 크기로 나누어 다루기",
      "rationale": "한 번에 끝내려는 마음이 클수록 시작이 늦어지는 흐름이 있습니다. 작은 단위로 나누면 손을 댈 자리가 생깁니다."
    }
  },
  "report_id": "00000000-0000-4000-8000-000000000001",
  "schema_version": "3.0",
  "session_id": "fixture-session-0001"
};

import { CastResult } from '../../types/iching';

export function getFixtureCastResult(report: PreCounselingReportV2): CastResult {
  const casting = report.academic_details.casting;
  const focus = report.academic_details.focus_rule;
  return {
    originalHexId: casting.original_hexagram_id,
    transformedHexId: casting.transformed_hexagram_id || casting.original_hexagram_id,
    lines: casting.lines.map((l) => ({
      position: l.position,
      value: l.value,
      isYang: l.value === 7 || l.value === 9,
      isChanging: l.is_changing,
    })),
    changingPositions: casting.changing_lines,
    focusRule: {
      focusType: focus.focus_type,
      targetHexagramType: focus.target_hexagram_type,
      targetLineNumbers: focus.target_line_numbers,
      descriptionKo: focus.description_ko,
      bodyUseType: focus.body_use_type,
      bodyUseNoteKo: focus.body_use_note_ko,
    },
  };
}

export const AVAILABLE_FIXTURES: Record<
  string,
  {
    name: string;
    reportData: AnyReportData | null;
    reportStatus?: 'ready' | 'failed' | 'not_requested';
    reportErrorCode?: string;
  }
> = {
  v2_invariant: {
    name: 'v2 불변괘 (화뢰서합 21)',
    reportData: FIXTURE_V2_INVARIANT as unknown as PreCounselingReportV2,
    reportStatus: 'ready',
  },
  v2_single_changing: {
    name: 'v2 동효 1개 (수천수 5)',
    reportData: FIXTURE_V2_SINGLE_CHANGING as unknown as PreCounselingReportV2,
    reportStatus: 'ready',
  },
  v2_three_changing: {
    name: 'v2 동효 3개 (지천태 11)',
    reportData: FIXTURE_V2_THREE_CHANGING as unknown as PreCounselingReportV2,
    reportStatus: 'ready',
  },
  v2_multi_changing: {
    name: 'v2 동효 4개 (중천건 1)',
    reportData: FIXTURE_V2_MULTI_CHANGING as unknown as PreCounselingReportV2,
    reportStatus: 'ready',
  },
  v2_missing_translation: {
    name: 'v2 번역 결측 (확인된 번역 없음)',
    reportData: FIXTURE_V2_MISSING_TRANSLATION as unknown as PreCounselingReportV2,
    reportStatus: 'ready',
  },
  v2_unknown: {
    name: 'v2 알 수 없는 판본 (schema_version 3.0)',
    reportData: FIXTURE_V2_UNKNOWN as unknown as AnyReportData,
    reportStatus: 'ready',
  },
  legacy_report: {
    name: 'v1 레거시 리포트 (과거 형식)',
    reportData: FIXTURE_LEGACY_REPORT as unknown as HexagramReportData,
    reportStatus: 'ready',
  },
  report_failed: {
    name: '리포트 생성 실패 (REPORT_EVIDENCE_INVALID)',
    reportData: null,
    reportStatus: 'failed',
    reportErrorCode: 'REPORT_EVIDENCE_INVALID',
  },
};

