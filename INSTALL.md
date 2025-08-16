# 설치 가이드

## 요구사항

- Home Assistant 2024.1.0 이상
- n8n 인스턴스 (0.150.0 이상 권장)
- n8n API 키

## n8n API 키 생성

1. n8n 관리자로 로그인
2. 설정 → API 설정으로 이동
3. "Create API Key" 클릭
4. 키 이름 입력 (예: "HomeAssistant")
5. 생성된 API 키 복사 및 안전하게 보관

## Home Assistant 설치

### 방법 1: HACS (권장)

1. HACS 열기
2. 메뉴 → Custom repositories
3. Repository 추가:
   - URL: `https://github.com/pages/ha-n8n-monitor`
   - Category: Integration
4. "ADD" 클릭
5. HACS에서 "n8n Monitor" 검색
6. "DOWNLOAD" 클릭
7. Home Assistant 재시작

### 방법 2: 수동 설치

1. 최신 릴리스 다운로드
2. 압축 해제
3. `custom_components/n8n_monitor` 폴더를 복사
4. Home Assistant config 디렉토리에 붙여넣기:
   ```
   config/
   └── custom_components/
       └── n8n_monitor/
           ├── __init__.py
           ├── manifest.json
           ├── config_flow.py
           └── ... (기타 파일들)
   ```
5. Home Assistant 재시작

## 통합 설정

1. 설정 → 기기 & 서비스 → 통합 추가
2. "n8n Monitor" 검색
3. 정보 입력:
   - **n8n API URL**: `https://your-n8n.com`
   - **API Key**: 위에서 생성한 키
   - **기기 이름**: 원하는 이름 (선택사항)

## 복수 서버 추가

여러 n8n 서버를 모니터링하려면:

1. 통합 추가를 다시 클릭
2. 다른 서버 정보 입력
3. 각 서버는 독립적인 기기로 등록됨

## 문제 해결

### API 연결 실패

1. URL이 정확한지 확인 (https:// 포함)
2. API 키가 유효한지 확인
3. n8n이 실행 중인지 확인
4. 방화벽/네트워크 설정 확인

### Public API 비활성화 시

n8n이 Public API를 비활성화한 경우, 자동으로 REST API로 폴백합니다.

### 로그 확인

문제 발생 시 Home Assistant 로그 확인:
```
설정 → 시스템 → 로그
```

`n8n_monitor` 관련 오류 메시지 확인

## 업데이트

### HACS 사용 시
1. HACS → Integrations
2. n8n Monitor 찾기
3. 업데이트 가능 시 "UPDATE" 버튼 표시
4. 클릭 후 Home Assistant 재시작

### 수동 설치 시
1. 최신 버전 다운로드
2. 기존 파일 덮어쓰기
3. Home Assistant 재시작
