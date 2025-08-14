# Backend — Luồng Invite & Reset Password (Gmail SMTP, Username & Password Random)

## 1. Mục tiêu

* **Invite**: Gửi lời mời tham gia hệ thống kèm username & password random, token vô thời hạn nhưng thu hồi bằng **blacklist** sau khi sử dụng hoặc revoke thủ công.
* **Reset Password**: Đặt lại mật khẩu với token TTL ngắn (10–30 phút), single-use.
* Sử dụng Gmail SMTP để gửi email HTML.

---

## 2. Luồng xử lý

### Invite

1. Admin gọi `/auth/invite` → backend tạo:

   * **opaque token** và lưu hash vào DB (`invite_tokens`).
   * **username** random (nếu chưa tồn tại).
   * **password** random (đủ mạnh) và lưu hash vào DB.
2. Xác định domain FE từ `Origin` (qua CORS allowlist) hoặc `PUBLIC_BASE_URL`.
3. Build link: `https://<FE_DOMAIN>/invite#token=<TOKEN>`.
4. Gửi email HTML kèm username & password random.
5. Khi người dùng accept qua `/auth/accept-invite`, backend validate token → cho phép đổi mật khẩu nếu muốn → **blacklist** token.

### Reset Password

1. User gọi `/auth/forgot-password` → backend tạo token TTL ngắn (10–30 phút), lưu vào DB (`reset_tokens`).
2. Build link: `https://<FE_DOMAIN>/reset#token=<TOKEN>` và gửi email HTML.
3. User gửi token + mật khẩu mới qua `/auth/reset-password` → backend validate → đổi mật khẩu → invalidate token + revoke refresh tokens cũ.

---

## 3. Cấu hình `.env`

```env
RESET_TOKEN_TTL_MINUTES=20

# Gmail SMTP (khuyến nghị App Password với 2FA)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=true
SMTP_USER=your_account@gmail.com
SMTP_PASS=your_gmail_app_password
EMAIL_FROM_NAME=${APP_NAME}
EMAIL_FROM=your_account@gmail.com
```

> **Lưu ý:** Gmail yêu cầu bật **2-Step Verification** và tạo **App Password**. Không dùng mật khẩu đăng nhập trực tiếp.

---

## 4. Gửi Email HTML với Python (Invite)
- Template tiếng anh, responsive đẹp

```python
import os
import smtplib
import secrets
import string
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader

def gen_random_password(length=12):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def gen_random_username(prefix="user"):
    return f"{prefix}{secrets.randbelow(100000)}"

env = Environment(loader=FileSystemLoader(os.environ["EMAIL_TEMPLATES_DIR"]))
template = env.get_template("invite.html.j2")

username = gen_random_username()
password = gen_random_password()
link = "https://app.example.com/invite#token=..."

html = template.render(action_url=link, username=username, password=password)

msg = MIMEText(html, "html")
msg["Subject"] = "You're invited!"
msg["From"] = f"{os.environ['EMAIL_FROM_NAME']} <{os.environ['EMAIL_FROM']}>"
msg["To"] = "user@example.com"

with smtplib.SMTP(os.environ["SMTP_HOST"], os.environ["SMTP_PORT"]) as server:
    if os.environ.get("SMTP_TLS") == "true":
        server.starttls()
    server.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
    server.send_message(msg)
```

---

## 5. Best Practices

* **Token**:

  * Opaque random 32–64 bytes, lưu hash SHA-256 trong DB.
  * Invite: vô thời hạn, revoke sau khi dùng (blacklist).
  * Reset: TTL ngắn, single-use.
* **Username/Password random**:

  * Username tránh trùng, có prefix rõ ràng.
  * Password ≥ 12 ký tự, gồm chữ hoa, chữ thường, số, ký tự đặc biệt.
  * Chỉ gửi password qua email khi phát hành lần đầu; hash ngay khi lưu.
* **Domain**: Lấy từ `Origin` header (đã qua CORS) hoặc fallback `PUBLIC_BASE_URL`.
* **Bảo mật**:

  * Token ở fragment `#token=...` để tránh bị log.
  * Endpoint gửi mail trả về 200 chung, không tiết lộ tồn tại tài khoản.
  * Rate limit các endpoint `/auth/invite`, `/auth/forgot-password`, `/auth/reset-password`.
  * Audit log phát hành và tiêu thụ token.
