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

## GitHub Actions → Amazon ECR → EC2

Workflow `.github/workflows/deploy.yml` chạy test với mọi pull request vào `main`. Khi có push vào `main`, nó tạo image, đẩy image lên ECR và deploy qua SSH. Image được gắn tag bằng commit SHA. AWS access key chỉ được dùng trong GitHub Actions; EC2 lấy quyền đọc ECR qua instance profile.

### GitHub repository configuration

Tạo repository ECR trước và thêm các GitHub **Variables**:

- `AWS_REGION`: AWS region, ví dụ `ap-southeast-1`
- `ECR_REPOSITORY`: tên ECR repository

Thêm các GitHub **Secrets**:

- `AWS_ACCESS_KEY_ID`: access key có quyền push image lên ECR (nên giới hạn quyền vào đúng repository)
- `AWS_SECRET_ACCESS_KEY`: secret tương ứng
- `EC2_HOST`: public DNS hoặc IP của EC2
- `EC2_USER`: SSH user, ví dụ `ubuntu` hoặc `ec2-user`
- `EC2_SSH_KEY`: private SSH key dạng PEM, giữ nguyên các dòng BEGIN/END

Nếu bạn đang có tên secret theo cách ghi `aws_access_key`, `aws_secret_access_key`, `ec2_host`, hoặc `ec2_ssh_key`, hãy đổi tên thành các tên mà workflow tham chiếu ở trên hoặc sửa tham chiếu workflow cho khớp. Không đặt giá trị bí mật trong GitHub Variables hoặc trong repository.

### Chuẩn bị EC2 một lần

1. Cài Docker Engine, Docker Compose plugin và AWS CLI trên EC2.
2. Gắn IAM instance profile có quyền `ecr:GetAuthorizationToken` và quyền pull (tối thiểu `ecr:BatchCheckLayerAvailability`, `ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`) với đúng ECR repository. Không cần chép AWS access key CI lên EC2.
3. Mở inbound TCP port `22` chỉ từ IP runner/địa chỉ quản trị phù hợp, và mở port `8000` nếu cần truy cập API trực tiếp.
4. Tạo `/opt/fastapi-mysql-app/.env` trên EC2 với nội dung sau. Thay các giá trị theo tài khoản, region, ECR repository của bạn; dùng mật khẩu DB mạnh:

   ```dotenv
   ECR_REGISTRY=123456789012.dkr.ecr.ap-southeast-1.amazonaws.com
   ECR_REPOSITORY=fastapi-mysql
   MYSQL_DATABASE=app_db
   MYSQL_USER=app_user
   MYSQL_PASSWORD=replace-with-a-strong-password
   MYSQL_ROOT_PASSWORD=replace-with-another-strong-password
   ```

   Bảo vệ tệp bằng `chmod 600 /opt/fastapi-mysql-app/.env`.    GitHub Actions sẽ tải `compose.yaml` lên cùng thư mục và khởi động ứng dụng cùng MySQL. Cùng một file Compose hỗ trợ local (build từ Dockerfile) lẫn deploy production (dùng image ECR).

5. Tạo ECR repository tương ứng trước khi chạy workflow. `AWS_ACCESS_KEY_ID` và `AWS_SECRET_ACCESS_KEY` phải có quyền push image vào đó.

Sau khi deploy, API lắng nghe trên port `8000`. Dữ liệu MySQL nằm trong Docker volume `mysql_data`; không xóa volume khi cập nhật ứng dụng.
