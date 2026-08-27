#!/usr/bin/env python3
"""
보안 취약점 스캐너 (Security Scanner)
- 하드코딩된 시크릿/토큰 검사
- SQL 인젝션 패턴 검사
- CORS 및 API 보안 설정 검사
- RLS / DB 접근 제어 검사
- 프론트엔드 환경변수 보안 검사
- .gitignore 보안 검사
"""

import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[4]

def scan_secrets():
    issues = []
    secret_patterns = [
        (r"(?i)(api[_-]?key|secret[_-]?key|password|service[_-]?role)\s*=\s*['\"][A-Za-z0-9_\-\.]{15,}['\"]", "하드코딩된 시크릿 키/패스워드 의심 패턴"),
        (r"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+", "JWT 토큰 (Supabase anon/service_role 등) 하드코딩"),
        (r"AIza[0-9A-Za-z-_]{35}", "Google API Key 하드코딩"),
        (r"sk-[a-zA-Z0-9]{20,}", "OpenAI API Key 하드코딩")
    ]
    
    ignore_dirs = {'.venv', 'node_modules', '.git', '.next', '__pycache__', 'dist', 'build'}
    
    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix in ['.py', '.ts', '.tsx', '.js', '.json', '.env', '.env.local', '.sql']:
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    rel_path = file_path.relative_to(ROOT_DIR)
                    
                    # scripts/seed_supabase_rest.py 등 임시 스크립트 제외 필터링 또는 경고
                    for pattern, desc in secret_patterns:
                        matches = re.finditer(pattern, content)
                        for match in matches:
                            # .env.example 은 제외
                            if 'example' in str(rel_path).lower():
                                continue
                            issues.append({
                                'type': 'HARDCODED_SECRET',
                                'severity': 'HIGH' if 'service_role' in desc or 'JWT' in desc else 'MEDIUM',
                                'file': str(rel_path),
                                'description': desc,
                                'matched_snippet': match.group(0)[:30] + '...'
                            })
                except Exception as e:
                    pass
    return issues

def scan_cors_and_api():
    issues = []
    main_api = ROOT_DIR / "api" / "main.py"
    if main_api.exists():
        content = main_api.read_text(encoding='utf-8', errors='ignore')
        if 'allow_origins=["*"]' in content and 'allow_credentials=True' in content:
            issues.append({
                'type': 'CORS_MISCONFIGURATION',
                'severity': 'HIGH',
                'file': 'api/main.py',
                'description': 'CORS allow_origins=["*"] 와 allow_credentials=True가 동시 사용될 경우 브라우저 표준 위반 및 CSRF/Credential 노출 위험'
            })
        if 'X-Content-Type-Options' not in content:
            issues.append({
                'type': 'MISSING_SECURITY_HEADERS',
                'severity': 'MEDIUM',
                'file': 'api/main.py',
                'description': 'OWASP 권장 보안 헤더 (X-Content-Type-Options, X-Frame-Options 등)가 누락되어 있습니다.'
            })
        if 'req.user_id and c_session.user_id != req.user_id' in content:
            issues.append({
                'type': 'BOLA_BYPASS_RISK',
                'severity': 'HIGH',
                'file': 'api/main.py',
                'description': 'req.user_id 누락 시 세션 소유권 검사가 우회될 수 있는 취약점이 있습니다.'
            })
    return issues

