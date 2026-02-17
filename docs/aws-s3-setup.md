# AWS S3 설정 가이드

PhotoDiary에서 사진을 클라우드에 저장하기 위한 AWS S3 설정 방법입니다.

---

## 1. AWS 계정 준비

AWS 계정이 없다면 [https://aws.amazon.com](https://aws.amazon.com)에서 가입합니다.

---

## 2. IAM 사용자 생성 (권장)

Root 계정의 Access Key는 **모든 AWS 리소스에 무제한 접근** 가능하므로, S3 전용 IAM 사용자를 만들어 사용하는 것을 권장합니다.

### 단계

1. [AWS 콘솔](https://console.aws.amazon.com/) 로그인
2. 상단 검색창에 **IAM** 입력 → IAM 서비스 진입
3. 좌측 메뉴 **사용자(Users)** → **사용자 생성** 클릭
4. 사용자 이름 입력 (예: `photodiary-s3`)
5. 권한 설정:
   - **직접 정책 연결** 선택
   - `AmazonS3FullAccess` 검색 → 체크
6. **사용자 생성** 완료

---

## 3. Access Key 발급

### IAM 사용자 (권장)

1. IAM → 사용자 → 생성한 사용자 클릭
2. **보안 자격 증명** 탭
3. **액세스 키 만들기** 클릭
4. 사용 사례: **Command Line Interface(CLI)** 선택
5. 경고 체크 후 생성
6. **Access Key ID**와 **Secret Access Key** 복사

> **주의**: Secret Access Key는 생성 직후 화면에서만 확인 가능합니다. 반드시 복사해두세요.

### Root 사용자 (비권장)

1. 콘솔 우측 상단 계정 이름 클릭 → **보안 자격 증명**
2. 액세스 키 섹션 → **액세스 키 만들기**
3. 경고 체크 후 생성

---

## 4. S3 버킷 생성

### AWS 콘솔에서 생성

1. 상단 검색창에 **S3** 입력 → S3 서비스 진입
2. **버킷 만들기** 클릭
3. 버킷 이름 입력 (예: `photodiary-s3`)
4. 리전: **아시아 태평양(서울) ap-northeast-2**
5. 나머지 기본값 → **버킷 만들기**

### Python으로 생성

```python
import boto3

client = boto3.client("s3", region_name="ap-northeast-2")
client.create_bucket(
    Bucket="photodiary-s3",
    CreateBucketConfiguration={"LocationConstraint": "ap-northeast-2"},
)
```

---

## 5. 환경변수 설정

프로젝트 루트의 `.env` 파일에 다음을 추가합니다:

```env
AWS_ACCESS_KEY_ID=AKIA...발급받은키
AWS_SECRET_ACCESS_KEY=발급받은시크릿키
AWS_S3_BUCKET_NAME=photodiary-s3
AWS_S3_REGION=ap-northeast-2
```

> `.env`는 `.gitignore`에 포함되어 있으므로 git에 커밋되지 않습니다.

---

## 6. 동작 확인

```bash
python -m pipeline.utils.s3_uploader <이미지파일경로>
```

업로드 성공 시 S3 키와 URL이 출력됩니다.

### Python에서 사용

```python
from pipeline.utils.s3_uploader import upload_to_s3

result = upload_to_s3("photo.jpg", user_id="user123")
print(result.s3_url)
# https://photodiary-s3.s3.ap-northeast-2.amazonaws.com/photos/user123/1739..._photo.jpg
```
