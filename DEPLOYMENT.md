# AWS 배포 가이드

이 문서는 Mattermost Bot을 AWS Elastic Beanstalk에 배포하고 CodePipeline으로 CI/CD 파이프라인을 구축하는 방법을 설명합니다.

## 아키텍처 개요

- **애플리케이션**: Flask 기반 Mattermost Bot
- **호스팅**: AWS Elastic Beanstalk (Python 3.11)
- **CI/CD**: AWS CodePipeline + CodeBuild
- **시크릿 관리**: AWS Systems Manager Parameter Store
- **소스 코드**: GitHub (또는 AWS CodeCommit)

## 사전 준비사항

1. AWS CLI 설치 및 구성
2. EB CLI 설치
3. GitHub 계정 (또는 AWS CodeCommit)
4. 필요한 API 키들

## Step 1: AWS Systems Manager에 시크릿 등록

환경 변수들을 AWS Systems Manager Parameter Store에 안전하게 저장합니다.

```bash
# Mattermost Token
aws ssm put-parameter \
    --name "/mattermost-bot/MATTERMOST_TOKEN" \
    --value "your_mattermost_token" \
    --type "SecureString" \
    --region us-east-1

# Gemini API Key
aws ssm put-parameter \
    --name "/mattermost-bot/GEMINI_API_KEY" \
    --value "your_gemini_api_key" \
    --type "SecureString" \
    --region us-east-1

# Weather API Key (선택사항)
aws ssm put-parameter \
    --name "/mattermost-bot/WEATHER_API_KEY" \
    --value "your_weather_api_key" \
    --type "SecureString" \
    --region us-east-1

# Giphy API Key (선택사항)
aws ssm put-parameter \
    --name "/mattermost-bot/GIPHY_API_KEY" \
    --value "your_giphy_api_key" \
    --type "SecureString" \
    --region us-east-1
```

## Step 2: Elastic Beanstalk 애플리케이션 생성

### 2.1 EB CLI 초기화

```bash
cd mattermost_bot
eb init
```

다음 옵션을 선택합니다:
- Region: `us-east-1`
- Application name: `Mattermost-Bot-SSAFY`
- Platform: `Python`
- Platform version: `Python 3.11`
- SSH: `No` (필요시 Yes)

### 2.2 환경 생성

```bash
eb create mattermost-bot-prod \
    --instance-type t3.micro \
    --region us-east-1 \
    --envvars FLASK_ENV=production
```

### 2.3 IAM 역할에 SSM 권한 추가

Elastic Beanstalk 인스턴스가 Parameter Store에 접근할 수 있도록 IAM 역할에 권한을 추가합니다.

1. AWS Console > IAM > Roles
2. `aws-elasticbeanstalk-ec2-role` 검색
3. "Attach policies" 클릭
4. `AmazonSSMReadOnlyAccess` 정책 추가

### 2.4 Systems Manager 파라미터를 환경 변수로 연결

`.ebextensions/03_ssm_parameters.config` 파일을 생성합니다:

```yaml
option_settings:
  aws:elasticbeanstalk:application:environment:
    MATTERMOST_TOKEN: '`{"Ref": "AWSEBParameterStoreMATTERMOSTTOKEN"}`'
    GEMINI_API_KEY: '`{"Ref": "AWSEBParameterStoreGEMINIAPIKEY"}`'
    WEATHER_API_KEY: '`{"Ref": "AWSEBParameterStoreWEATHERAPIKEY"}`'
    GIPHY_API_KEY: '`{"Ref": "AWSEBParameterStoreGIPHYAPIKEY"}`'

Resources:
  AWSEBParameterStoreMATTERMOSTTOKEN:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /mattermost-bot/MATTERMOST_TOKEN

  AWSEBParameterStoreGEMINIAPIKEY:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /mattermost-bot/GEMINI_API_KEY

  AWSEBParameterStoreWEATHERAPIKEY:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /mattermost-bot/WEATHER_API_KEY

  AWSEBParameterStoreGIPHYAPIKEY:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /mattermost-bot/GIPHY_API_KEY
```

