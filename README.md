# n8n Monitor for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/pageskr/ha-n8n-monitor)](https://github.com/pageskr/ha-n8n-monitor/releases)
[![License](https://img.shields.io/github/license/pageskr/ha-n8n-monitor)](LICENSE)

Home Assistant에서 n8n 워크플로우 자동화 플랫폼을 모니터링하는 커스텀 통합입니다.

## 📋 목차

- [주요 기능](#-주요-기능)
- [요구사항](#-요구사항)
- [설치 방법](#-설치-방법)
- [설정](#-설정)
- [센서](#-센서)
- [옵션 설정](#-옵션-설정)
- [대시보드 예제](#-대시보드-예제)
- [자동화 예제](#-자동화-예제)
- [문제 해결](#-문제-해결)
- [개발자 정보](#-개발자-정보)

## 🌟 주요 기능

- **복수 n8n 서버 지원**: 여러 n8n 인스턴스를 동시에 모니터링
- **실시간 모니터링**: 워크플로우 상태 및 실행 통계
- **상세한 실행 로그**: 성공/실패/진행중/취소된 실행 추적
- **유연한 연결 옵션**: HTTP/HTTPS, 포트 지정, SSL 검증 옵션
- **커스터마이징 가능**: 수집 주기, 시간 창, 데이터 제한, 타임아웃 설정
- **서비스 기반 통합**: Home Assistant에서 서비스로 표시
- **한국어/영어 지원**: 다국어 UI 제공

## 📌 요구사항

- Home Assistant 2024.1.0 이상
- n8n 인스턴스 (0.150.0 이상 권장)
- n8n API 키

## 🔧 설치 방법

### HACS를 통한 설치 (권장)

1. HACS 열기
2. 메뉴 → Custom repositories
3. Repository 추가:
   - URL: `https://github.com/pageskr/ha-n8n-monitor`
   - Category: `Integration`
4. "ADD" 클릭
5. HACS에서 "n8n Monitor" 검색
6. "DOWNLOAD" 클릭
7. Home Assistant 재시작

### 수동 설치

1. 최신 릴리스 다운로드
2. `custom_components/n8n_monitor` 폴더를 Home Assistant의 `config/custom_components/` 디렉토리에 복사
3. Home Assistant 재시작

## ⚙️ 설정

### n8n API 키 생성

1. n8n 관리자로 로그인
2. 설정 → API 설정으로 이동
3. "Create API Key" 클릭
4. 키 이름 입력 (예: "HomeAssistant")
5. 생성된 API 키 복사 및 안전하게 보관

### 통합 추가

1. Home Assistant 설정 → 기기 & 서비스 → 통합 추가
2. "n8n Monitor" 검색 및 선택
3. 필요한 정보 입력:
   - **n8n API URL**: n8n 인스턴스 주소 
     - 예: `http://n8n:5678` (Docker 내부)
     - 예: `https://n8n.example.com` (외부 도메인)
   - **API Key**: n8n API 키 (`X-N8N-API-KEY`)
   - **기기 이름**: 선택사항 (예: `n8n-Production`)
   - **SSL 인증서 검증**: 자체 서명 인증서 사용 시 비활성화

## 📊 센서

각 n8n 인스턴스는 하나의 서비스로 등록되며, 다음 3개의 센서가 생성됩니다:

### Info 센서
- 엔티티 ID: `sensor.{device_name}_info`
- 상태: n8n URL
- 속성:
  - `url`: n8n 인스턴스 URL
  - `device_name`: 설정된 기기 이름

### 워크플로우 센서
- 엔티티 ID: `sensor.{device_name}_workflows`
- 상태: 전체 워크플로우 수
- 속성:
  - `items`: 각 워크플로우의 상세 정보
    - `id`: 워크플로우 ID
    - `name`: 워크플로우 이름
    - `active`: 활성화 상태
    - `last_execution_time`: 마지막 실행 시간
    - `recent_execution`: 최근 실행 통계 (상태별 카운트)
  - `total`: 총 워크플로우 수
  - `active`: 활성 워크플로우 수
  - `generated_at`: 데이터 생성 시간
  - `execution_hours`: 실행 통계 시간 창

### 실행 센서
- 엔티티 ID: `sensor.{device_name}_executions`
- 상태: 설정된 시간 창 내 총 실행 수
- 속성:
  - `success`: 성공한 실행
    - `count`: 총 개수
    - `items`: 상세 목록 (최대 N개)
  - `error`: 실패한 실행
    - `count`: 총 개수
    - `items`: 상세 목록 (에러 메시지 포함)
  - `running`: 실행 중
    - `count`: 총 개수
    - `items`: 상세 목록
  - `canceled`: 취소됨
    - `count`: 총 개수
    - `items`: 상세 목록
  - `unknown`: 알 수 없음
    - `count`: 총 개수
    - `items`: 상세 목록
  - `window`: 통계 시간 창
  - `generated_at`: 데이터 생성 시간

## 🛠️ 옵션 설정

통합 옵션에서 다음 항목을 조정할 수 있습니다:

| 옵션 | 설명 | 기본값 | 범위 |
|------|------|--------|------|
| 업데이트 간격 | 데이터 업데이트 주기 | 300초 | 60-3600초 |
| 실행 창 | 실행 통계 시간 범위 | 6시간 | 1-168시간 |
| 페이지 크기 | API 요청당 항목 수 | 100 | 10-250 |
| 속성 최대 항목 | 속성에 저장할 최대 실행 수 | 50 | 10-200 |
| 요청 타임아웃 | API 요청 타임아웃 | 60초 | 10-300초 |
| SSL 인증서 검증 | SSL 인증서 검증 여부 | 활성 | 활성/비활성 |

## 📱 대시보드 예제

### 기본 정보 카드
```yaml
type: entities
title: n8n 상태
entities:
  - entity: sensor.n8n_production_info
    name: 서버 URL
  - entity: sensor.n8n_production_workflows
    name: 워크플로우
  - entity: sensor.n8n_production_executions
    name: 실행 (6시간)
```

### 실행 통계 카드
```yaml
type: markdown
title: n8n 실행 통계
content: |
  **시간 창**: {{ state_attr('sensor.n8n_production_executions', 'window') }}
  
  - ✅ 성공: {{ state_attr('sensor.n8n_production_executions', 'success').count }}
  - ❌ 실패: {{ state_attr('sensor.n8n_production_executions', 'error').count }}
  - 🔄 진행중: {{ state_attr('sensor.n8n_production_executions', 'running').count }}
  - ⏹️ 취소됨: {{ state_attr('sensor.n8n_production_executions', 'canceled').count }}
  
  **활성 워크플로우**: {{ state_attr('sensor.n8n_production_workflows', 'active') }} / {{ states('sensor.n8n_production_workflows') }}
```

### 최근 실패 목록
```yaml
type: markdown
title: 최근 실패한 실행
content: >
  {% set failed = state_attr('sensor.n8n_production_executions', 'error').items %}
  {% if failed and failed|length > 0 %}
  | 워크플로우 | 시작 시간 | 오류 |
  |------------|----------|------|
  {% for item in failed[:5] %}
  | {{ item.workflowName }} | {{ item.startedAt | as_timestamp | timestamp_custom('%m/%d %H:%M') }} | {{ item.error[:50] }}... |
  {% endfor %}
  {% else %}
  최근 실패한 실행이 없습니다.
  {% endif %}
```

### 워크플로우 활동 상태
```yaml
type: markdown
title: 워크플로우 활동
content: >
  {% set workflows = state_attr('sensor.n8n_production_workflows', 'items') %}
  {% if workflows %}
  | 이름 | 상태 | 최근 성공 | 최근 실패 |
  |------|------|-----------|-----------|
  {% for wf in workflows[:10] %}
  | {{ wf.name }} | {{ '🟢' if wf.active else '🔴' }} | {{ wf.recent_execution.success }} | {{ wf.recent_execution.error }} |
  {% endfor %}
  {% endif %}
```

## 🤖 자동화 예제

### 실행 실패 알림
```yaml
automation:
  - alias: "n8n 실행 실패 알림"
    trigger:
      - platform: state
        entity_id: sensor.n8n_production_executions
        attribute: error.count
    condition:
      - condition: template
        value_template: >
          {{ trigger.to_state.attributes.error.count > 0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "n8n 실행 실패"
          message: >
            {{ trigger.to_state.attributes.error.count }}개의 
            워크플로우 실행이 실패했습니다.
```

### 높은 실패율 경고
```yaml
automation:
  - alias: "n8n 높은 실패율 경고"
    trigger:
      - platform: time_pattern
        minutes: "/10"
    condition:
      - condition: template
        value_template: >
          {% set total = states('sensor.n8n_production_executions') | int(0) %}
          {% set failed = state_attr('sensor.n8n_production_executions', 'error').count | int(0) %}
          {{ total > 10 and (failed / total) > 0.1 }}
    action:
      - service: persistent_notification.create
        data:
          title: "n8n 높은 실패율"
          message: >
            실패율이 10%를 초과했습니다!
            전체: {{ states('sensor.n8n_production_executions') }}
            실패: {{ state_attr('sensor.n8n_production_executions', 'error').count }}
```

### 비활성 워크플로우 알림
```yaml
automation:
  - alias: "n8n 비활성 워크플로우 확인"
    trigger:
      - platform: time
        at: "09:00:00"
    condition:
      - condition: template
        value_template: >
          {% set total = states('sensor.n8n_production_workflows') | int(0) %}
          {% set active = state_attr('sensor.n8n_production_workflows', 'active') | int(0) %}
          {{ total > 0 and active < total }}
    action:
      - service: notify.mobile_app
        data:
          title: "n8n 비활성 워크플로우"
          message: >
            {{ states('sensor.n8n_production_workflows') | int - 
               state_attr('sensor.n8n_production_workflows', 'active') | int }}개의 
            워크플로우가 비활성 상태입니다.
```

## 🔍 문제 해결

### 연결 문제

#### "Cannot connect" 오류
- n8n URL이 올바른지 확인 (프로토콜 포함: http:// 또는 https://)
- API 키가 유효한지 확인
- n8n 인스턴스가 실행 중인지 확인
- 방화벽/네트워크 설정 확인

#### Docker 네트워크 문제
Docker 환경에서 DNS 해결 문제가 발생하는 경우:

1. **IP 주소 사용**
   ```bash
   docker inspect n8n | grep IPAddress
   ```
   URL에 `http://172.17.0.3:5678` 형식으로 입력

2. **Docker Compose 네트워크 설정**
   ```yaml
   services:
     homeassistant:
       networks:
         - n8n_network
     n8n:
       networks:
         - n8n_network
   
   networks:
     n8n_network:
       driver: bridge
   ```

3. **호스트 네트워크 사용**
   - URL에 `http://host.docker.internal:5678` 시도 (Docker Desktop)
   - 또는 `http://172.17.0.1:5678` (Linux Docker)

### SSL 인증서 문제
- 자체 서명 인증서 사용 시 "SSL 인증서 검증" 옵션 비활성화
- 인증서가 만료되지 않았는지 확인

### 데이터 수집 문제

#### 데이터가 표시되지 않음
- n8n API가 활성화되어 있는지 확인
- API 키에 충분한 권한이 있는지 확인
- Home Assistant 로그 확인: 설정 → 시스템 → 로그

#### 성능 문제
- 업데이트 간격을 늘리기 (예: 300초 → 600초)
- 속성 최대 항목 수 줄이기
- 페이지 크기 조정
- 요청 타임아웃 증가

### 로그 레벨 설정
`configuration.yaml`에 추가:
```yaml
logger:
  default: info
  logs:
    custom_components.n8n_monitor: debug
```

## 🧩 통합 구조

```
custom_components/n8n_monitor/
├── __init__.py          # 통합 초기화
├── api.py               # n8n API 클라이언트
├── config_flow.py       # UI 설정 플로우
├── const.py             # 상수 정의
├── coordinator.py       # 데이터 업데이트 코디네이터
├── manifest.json        # 통합 메타데이터
├── sensor.py            # 센서 엔티티
├── strings.json         # UI 문자열
└── translations/        # 번역 파일
    ├── en.json         # 영어
    └── ko.json         # 한국어
```

## 👨‍💻 개발자 정보

### 제작자
[Pages in Korea (pages.kr)](https://pages.kr)

### 기여
이슈 및 풀 리퀘스트는 언제나 환영합니다!

### 라이선스
이 프로젝트는 MIT 라이선스 하에 제공됩니다.

### 버전 히스토리

#### v1.2.0 (2024-12-21)
- **API 호출 최적화**: 실행 정보를 한 번만 가져와서 공유
- **서버 부하 감소**: 워크플로우와 실행 정보가 동일한 데이터 사용
- **성능 개선**: 불필요한 중복 API 호출 제거

#### v1.1.0 (2024-12-21)
- 서비스 기반 통합으로 변경
- 실행 상태 집계 개선
- n8n API 스펙 준수
- Docker 네트워크 지원 개선
- 활성 워크플로우 카운트 추가

#### v1.0.0 (2024-12-20)
- 초기 릴리스
