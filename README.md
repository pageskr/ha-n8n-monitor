# n8n Monitor for Home Assistant

[![GitHub Release](https://img.shields.io/github/v/release/pages/ha-n8n-monitor)](https://github.com/pages/ha-n8n-monitor/releases)
[![License](https://img.shields.io/github/license/pages/ha-n8n-monitor)](LICENSE)

n8n 워크플로우 자동화 플랫폼을 Home Assistant에서 모니터링하는 커스텀 통합입니다.

## 주요 기능

- **복수 n8n 서버 지원**: 여러 n8n 인스턴스를 동시에 모니터링
- **실시간 모니터링**: 워크플로우 상태 및 실행 통계
- **상세한 실행 로그**: 성공/실패/진행중/취소된 실행 추적
- **커스터마이징 가능**: 수집 주기, 시간 창, 데이터 제한 설정
- **한국어/영어 지원**: 다국어 UI 제공

## 설치 방법

### HACS를 통한 설치 (권장)

1. HACS에서 "Custom repositories" 추가
2. Repository URL: `https://github.com/pages/ha-n8n-monitor`
3. Category: `Integration` 선택
4. 설치 후 Home Assistant 재시작

### 수동 설치

1. 이 저장소의 최신 릴리스 다운로드
2. `custom_components/n8n_monitor` 폴더를 Home Assistant의 `config/custom_components/` 디렉토리에 복사
3. Home Assistant 재시작

## 설정

1. Home Assistant 설정 → 기기 & 서비스 → 통합 추가
2. "n8n Monitor" 검색 및 선택
3. 필요한 정보 입력:
   - **n8n API URL**: n8n 인스턴스 주소 (예: `https://n8n.example.com`)
   - **API Key**: n8n API 키 (`X-N8N-API-KEY`)
   - **기기 이름**: 선택사항 (예: `n8n-Production`)

## 센서

각 n8n 인스턴스마다 2개의 센서가 생성됩니다:

### 워크플로우 센서
- 엔티티 ID: `sensor.{device_name}_workflows`
- 상태: 전체 워크플로우 수
- 속성:
  - `items`: 각 워크플로우의 상세 정보
  - `total`: 총 워크플로우 수
  - `generated_at`: 데이터 생성 시간
  - `execution_hours`: 실행 통계 시간 창

### 실행 센서
- 엔티티 ID: `sensor.{device_name}_executions`
- 상태: 설정된 시간 창 내 총 실행 수
- 속성:
  - `success`: 성공한 실행 (count, items)
  - `failed`: 실패한 실행 (count, items, error)
  - `running`: 실행 중 (count)
  - `canceled`: 취소됨 (count)
  - `window`: 통계 시간 창
  - `generated_at`: 데이터 생성 시간

## 옵션 설정

통합 옵션에서 다음 항목을 조정할 수 있습니다:

- **업데이트 간격**: 60-3600초 (기본: 300초)
- **실행 창**: 1-168시간 (기본: 6시간)
- **페이지 크기**: 10-500 (기본: 100)
- **속성 최대 항목**: 10-200 (기본: 50)

## 대시보드 예제

### 기본 정보 카드
```yaml
type: entities
title: n8n 상태
entities:
  - entity: sensor.n8n_production_workflows
    name: 워크플로우
  - entity: sensor.n8n_production_executions
    name: 실행 (6시간)
```

### 실행 통계
```yaml
type: markdown
title: n8n 실행 통계
content: |
  **시간 창**: {{ state_attr('sensor.n8n_production_executions', 'window') }}
  
  - ✅ 성공: {{ state_attr('sensor.n8n_production_executions', 'success').count }}
  - ❌ 실패: {{ state_attr('sensor.n8n_production_executions', 'failed').count }}
  - 🔄 진행중: {{ state_attr('sensor.n8n_production_executions', 'running').count }}
  - ⏹️ 취소됨: {{ state_attr('sensor.n8n_production_executions', 'canceled').count }}
```

### 최근 실패 목록
```yaml
type: markdown
title: 최근 실패한 실행
content: >
  {% set failed = state_attr('sensor.n8n_production_executions', 'failed').items %}
  {% if failed and failed|length > 0 %}
  | 워크플로우 | 시작 시간 | 오류 |
  |------------|----------|------|
  {% for item in failed[:5] %}
  | {{ item.workflowId }} | {{ item.startedAt | as_timestamp | timestamp_custom('%m/%d %H:%M') }} | {{ item.error[:50] }}... |
  {% endfor %}
  {% else %}
  최근 실패한 실행이 없습니다.
  {% endif %}
```

## 자동화 예제

### 실행 실패 알림
```yaml
automation:
  - alias: "n8n 실행 실패 알림"
    trigger:
      - platform: template
        value_template: >
          {{ state_attr('sensor.n8n_production_executions', 'failed').count > 0 }}
    action:
      - service: notify.mobile_app
        data:
          title: "n8n 실행 실패"
          message: >
            {{ state_attr('sensor.n8n_production_executions', 'failed').count }}개의 
            워크플로우 실행이 실패했습니다.
```

### 높은 실패율 경고
```yaml
automation:
  - alias: "n8n 높은 실패율 경고"
    trigger:
      - platform: template
        value_template: >
          {% set total = states('sensor.n8n_production_executions') | int(0) %}
          {% set failed = state_attr('sensor.n8n_production_executions', 'failed').count | int(0) %}
          {{ total > 0 and (failed / total) > 0.1 }}
    action:
      - service: persistent_notification.create
        data:
          title: "n8n 높은 실패율"
          message: >
            실패율이 10%를 초과했습니다!
            전체: {{ states('sensor.n8n_production_executions') }}
            실패: {{ state_attr('sensor.n8n_production_executions', 'failed').count }}
```

## 보안 고려사항

1. **HTTPS 사용**: n8n 인스턴스는 반드시 HTTPS를 사용해야 합니다
2. **API 키 보호**: API 키는 Home Assistant의 암호화된 저장소에 저장됩니다
3. **최소 권한**: n8n API 키는 읽기 권한만 있으면 충분합니다
4. **네트워크 보안**: Home Assistant에서 n8n으로의 아웃바운드 연결만 필요

## 문제 해결

### "Cannot connect" 오류
- n8n URL이 올바른지 확인
- API 키가 유효한지 확인
- n8n 인스턴스가 실행 중인지 확인
- 방화벽 설정 확인

### 데이터가 표시되지 않음
- n8n Public API가 활성화되어 있는지 확인
- API 키에 충분한 권한이 있는지 확인

### 성능 문제
- 업데이트 간격을 늘리기 (예: 300초 → 600초)
- 속성 최대 항목 수 줄이기
- 페이지 크기 조정

## 라이선스

이 프로젝트는 MIT 라이선스 하에 제공됩니다.

## 기여

이슈 및 풀 리퀘스트는 언제나 환영합니다!

## 제작자

[Pages in Korea (pages.kr)](https://pages.kr)
