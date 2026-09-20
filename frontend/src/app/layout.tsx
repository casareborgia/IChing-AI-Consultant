import type { Metadata } from 'next';
import './globals.css';
import { AppProviders } from '@/components/providers/AppProviders';
import { Analytics } from '@vercel/analytics/react';

export const metadata: Metadata = {
  title: '마음지기 | 주역 심층 AI 상담 (I-Ching Oracle)',
  description: '마음지기 - 변화의 원리를 거울삼아 마주한 질문을 깊이 들여다보는 주역 기반 AI 심층 성찰 상담 서비스',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko" className="dark bg-stone-950 text-stone-100">
      <head>
        <link
          rel="stylesheet"
          as="style"
          crossOrigin=""
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css"
        />
      </head>
      <body className="min-h-screen bg-stone-950 font-sans antialiased">
        <AppProviders>{children}</AppProviders>
        <Analytics />
      </body>
    </html>
  );
}
