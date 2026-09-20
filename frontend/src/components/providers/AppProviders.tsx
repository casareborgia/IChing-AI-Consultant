'use client';

import React from 'react';
import { AuthProvider } from '@/context/AuthContext';
import { VisitTracker } from '@/components/analytics/VisitTracker';

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      {/* 방문자수·재방문 횟수 집계용 1st-party ping. 화면에는 아무 것도 그리지 않는다. */}
      <VisitTracker />
      {children}
    </AuthProvider>
  );
}
