# AWS 배포 가이드

이 문서는 Mattermost Bot을 AWS Elastic Beanstalk에 배포하는 방법을 설명합니다.

## 현재 배포 정보

| 항목 | 값 |
|------|-----|
| **애플리케이션** | Mattermost-Bot-SSAFY |
| **환경** | mattermost-bot-prod |
| **URL** | http://mattermost-bot-prod.eba-iusyhcp9.us-east-1.elasticbeanstalk.com |
| **Webhook URL** | http://mattermost-bot-prod.eba-iusyhcp9.us-east-1.elasticbeanstalk.com/webhook |
| **리전** | us-east-1 |
| **인스턴스** | t3.micro |

## 아키텍처 개요

- **애플리케이션**: Flask 기반 Mattermost Bot
- **호스팅**: AWS Elastic Beanstalk (Python 3.11)
- **인스턴스**: Single Instance (t3.micro)

## 사전 준비사항

1. AWS CLI 설치 및 구성
2. 필요한 API 키들 (MATTERMOST_TOKEN, GEMINI_API_KEY)

## 빠른 배포 (AWS CLI)

### 1. AWS CLI 설정

```bash
aws configure
# AWS Access Key ID: [your-access-key]
# AWS Secret Access Key: [your-secret-key]
# Default region name: us-east-1
```

### 2. 애플리케이션 생성

```bash
aws elasticbeanstalk create-application \
    --application-name Mattermost-Bot-SSAFY \
    --description "Mattermost Bot in SSAFY" \
    --region us-east-1
```

### 3. IAM 역할 및 인스턴스 프로파일 생성

```bash
# Trust Policy 생성
cat > /tmp/trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# IAM 역할 생성
aws iam create-role \
    --role-name aws-elasticbeanstalk-ec2-role \
    --assume-role-policy-document file:///tmp/trust-policy.json

# 정책 연결
aws iam attach-role-policy \
    --role-name aws-elasticbeanstalk-ec2-role \
    --policy-arn arn:aws:iam::aws:policy/AWSElasticBeanstalkWebTier

aws iam attach-role-policy \
    --role-name aws-elasticbeanstalk-ec2-role \
    --policy-arn arn:aws:iam::aws:policy/AWSElasticBeanstalkWorkerTier

# 인스턴스 프로파일 생성
aws iam create-instance-profile \
    --instance-profile-name aws-elasticbeanstalk-ec2-role

aws iam add-role-to-instance-profile \
    --instance-profile-name aws-elasticbeanstalk-ec2-role \
    --role-name aws-elasticbeanstalk-ec2-role
```

### 4. 애플리케이션 배포

```bash
# S3 버킷 생성
aws s3 mb s3://mattermost-bot-deploy-$(aws sts get-caller-identity --query Account --output text) --region us-east-1

# 배포 패키지 생성 및 업로드
cd mattermost_bot
zip -r /tmp/app.zip . -x "*.git*" -x ".env" -x ".claude*" -x "__pycache__/*"
aws s3 cp /tmp/app.zip s3://mattermost-bot-deploy-$(aws sts get-caller-identity --query Account --output text)/app-v1.zip

# 애플리케이션 버전 생성
aws elasticbeanstalk create-application-version \
    --application-name Mattermost-Bot-SSAFY \
    --version-label v1 \
    --source-bundle S3Bucket=mattermost-bot-deploy-$(aws sts get-caller-identity --query Account --output text),S3Key=app-v1.zip \
    --region us-east-1

# 환경 생성
aws elasticbeanstalk create-environment \
    --application-name Mattermost-Bot-SSAFY \
    --environment-name mattermost-bot-prod \
    --solution-stack-name "64bit Amazon Linux 2023 v4.9.1 running Python 3.11" \
    --version-label v1 \
    --option-settings \
        Namespace=aws:autoscaling:launchconfiguration,OptionName=InstanceType,Value=t3.micro \
        Namespace=aws:autoscaling:launchconfiguration,OptionName=IamInstanceProfile,Value=aws-elasticbeanstalk-ec2-role \
        Namespace=aws:elasticbeanstalk:environment,OptionName=EnvironmentType,Value=SingleInstance \
        Namespace=aws:elasticbeanstalk:application:environment,OptionName=MATTERMOST_TOKEN,Value=your_token \
        Namespace=aws:elasticbeanstalk:application:environment,OptionName=GEMINI_API_KEY,Value=your_api_key \
    --region us-east-1
```

