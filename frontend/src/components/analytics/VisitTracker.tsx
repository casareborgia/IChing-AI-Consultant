'use client';

import { useEffect, useRef } from 'react';
import { useAuth } from '@/context/AuthContext';
import { postVisitPingApi } from '@/lib/api';

/**
 * 자체 1st-party 방문 기록기.
 *
 * `@vercel/analytics`는 Vercel 대시보드로만 가고 우리 DB에 아무 것도 남기지
 * 않는다. 운영 대시보드가 방문자수·재방문 횟수를 보려면 우리 백엔드가 방문을
 * 알아야 하므로, 브라우저 세션당 한 번 ping을 보낸다.
 *
 * 저장하는 것
 * - localStorage `iching_visitor_id`: 브라우저가 스스로 만든 랜덤 UUID.
 *   서버는 이 값의 원문을 저장하지 않고 서버 pepper를 섞은 해시만 남긴다.
 * - sessionStorage `iching_visit_pinged`: 이 탭 세션에서 이미 보냈다는 표시.
 *   탭을 새로 열면 다시 보내지만, 서버가 30분 이내 재호출을 같은 방문으로
 *   병합하므로 방문 수가 부풀지 않는다.
 *
 * 수집이 꺼져 있으면(`VISITOR_ANALYTICS_ENABLED=false`) 서버가 'disabled'를
 * 돌려주고, 그 경우 **식별자를 저장하지 않는다.** 수집하지도 않을 식별자를
 * 이용자 브라우저에 남기지 않기 위한 것이다.
 */

const VISITOR_ID_KEY = 'iching_visitor_id';
const SESSION_FLAG_KEY = 'iching_visit_pinged';

function readStored(storage: 'local' | 'session', key: string): string | null {
  try {
    const store = storage === 'local' ? window.localStorage : window.sessionStorage;
    return store.getItem(key);
  } catch {
    // 사생활 보호 모드나 저장소 차단 환경. 방문 기록은 포기하고 조용히 넘어간다.
    return null;
  }
}

function writeStored(storage: 'local' | 'session', key: string, value: string): void {
  try {
    const store = storage === 'local' ? window.localStorage : window.sessionStorage;
    store.setItem(key, value);
  } catch {
    /* 저장 실패는 무시한다 */
  }
}

function newVisitorId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // randomUUID가 없는 구형 브라우저 대비. 서버의 허용 형식(32~64자 hex)에 맞춘다.
  const bytes = new Uint8Array(16);
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

/** User-Agent 원문은 서버에 보내지 않는다. 세 값 중 하나로만 좁힌다. */
function detectDevice(): 'mobile' | 'tablet' | 'desktop' {
  const ua = navigator.userAgent || '';
  if (/iPad|Tablet|PlayBook|Silk/i.test(ua) || (/Android/i.test(ua) && !/Mobile/i.test(ua))) {
    return 'tablet';
  }
  if (/Mobi|Android|iPhone|iPod|IEMobile|Opera Mini/i.test(ua)) {
    return 'mobile';
  }
  return 'desktop';
}

/** 같은 사이트 내 이동은 유입이 아니다. 외부 referrer만 넘긴다. */
function externalReferrer(): string | undefined {
  const raw = document.referrer;
  if (!raw) return undefined;
  try {
    if (new URL(raw).hostname === window.location.hostname) return undefined;
  } catch {
    return undefined;
  }
  return raw;
}

export function VisitTracker() {
  const { session, isLoading } = useAuth();
  const sentRef = useRef(false);

  useEffect(() => {
    // 세션 복구가 끝난 뒤에 보낸다. 로그인 상태를 모르는 채로 보내면 회원
    // 방문이 전부 익명으로 집계된다.
    if (isLoading || sentRef.current) return;
    if (readStored('session', SESSION_FLAG_KEY)) {
      sentRef.current = true;
      return;
    }
    sentRef.current = true;

    // 기존 식별자가 없으면 후보를 만들어 보내고, 서버가 실제로 기록했을 때만
    // 저장한다.
    const stored = readStored('local', VISITOR_ID_KEY);
    const visitorId = stored || newVisitorId();

    // postVisitPingApi 는 스스로 실패를 삼키지만, 여기서도 한 겹 막는다.
    // 이 effect 에서 예외가 새면 화면 전체가 영향을 받는다.
    void (async () => {
      const res = await postVisitPingApi(
        visitorId,
        {
          path: window.location.pathname,
          referrer: externalReferrer(),
          device: detectDevice(),
        },
        session?.access_token ?? null
      );

      if (res.status === 'recorded' || res.status === 'merged') {
        if (!stored) writeStored('local', VISITOR_ID_KEY, visitorId);
        writeStored('session', SESSION_FLAG_KEY, '1');
      }
    })().catch(() => {
      /* 방문 통계 실패는 서비스 이용에 영향을 주지 않는다 */
    });
  }, [isLoading, session?.access_token]);

  return null;
}
