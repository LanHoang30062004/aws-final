# FastAPI + MySQL

Ứng dụng mẫu cung cấp API CRUD cho tài nguyên `items` và lưu dữ liệu trong MySQL.

## Chạy local

Yêu cầu Docker Compose:

```sh
docker compose up --build
```

- Kiểm tra trạng thái: `GET http://localhost:8000/health`
- Tạo item: `POST http://localhost:8000/items` với JSON `{"name":"Notebook","description":"Project notes"}`
- Liệt kê: `GET http://localhost:8000/items`
- Xem một item: `GET http://localhost:8000/items/{id}`
- Xóa: `DELETE http://localhost:8000/items/{id}`
- Swagger UI: `http://localhost:8000/docs`

Các mật khẩu mặc định trong `compose.yaml` chỉ dành cho local development. Không dùng các giá trị mặc định này ở môi trường thật.

## Chạy test

```sh
python -m pip install -r requirements.txt
pytest -q
```

Test dùng SQLite tạm thời; MySQL không cần thiết để chạy test.

## GitHub Actions → Docker Hub → EC2 private subnet (SSM)

Workflow `.github/workflows/deploy.yml` chạy test với pull request vào `main`. Khi push vào `main`, workflow đẩy image lên Docker Hub rồi deploy qua AWS Systems Manager (SSM) Run Command bằng AWS IAM access key. Image được gắn tag bằng commit SHA; deploy không cần SSH inbound hay public IP trên EC2.

### GitHub repository configuration

Tạo repository `fastapi-mysql` trên Docker Hub. Tên repository đã được cố định trong workflow và `compose.yaml`, nên không cần GitHub Variable cho repository.

Thêm các GitHub **Secrets**:

- `DOCKERHUB_USERNAME`: tên tài khoản Docker Hub; workflow dùng secret này cả khi đăng nhập lẫn đặt namespace image
- `DOCKERHUB_TOKEN`: Docker Hub access token có quyền push vào repository
- `AWS_ACCESS_KEY_ID`: access key của IAM user chỉ dành cho CI/CD
- `AWS_SECRET_ACCESS_KEY`: secret key tương ứng
- `AWS_REGION`: AWS region của EC2, ví dụ `ap-southeast-1`
- `EC2_INSTANCE_ID`: instance ID của EC2, ví dụ `i-0123456789abcdef0`

Không cần tạo GitHub Variables cho Docker Hub. Không đặt token hoặc private key trong repository.

### Cấu hình IAM và SSM

1. Tạo IAM user riêng cho CI/CD, không dùng root user, rồi tạo access key. Lưu access key và secret key dưới GitHub Secrets như trên.
2. Cấp IAM user quyền tối thiểu dùng SSM: `ssm:SendCommand` cho đúng EC2 instance và document `AWS-RunShellScript`, cùng `ssm:GetCommandInvocation` để workflow chờ và đọc kết quả. Tránh cấp `AdministratorAccess`.
3. Gắn IAM instance profile có policy `AmazonSSMManagedInstanceCore` vào EC2. SSM Agent phải hoạt động và instance cần kết nối outbound tới Systems Manager (qua NAT Gateway hoặc VPC endpoints SSM phù hợp).
4. Cài Docker Engine và Docker Compose plugin trên EC2. Đặt Docker Hub repository ở chế độ **public** để không cần đăng nhập Docker Hub trên EC2; nếu repository private, cần cấu hình credential chỉ có quyền pull trên EC2.
5. Tạo `/opt/fastapi-mysql-app/.env` trên EC2 với nội dung sau và mật khẩu DB mạnh:

   ```dotenv
   MYSQL_DATABASE=app_db
   MYSQL_USER=app_user
   MYSQL_PASSWORD=replace-with-a-strong-password
   MYSQL_ROOT_PASSWORD=replace-with-another-strong-password
   ```

   Bảo vệ tệp bằng `chmod 600 /opt/fastapi-mysql-app/.env`. Workflow chuyển `compose.yaml` tới EC2 qua SSM, sau đó pull image và khởi động ứng dụng cùng MySQL.

6. Đảm bảo EC2 có outbound internet hoặc route phù hợp để kéo image Docker Hub và image MySQL.

Không cần mở inbound port `22` hoặc đặt EC2 trong public subnet. AWS access key/secret key cho phép GitHub Actions gọi AWS SSM API, nhưng không tự tạo kết nối mạng tới EC2; SSM Agent, instance profile và kết nối outbound vẫn bắt buộc. Để truy cập API từ bên ngoài VPC, cấu hình ALB/NLB, VPN hoặc một đường truy cập riêng phù hợp. API lắng nghe trên port `8000`.