def scan_sql_injection():
    issues = []
    ignore_dirs = {'.venv', 'node_modules', '.git', '.next', '__pycache__'}
    sql_patterns = [
        (r'execute\(\s*f["\'].*SELECT.*\{.*\}', "f-string을 사용한 동적 SQL 쿼리 생성 (SQL Injection 위험)"),
        (r'execute\(\s*f["\'].*INSERT.*\{.*\}', "f-string을 사용한 동적 INSERT 쿼리 생성 (SQL Injection 위험)"),
        (r'execute\(\s*f["\'].*UPDATE.*\{.*\}', "f-string을 사용한 동적 UPDATE 쿼리 생성 (SQL Injection 위험)"),
        (r'execute\(\s*f["\'].*DELETE.*\{.*\}', "f-string을 사용한 동적 DELETE 쿼리 생성 (SQL Injection 위험)")
    ]
    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in files:
            file_path = Path(root) / file
            if file_path.suffix == '.py':
                # scripts 내부의 덤프 생성기는 제외 (단, api/ 및 core/는 철저 점검)
                rel_path = file_path.relative_to(ROOT_DIR)
                if str(rel_path).startswith('scripts/'):
                    continue
                try:
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    for pattern, desc in sql_patterns:
                        if re.search(pattern, content):
                            issues.append({
                                'type': 'SQL_INJECTION_RISK',
                                'severity': 'HIGH',
                                'file': str(rel_path),
                                'description': desc
                            })
                except Exception:
                    pass
    return issues

def scan_gitignore():
    issues = []
    gitignore_path = ROOT_DIR / ".gitignore"
    if not gitignore_path.exists():
        issues.append({
            'type': 'MISSING_GITIGNORE',
            'severity': 'CRITICAL',
            'file': '.gitignore',
            'description': '.gitignore 파일이 존재하지 않습니다.'
        })
    else:
        content = gitignore_path.read_text(encoding='utf-8')
        required_ignores = ['.env', '.env.local', '*.pem', '*.key', 'service_account.json']
        for item in required_ignores:
            if item not in content:
                issues.append({
                    'type': 'INCOMPLETE_GITIGNORE',
                    'severity': 'MEDIUM',
                    'file': '.gitignore',
                    'description': f'{item} 패턴이 .gitignore에 누락되어 민감 정보가 Git에 커밋될 위험이 있습니다.'
                })
    return issues

def scan_frontend_env():
    issues = []
    fe_env = ROOT_DIR / "frontend" / ".env.local"
    if fe_env.exists():
        content = fe_env.read_text(encoding='utf-8', errors='ignore')
        if 'SERVICE_ROLE' in content.upper() and 'NEXT_PUBLIC_' in content:
            issues.append({
                'type': 'EXPOSED_SERVICE_ROLE_KEY',
                'severity': 'CRITICAL',
                'file': 'frontend/.env.local',
                'description': '클라이언트에 노출되는 NEXT_PUBLIC_ 변수에 Supabase Service Role Key가 포함되어 있습니다.'
            })
    return issues

def main():
    print("=" * 60)
    print(" 주역 상담 앱 (I-Ching Oracle) 보안 취약점 점검 스캐너 ")
    print("=" * 60)
    
    all_issues = []
    all_issues.extend(scan_secrets())
    all_issues.extend(scan_cors_and_api())
    all_issues.extend(scan_sql_injection())
    all_issues.extend(scan_gitignore())
    all_issues.extend(scan_frontend_env())
    
    critical_count = sum(1 for i in all_issues if i['severity'] == 'CRITICAL')
    high_count = sum(1 for i in all_issues if i['severity'] == 'HIGH')
    medium_count = sum(1 for i in all_issues if i['severity'] == 'MEDIUM')
    
    print(f"\n[점검 결과 통계]")
    print(f"  - CRITICAL (치명적) : {critical_count}건")
    print(f"  - HIGH     (높음)   : {high_count}건")
    print(f"  - MEDIUM   (보통)   : {medium_count}건")
    print(f"  - 총 발견 이슈     : {len(all_issues)}건\n")
    
    if all_issues:
        print("[세부 취약점 목록]")
        for idx, issue in enumerate(all_issues, 1):
            print(f"{idx}. [{issue['severity']}] {issue['type']} in {issue['file']}")
            print(f"   설명: {issue['description']}")
            if 'matched_snippet' in issue:
                print(f"   스니펫: {issue['matched_snippet']}")
            print()
    else:
        print(" 취약점이 발견되지 않았습니다. 안전합니다.")
        
    print("=" * 60)

if __name__ == '__main__':
    main()