또는 더 간단한 방법으로 Elastic Beanstalk 콘솔에서 직접 환경 변수를 설정할 수 있습니다:

```bash
eb setenv \
    MATTERMOST_TOKEN=$(aws ssm get-parameter --name "/mattermost-bot/MATTERMOST_TOKEN" --with-decryption --query "Parameter.Value" --output text) \
    GEMINI_API_KEY=$(aws ssm get-parameter --name "/mattermost-bot/GEMINI_API_KEY" --with-decryption --query "Parameter.Value" --output text) \
    WEATHER_API_KEY=$(aws ssm get-parameter --name "/mattermost-bot/WEATHER_API_KEY" --with-decryption --query "Parameter.Value" --output text) \
    GIPHY_API_KEY=$(aws ssm get-parameter --name "/mattermost-bot/GIPHY_API_KEY" --with-decryption --query "Parameter.Value" --output text)
```

## Step 3: 애플리케이션 배포 테스트

```bash
# 로컬 변경사항 커밋
git add .
git commit -m "Add AWS deployment configuration"

# Elastic Beanstalk에 배포
eb deploy
```

배포 후 상태 확인:

```bash
# 환경 상태 확인
eb status

# 로그 확인
eb logs

# 환경 URL 확인
eb open
```

## Step 4: AWS CodePipeline 설정

### 4.1 S3 버킷 생성 (Artifact 저장용)

```bash
aws s3 mb s3://mattermost-bot-pipeline-artifacts-$(aws sts get-caller-identity --query Account --output text) --region us-east-1
```

### 4.2 CodeBuild 프로젝트 생성

1. AWS Console > CodeBuild > Create project
2. 프로젝트 설정:
   - **Project name**: `mattermost-bot-build`
   - **Source provider**: GitHub (또는 CodeCommit)
   - **Repository**: 본인의 GitHub 저장소 선택
   - **Environment**:
     - Environment image: `Managed image`
     - Operating system: `Amazon Linux 2`
     - Runtime: `Standard`
     - Image: `aws/codebuild/amazonlinux2-x86_64-standard:5.0`
     - Service role: 새로 생성 또는 기존 역할 선택
   - **Buildspec**: `Use a buildspec file` (buildspec.yml)
   - **Artifacts**:
     - Type: `Amazon S3`
     - Bucket name: 위에서 생성한 S3 버킷

### 4.3 CodePipeline 생성

1. AWS Console > CodePipeline > Create pipeline
2. 파이프라인 설정:

   **Step 1: Choose pipeline settings**
   - Pipeline name: `Mattermost-Bot-Pipeline`
   - Service role: 새로 생성
   - Artifact store: 위에서 생성한 S3 버킷

   **Step 2: Add source stage**
   - Source provider: `GitHub (Version 2)` 또는 `AWS CodeCommit`
   - Repository: 본인의 저장소 선택
   - Branch: `main` (또는 원하는 브랜치)
   - Detection options: `Start the pipeline on source code change` 체크

   **Step 3: Add build stage**
   - Build provider: `AWS CodeBuild`
   - Project name: `mattermost-bot-build` (위에서 생성한 프로젝트)

   **Step 4: Add deploy stage**
   - Deploy provider: `AWS Elastic Beanstalk`
   - Application name: `Mattermost-Bot-SSAFY`
   - Environment name: `mattermost-bot-prod`

3. "Create pipeline" 클릭

## Step 5: 파이프라인 테스트

1. 코드 변경 후 Git push:

```bash
git add .
git commit -m "Test CI/CD pipeline"
git push origin main
```

2. CodePipeline이 자동으로 실행되는지 확인:
   - AWS Console > CodePipeline > Pipelines
   - `Mattermost-Bot-Pipeline` 선택
   - Source, Build, Deploy 단계가 성공하는지 확인

