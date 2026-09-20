/**
 * CYCLE-03 T04-FE-ENV-E2E 브라우저 검증용 Mock 인터셉트 헬퍼
 */

window.__setupMockScenario = function(scenarioName, options = {}) {
  const origFetch = window.__origFetch || window.fetch;
  window.__origFetch = origFetch;

  const networkLog = window.__networkLog || [];
  window.__networkLog = networkLog;

  window.fetch = async function(...args) {
    const url = String(args[0]);
    const init = args[1] || {};
    const headers = init.headers || {};

    // Header에서 Idempotency-Key 캡처 (토큰 및 민감정보는 제외/마스킹)
    const idempotencyKey = headers['Idempotency-Key'] || headers['idempotency-key'] || null;
    const authHeader = headers['Authorization'] || headers['authorization'] || null;

    networkLog.push({
      time: new Date().toISOString(),
      url: url.replace(/^http:\/\/localhost:8008/, ''),
      method: init.method || 'GET',
      idempotencyKey: idempotencyKey,
      hasAuth: Boolean(authHeader),
    });

    // 1. Public Config 시나리오
    if (url.includes('/api/public/config')) {
      if (scenarioName === 'config-active') {
        return new Response(JSON.stringify({
          service_stage: 'free_beta',
          generation_enabled: true,
          purchase_enabled: false,
          policy_documents_draft: false,
          free_beta_ready: true,
          consultation_credit_cost: 10,
          welcome_credits: 50,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

      if (scenarioName === 'config-preparing') {
        return new Response(JSON.stringify({
          service_stage: 'free_beta',
          generation_enabled: true,
          purchase_enabled: false,
          policy_documents_draft: false,
          free_beta_ready: false, // 준비 중
          consultation_credit_cost: 10,
          welcome_credits: 50,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

      if (scenarioName === 'config-fallback') {
        return new Response(JSON.stringify({ detail: 'Internal Server Error' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    // 2. GET /api/me/credits 잔액 시나리오
    if (url.includes('/api/me/credits')) {
      if (scenarioName === 'auth-balance-success' || options.balanceSuccess) {
        return new Response(JSON.stringify({
          remaining_credits: 40,
          welcome_granted: true,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

      if (scenarioName === 'auth-balance-failed' || options.balanceFailed) {
        return new Response(JSON.stringify({ detail: 'Credit service unavailable' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    }

    // 3. /api/counsel/start 시나리오
    if (url.includes('/api/counsel/start')) {
      if (scenarioName === 'counsel-200' || options.counselSuccess) {
        return new Response(JSON.stringify({
          session_id: 'sess-mock-001',
          operation_id: 'op-mock-start-200',
          operation_status: 'SUCCEEDED',
          credit_delta: -10,
          remaining_credits: 40,
          is_crisis: false,
          cast_result: {
            primary_hexagram: { number: 1, name: '중천건', name_hanja: '重天乾' },
            transformed_hexagram: null,
            changing_lines: [],
            judgment: { original: '元亨利貞', korean: '건은 크게 형통하고 바르게 함이 이로우니라.' },
          },
          first_message: {
            id: 'msg-mock-1',
            sender: 'ai',
            content: '마주하신 고민에서 하늘의 굳건한 변화의 기운이 엿보입니다. 어떤 점에서 가장 마음이 쓰이시나요?',
            timestamp: '12:00 PM',
          },
          report_data: {
            primary_hexagram_name: '중천건',
            primary_hexagram_hanja: '重天乾',
            focus_rule_desc: '변효가 없으므로 본괘의 괘사를 위주로 살핍니다.',
          },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

      if (scenarioName === 'counsel-polling-timeout' || options.pollingTimeout) {
        return new Response(JSON.stringify({
          code: 'OPERATION_IN_PROGRESS',
          operation_id: 'op-mock-timeout-999',
          retry_after_seconds: 0.1,
        }), { status: 202, headers: { 'Content-Type': 'application/json' } });
      }

      if (scenarioName === 'counsel-released' || options.counselReleased) {
        return new Response(JSON.stringify({
          code: 'OPERATION_IN_PROGRESS',
          operation_id: 'op-mock-released-888',
          retry_after_seconds: 0.1,
        }), { status: 202, headers: { 'Content-Type': 'application/json' } });
      }
    }

    // 4. /api/counsel/operations/ 조회 시나리오
    if (url.includes('/api/counsel/operations/')) {
      if (scenarioName === 'counsel-polling-timeout' || options.pollingTimeout) {
        // 지속적으로 PROCESSING 반환하여 polling 한도 초과(timeout) 유도
        return new Response(JSON.stringify({
          operation_id: 'op-mock-timeout-999',
          operation_status: 'PROCESSING',
          retry_after_seconds: 0.1,
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }

      if (scenarioName === 'counsel-released' || options.counselReleased) {
        // 답변 없이 릴리스된 terminal 오류 반환
        return new Response(JSON.stringify({
          operation_id: 'op-mock-released-888',
          operation_status: 'RELEASED',
          credit_delta: 0,
          remaining_credits: 50,
          response_snapshot: null,
          message: '안전 또는 시스템 정책에 따라 작업이 해제되었습니다.',
        }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
    }

    return origFetch(...args);
  };

  console.log(`[MockScenarios] Active scenario: ${scenarioName}`);
};