### 5. 배포 상태 확인

```bash
aws elasticbeanstalk describe-environments \
    --application-name Mattermost-Bot-SSAFY \
    --environment-names mattermost-bot-prod \
    --region us-east-1 \
    --query "Environments[0].{Status:Status,Health:Health,URL:CNAME}"
```

## 업데이트 배포

코드 변경 후 재배포:

```bash
# 새 버전 패키지 생성
zip -r /tmp/app.zip . -x "*.git*" -x ".env" -x ".claude*" -x "__pycache__/*"

# S3 업로드
aws s3 cp /tmp/app.zip s3://mattermost-bot-deploy-414386367477/app-v2.zip

# 새 버전 생성
aws elasticbeanstalk create-application-version \
    --application-name Mattermost-Bot-SSAFY \
    --version-label v2 \
    --source-bundle S3Bucket=mattermost-bot-deploy-414386367477,S3Key=app-v2.zip \
    --region us-east-1

# 환경 업데이트
aws elasticbeanstalk update-environment \
    --application-name Mattermost-Bot-SSAFY \
    --environment-name mattermost-bot-prod \
    --version-label v2 \
    --region us-east-1
```

## 환경 변수 설정

```bash
aws elasticbeanstalk update-environment \
    --application-name Mattermost-Bot-SSAFY \
    --environment-name mattermost-bot-prod \
    --option-settings \
        Namespace=aws:elasticbeanstalk:application:environment,OptionName=MATTERMOST_TOKEN,Value=your_token \
        Namespace=aws:elasticbeanstalk:application:environment,OptionName=GEMINI_API_KEY,Value=your_api_key \
    --region us-east-1
```

## 모니터링

### 상태 확인

```bash
# Health 체크
curl http://mattermost-bot-prod.eba-iusyhcp9.us-east-1.elasticbeanstalk.com/health

# 환경 상태
aws elasticbeanstalk describe-environment-health \
    --environment-name mattermost-bot-prod \
    --attribute-names All \
    --region us-east-1
```

### 로그 확인

```bash
aws elasticbeanstalk request-environment-info \
    --environment-name mattermost-bot-prod \
    --info-type tail \
    --region us-east-1

# 잠시 후
aws elasticbeanstalk retrieve-environment-info \
    --environment-name mattermost-bot-prod \
    --info-type tail \
    --region us-east-1
```

## 롤백

```bash
# 이전 버전으로 롤백
aws elasticbeanstalk update-environment \
    --application-name Mattermost-Bot-SSAFY \
    --environment-name mattermost-bot-prod \
    --version-label v1 \
    --region us-east-1
```

## 환경 종료

```bash
aws elasticbeanstalk terminate-environment \
    --environment-name mattermost-bot-prod \
    --region us-east-1
```

## Mattermost 설정

Outgoing Webhook 설정:
- **Callback URL**: `http://mattermost-bot-prod.eba-iusyhcp9.us-east-1.elasticbeanstalk.com/webhook`
- **Token**: 환경 변수 `MATTERMOST_TOKEN`과 일치해야 함

## 비용 최적화

- **인스턴스**: t3.micro (프리 티어 대상)
- **환경 타입**: SingleInstance (Load Balancer 비용 절감)
- **리전**: us-east-1 (가장 저렴)

## 참고 자료

- [AWS Elastic Beanstalk Python 문서](https://docs.aws.amazon.com/elasticbeanstalk/latest/dg/create-deploy-python-apps.html)
- [AWS CLI Elastic Beanstalk](https://docs.aws.amazon.com/cli/latest/reference/elasticbeanstalk/)