## Step 6: Mattermost Webhook 설정 업데이트

Elastic Beanstalk URL로 Mattermost Webhook을 업데이트합니다:

1. EB URL 확인:
```bash
eb status | grep CNAME
```

2. Mattermost에서 Webhook 설정:
   - Callback URL: `http://your-eb-url.us-east-1.elasticbeanstalk.com/webhook`

## 모니터링 및 로깅

### CloudWatch 로그 확인

```bash
# EB CLI로 로그 확인
eb logs

# 또는 AWS Console > CloudWatch > Log groups
# /aws/elasticbeanstalk/mattermost-bot-prod 확인
```

### 애플리케이션 상태 확인

```bash
# Health 체크
curl http://your-eb-url.us-east-1.elasticbeanstalk.com/health
```

## 비용 최적화

### 1. Auto Scaling 설정

```bash
eb scale 1  # 인스턴스 1개로 시작
```

필요시 Auto Scaling 설정:
- AWS Console > Elastic Beanstalk > Configuration > Capacity
- Min instances: 1
- Max instances: 2
- Scaling triggers 설정 (CPU 사용률 등)

### 2. 인스턴스 타입

개발/테스트: `t3.micro` (프리 티어)
프로덕션: `t3.small` 또는 `t3.medium`

## 롤백 방법

### 이전 버전으로 롤백

```bash
# 사용 가능한 버전 확인
eb appversion

# 특정 버전으로 롤백
eb deploy --version <version-label>
```

### CodePipeline에서 롤백

1. AWS Console > CodePipeline > Pipelines
2. `Mattermost-Bot-Pipeline` 선택
3. Deploy 단계에서 "Release change"로 이전 성공한 버전 재배포

## 문제 해결

### 배포 실패

```bash
# 로그 확인
eb logs

# 환경 상태 확인
eb health

# 환경 변수 확인
eb printenv
```

### 애플리케이션이 시작하지 않을 때

1. CloudWatch Logs 확인
2. 환경 변수가 올바르게 설정되었는지 확인
3. requirements.txt의 모든 패키지가 설치되는지 확인

### 503 Service Unavailable

1. 인스턴스가 Health Check를 통과하는지 확인
2. Health Check 경로 확인: `/health`
3. Application Load Balancer 설정 확인

## 보안 권장사항

1. **HTTPS 설정**: Load Balancer에 SSL/TLS 인증서 추가
2. **보안 그룹**: 필요한 포트만 열기
3. **IAM 역할**: 최소 권한 원칙 적용
4. **시크릿 로테이션**: 정기적으로 API 키 변경
5. **WAF 적용**: AWS WAF로 웹 공격 방어 (선택사항)

## 추가 개선사항

### 1. Blue/Green 배포

```bash
eb clone mattermost-bot-prod -n mattermost-bot-staging
```

### 2. CloudFront 추가 (CDN)

정적 파일이 있는 경우 CloudFront를 앞단에 추가

### 3. 알람 설정

CloudWatch Alarms 설정:
- CPU 사용률 > 80%
- 에러율 > 5%
- 응답 시간 > 2초

## 유용한 명령어

```bash
# 환경 목록 확인
eb list

# 환경 정보 확인
eb status

# 환경 종료
eb terminate mattermost-bot-prod

# 새 환경 생성
eb create

# 로그 스트리밍
eb logs --stream

# SSH 접속 (SSH 키가 설정된 경우)
eb ssh

# 구성 확인
eb config
```

## 참고 자료

- [AWS Elastic Beanstalk Python 문서](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-apps.html)
- [AWS CodePipeline 문서](https://docs.aws.amazon.com/codepipeline/latest/userguide/welcome.html)
- [AWS Systems Manager Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)
- [EB CLI 문서](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/eb-cli3.html)
