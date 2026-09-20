import React from 'react';
import Link from 'next/link';
import { LegalHeader } from '../../components/layout/LegalHeader';
import { Footer } from '../../components/layout/Footer';
import { Eye, Trash2, Globe, ShieldCheck } from 'lucide-react';
import { LEGAL_DOCUMENTS_VERSION } from '../../lib/legalVersion';
import { LEGAL_REVISIONS } from '../../lib/legalHistory';
import { ConsentWithdrawSection } from '../../components/legal/ConsentWithdrawSection';

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-stone-950 text-stone-200 flex flex-col font-sans selection:bg-amber-900 selection:text-amber-100">
      <LegalHeader
        title="개인정보처리방침"
        subtitle="리인베스트먼트 '마음지기' 서비스의 개인정보보호법에 따른 정보 수집, 보관, 국외 이전 및 처리 방침"
        badgeText={LEGAL_DOCUMENTS_VERSION}
      />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:px-6 space-y-8 text-sm leading-relaxed">
        <div className="text-xs text-stone-400 leading-relaxed bg-stone-900/40 p-3.5 rounded-lg border border-stone-800/80">
          리인베스트먼트(이하 &apos;회사&apos;)는 주역 기반 AI 심층 성찰 상담 서비스 &apos;마음지기&apos;(이하 &apos;서비스&apos;)를 이용하는 정보주체의 자유와 권리 보호를 위하여 「개인정보 보호법」 및 관계 법령이 정한 바를 준수하며, 이용자의 개인정보를 안전하게 처리하고 보호하기 위해 다음과 같이 개인정보처리방침을 수립·공개합니다.
        </div>

        {/* 1. 수집하는 개인정보 항목 및 목적 (D03) */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Eye className="w-4 h-4 text-amber-500" />
            1. 수집하는 개인정보 항목 및 목적
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border border-stone-800 rounded-lg overflow-hidden">
              <thead className="bg-stone-900/80 text-stone-300 font-medium">
                <tr>
                  <th className="p-2.5 border-b border-stone-800">구분</th>
                  <th className="p-2.5 border-b border-stone-800">수집 항목</th>
                  <th className="p-2.5 border-b border-stone-800">처리 목적</th>
                  <th className="p-2.5 border-b border-stone-800">보유 및 이용 기간</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800/60 text-stone-400">
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">필수 (회원가입)</td>
                  <td className="p-2.5">계정 식별자(UUID), 이메일, 닉네임, 프로필 이미지 URL (Google OAuth)</td>
                  <td className="p-2.5">회원 식별, 서비스 접근 제어, 크레딧 원장 부여 및 관리</td>
                  <td className="p-2.5 text-stone-300">본인 직접 삭제 시 즉시 파기</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">필수 (상담 생성)</td>
                  <td className="p-2.5">상담 질문 발화, 대화 내용, 도출된 주역 괘 및 효 정보, 성찰 저널 데이터</td>
                  <td className="p-2.5">AI 주역 상담 수행, 맞춤형 성찰 저널 작성 및 본인 열람 기록 관리</td>
                  <td className="p-2.5 text-stone-300">본인 직접 삭제 시 즉시 파기</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">선택 (고객지원)</td>
                  <td className="p-2.5">문의 접수 이메일, 문의 분류, 문의 본문 내용, 상담 세션 식별자</td>
                  <td className="p-2.5">고객 문의 접수, 사실 관계 확인 및 처리 결과 회신</td>
                  <td className="p-2.5 text-stone-300">문의 처리 완료 후 3년간 보관 (전자상거래 등에서의 소비자보호에 관한 법률 준용)</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">서비스 이용 과정</td>
                  <td className="p-2.5">접속 로그, IP 주소, 이용 일시, 서비스 이용 기록</td>
                  <td className="p-2.5">서비스 보안, 부정 이용 방지, 비정상적 요청 제어</td>
                  <td className="p-2.5 text-stone-300">통신비밀보호법에 따라 3개월간 보관</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">방문 통계</td>
                  <td className="p-2.5">
                    가명처리된 방문자 식별자(이용자 브라우저에서 무작위 생성 후 서버 솔트와 결합한
                    일방향 해시로 가명처리), 방문 일시, 방문 횟수, 진입 경로, 외부 유입 도메인, 기기 유형(모바일/태블릿/PC)
                    <span className="block mt-1 text-[11px] text-stone-500">
                      IP 주소와 브라우저 정보(User-Agent) 원문은 이 항목에 저장하지 않습니다.
                    </span>
                  </td>
                  <td className="p-2.5">서비스 방문자수 및 재방문 현황 집계, 서비스 개선 판단</td>
                  <td className="p-2.5 text-stone-300">수집일로부터 180일 경과 시 파기</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* 2. 개인정보의 보유 및 파기 절차 (A29) */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Trash2 className="w-4 h-4 text-amber-500" />
            2. 개인정보의 보유 및 파기 절차
          </h2>
          <p className="text-stone-300 leading-relaxed">
            원칙적으로 개인정보의 수집 및 이용 목적이 달성된 후에는 해당 정보를 지체 없이 파기합니다.
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-stone-400 text-xs">
            <li>
              <strong className="text-stone-200">파기 절차:</strong> 이용자가 상담 완료 화면에서 <code className="text-amber-400 bg-stone-900 px-1 py-0.5 rounded">[이 상담 기록 삭제]</code> 버튼을 실행하면 연결된 대화 내용 및 성찰 저널이 DB에서 즉시 물리적 삭제(CASCADE)되며 복구되지 않습니다.
            </li>
            <li>
              <strong className="text-stone-200">파기 방법:</strong> 전자적 파일 형태로 저장된 개인정보는 기록을 재생할 수 없는 기술적 방법을 사용하여 영구 삭제합니다.
            </li>
          </ul>
        </section>

        {/* 3. 개인정보 처리 위탁 현황 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Globe className="w-4 h-4 text-amber-500" />
            3. 개인정보 처리 위탁 현황
          </h2>
          <p className="text-stone-300">
            서비스의 안정적 운영과 고품질 AI 상담 제공을 위해 다음과 같이 개인정보 처리를 위탁하고 있습니다:
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border border-stone-800 rounded-lg overflow-hidden">
              <thead className="bg-stone-900/80 text-stone-300 font-medium">
                <tr>
                  <th className="p-2.5 border-b border-stone-800">수탁 업체</th>
                  <th className="p-2.5 border-b border-stone-800">위탁 업무 내용</th>
                  <th className="p-2.5 border-b border-stone-800">실측 인프라 리전</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800/60 text-stone-400">
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">Google LLC</td>
                  <td className="p-2.5">Cloud Run 백엔드 API 호스팅 및 시스템 운영</td>
                  <td className="p-2.5 text-stone-300">asia-northeast3 (대한민국 서울)</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">Google LLC</td>
                  <td className="p-2.5">Vertex AI 기반 주역 괘 해석 및 성찰 대화 추론</td>
                  <td className="p-2.5 text-amber-400 font-mono">us-central1, us-east5 (미국)</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">Supabase Inc.</td>
                  <td className="p-2.5">사용자 인증 세션 관리 및 암호화 DB 호스팅</td>
                  <td className="p-2.5 text-stone-300">ap-northeast-1 (일본 도쿄, AWS 호스팅)</td>
                </tr>
                <tr>
                  <td className="p-2.5 font-medium text-stone-300">Vercel Inc.</td>
                  <td className="p-2.5">프런트엔드 웹 호스팅, 엣지 라우팅 및 서버리스 함수 서빙</td>
                  <td className="p-2.5 text-stone-300">iad1 (미국 워싱턴 D.C. / 글로벌 엣지 네트워크)</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-stone-500">
            * 데이터센터가 국내에 위치하더라도 수탁사가 국외 법인이거나 글로벌 백업망을 사용하는 경우 국외 이전 고지 대상에 포함될 수 있으며, 구체적 법정 고지 사항은 아래 4절에 따릅니다.
          </p>
        </section>

        {/* 4. 개인정보의 국외 이전 고지 (개인정보보호법 제28조의8 제2항에 따른 법정 고지) */}
        <section id="cross-border" className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <ShieldCheck className="w-4 h-4 text-amber-500" />
            4. 개인정보의 국외 이전 고지
          </h2>
          <p className="text-stone-300 leading-relaxed">
            회사는 서비스 제공 및 계약 이행을 위하여 필요한 범위 내에서 다음과 같이 개인정보를 국외로 이전(처리위탁 및 보관)하고 있습니다.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left border border-stone-800 rounded-lg overflow-hidden">
              <thead className="bg-stone-900/80 text-stone-300 font-medium">
                <tr>
                  <th className="p-2 border-b border-stone-800">이전받는 자</th>
                  <th className="p-2 border-b border-stone-800">이전 항목</th>
                  <th className="p-2 border-b border-stone-800">이전 국가/일시/방법</th>
                  <th className="p-2 border-b border-stone-800">이용 목적 및 보유 기간</th>
                  <th className="p-2 border-b border-stone-800">거부 방법 및 효과</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800/60 text-stone-400">
                <tr>
                  <td className="p-2 font-medium text-stone-300 align-top">
                    Google LLC<br />
                    <span className="text-[10px] text-stone-500">(Vertex AI)</span><br />
                    <span className="text-[10px] text-amber-400">google-cloud-compliance@google.com</span>
                  </td>
                  <td className="p-2 align-top">상담 질문 발화 및 대화 본문</td>
                  <td className="p-2 align-top">
                    미국 (us-central1, us-east5)<br />
                    상담 답변 요청 시 HTTPS 암호화 전송
                  </td>
                  <td className="p-2 align-top">
                    <strong>목적:</strong> AI 성찰 답변 생성 (모델 학습에 사용하지 않음)<br />
                    <strong>기간:</strong> AI 응답 생성 및 전송 완료 시 지체 없이 파기 (Google Cloud 서비스 계약에 따름)
                  </td>
                  <td className="p-2 align-top">
                    상담 이용 중단<br />
                    <span className="text-[10px] text-stone-500">(거부 시 AI 상담 서비스 이용이 제한됩니다)</span>
                  </td>
                </tr>
                <tr>
                  <td className="p-2 font-medium text-stone-300 align-top">
                    Supabase Inc.<br />
                    <span className="text-[10px] text-amber-400">privacy@supabase.io</span>
                  </td>
                  <td className="p-2 align-top">계정 식별자(UUID), 이메일, 닉네임, 크레딧 원장, 상담 대화록 및 저널</td>
                  <td className="p-2 align-top">
                    일본 (AWS ap-northeast-1 도쿄 리전) 및 미국 (법인 관리)<br />
                    데이터 저장 시 네트워크 암호화 전송
                  </td>
                  <td className="p-2 align-top">
                    <strong>목적:</strong> 사용자 인증, 세션 유지, 상담 데이터 암호화 보관<br />
                    <strong>기간:</strong> 본인 직접 삭제 시 즉시 파기
                  </td>
                  <td className="p-2 align-top">
                    서비스 이용 중단 및 상담 기록 직접 삭제<br />
                    <span className="text-[10px] text-stone-500">(거부 시 계정 기반 서비스 이용이 제한됩니다)</span>
                  </td>
                </tr>
                <tr>
                  <td className="p-2 font-medium text-stone-300 align-top">
                    Vercel Inc.<br />
                    <span className="text-[10px] text-amber-400">privacy@vercel.com</span>
                  </td>
                  <td className="p-2 align-top">접속 IP, 요청 헤더, 브라우저 쿠키/세션 정보</td>
                  <td className="p-2 align-top">
                    미국 (iad1 워싱턴 D.C. 리전 및 글로벌 엣지 네트워크)<br />
                    웹 서비스 접속 시 네트워크 전송
                  </td>
                  <td className="p-2 align-top">
                    <strong>목적:</strong> 웹 애플리케이션 호스팅 및 CDN 전송 최적화<br />
                    <strong>기간:</strong> Vercel 개인정보처리방침에 따른 운영 및 보안 목적 보존 후 파기
                  </td>
                  <td className="p-2 align-top">
                    서비스 접속 중단<br />
                    <span className="text-[10px] text-stone-500">(거부 시 웹 접속이 제한됩니다)</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="text-xs text-stone-400 leading-relaxed">
            ※ 본 국외 이전은 계약의 체결 및 이행에 필수적인 처리위탁 및 보관으로서 개인정보보호법 제28조의8 제1항 제3호 및 제2항에 따라 개인정보처리방침을 통해 공개함으로써 별도 동의 절차를 갈음합니다.
          </p>
        </section>

        {/* 5. 자동 수집 장치(브라우저 저장소) 이용 및 거부 방법 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Eye className="w-4 h-4 text-amber-500" />
            5. 방문 통계를 위한 브라우저 저장소 이용 및 거부 방법
          </h2>
          <p className="text-stone-300 leading-relaxed">
            서비스는 방문자수 및 재방문 현황을 집계하기 위해 이용자 브라우저의 저장소(localStorage,
            sessionStorage)에 <strong className="text-stone-200">무작위로 생성된 방문자 식별자</strong>를 저장합니다.
            이 식별자는 이용자 브라우저 식별을 위한 가명정보로서 이름·이메일 등 직접 식별 정보는 포함되지 않으며, 서버에는 원문이 아닌
            서버 솔트(pepper)와 결합된 일방향 해시 형태로 가명처리되어 기록됩니다.
          </p>
          <ul className="list-disc pl-5 space-y-1.5 text-stone-400 text-xs">
            <li>
              <strong className="text-stone-200">이용 목적:</strong> 같은 브라우저의 재방문 여부 판단, 일별 방문자수
              및 재방문 횟수 집계
            </li>
            <li>
              <strong className="text-stone-200">거부 방법:</strong> 브라우저 설정에서 사이트 데이터 저장을 차단하거나,
              브라우저의 시크릿/사생활 보호 모드를 이용하시면 저장되지 않습니다. 저장을 차단하더라도 상담 이용에는
              제한이 없습니다.
            </li>
            <li>
              <strong className="text-stone-200">삭제 방법:</strong> 브라우저의 방문 기록·사이트 데이터 삭제 기능으로
              언제든 제거할 수 있습니다.
            </li>
            <li>
              <strong className="text-stone-200">보유 기간:</strong> 서버에 기록된 방문 로그는 수집일로부터 180일이
              지나면 파기되며, 회원 탈퇴 시 해당 방문 기록과 회원 계정의 연결은 즉시 분리됩니다.
            </li>
          </ul>
        </section>

        {/* 6. 이용자의 권리 및 행사 방법 (A29 기록 열람 및 즉시 삭제) */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <Trash2 className="w-4 h-4 text-amber-500" />
            6. 이용자의 권리 (열람·삭제·동의철회)
          </h2>
          <div className="space-y-2 text-stone-300">
            <p>
              1. <strong>상담 기록 직접 삭제권 (A29):</strong> 이용자는 상담 완료 화면에서 <strong>[이 상담 기록 삭제]</strong> 버튼을 클릭하여 본인의 상담 대화록, 도출된 괘 데이터, 성찰 저널 및 크레딧 작업 스냅샷을 즉시 영구 파기할 수 있습니다.
            </p>
            <p>
              2. <strong>동의 철회 (A23):</strong> 이용자는 아래의 전용 기능을 통하거나 고객지원 센터를 통해 서비스 이용약관 및 개인정보 처리에 대한 동의를 언제든지 철회할 수 있습니다.
            </p>
            <p>
              3. <strong>권리 행사 창구:</strong> 데이터 열람·삭제 등 권리 행사는 서비스 내 상담 완료 화면 또는 <Link href="/contact" className="text-amber-400 underline">고객지원 센터</Link>를 통해 신청하실 수 있습니다.
            </p>
          </div>

          <ConsentWithdrawSection />
        </section>

        {/* 7. 개인정보 보호책임자 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <ShieldCheck className="w-4 h-4 text-amber-500" />
            7. 개인정보 보호책임자
          </h2>
          <p className="text-stone-300 leading-relaxed">
            개인정보 보호 관련 문의, 의견 수렴 및 불만 처리는 아래의 보호책임자 창구로 접수해 주시기 바랍니다:
          </p>
          <div className="p-3 rounded-lg bg-stone-900/60 border border-stone-800 text-xs text-stone-400 space-y-1">
            <p>• 소속: 리인베스트먼트</p>
            <p>• 개인정보보호책임자: 이승준</p>
            <p>• 사업장 소재지: 서울특별시 (상세 주소는 고객지원 문의)</p>
            <p>• 연락처: <a href="mailto:casareborgia@gmail.com" className="text-amber-400 underline">casareborgia@gmail.com</a> 또는 <Link href="/contact" className="text-amber-400 underline">고객지원 센터(문의 접수)</Link>를 통해 접수</p>
          </div>
        </section>

        {/* 8. 개인정보처리방침 개정 이력 */}
        <section className="space-y-3">
          <h2 className="text-base font-semibold text-stone-100 flex items-center gap-2 border-b border-stone-800 pb-2">
            <ShieldCheck className="w-4 h-4 text-amber-500" />
            8. 개인정보처리방침 개정 이력
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse border border-stone-800 text-xs text-stone-400">
              <thead>
                <tr className="bg-stone-900 text-stone-300">
                  <th className="p-2.5 border border-stone-800 w-28">버전</th>
                  <th className="p-2.5 border border-stone-800 w-32">시행일</th>
                  <th className="p-2.5 border border-stone-800">주요 개정 내용</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-800">
                {LEGAL_REVISIONS.map((item) => (
                  <tr key={item.version} className="hover:bg-stone-900/30">
                    <td className="p-2.5 font-medium text-stone-200 border border-stone-800">{item.version}</td>
                    <td className="p-2.5 text-stone-400 border border-stone-800">{item.effectiveDate}</td>
                    <td className="p-2.5 text-stone-300 border border-stone-800">
                      <div className="font-medium text-stone-200">{item.summary}</div>
                      <ul className="list-disc pl-4 mt-1 space-y-0.5 text-[11px] text-stone-400">
                        {item.changes.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
