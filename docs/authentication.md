# Authentication

The API uses JSON Web Tokens (JWT) through SimpleJWT. Registration creates a Viewer account; permissions for other roles are managed by an administrator.

1. Submit credentials to `POST /api/users/login/`:

   ```json
   {"username": "your-user", "password": "your-password"}
   ```

2. The response contains `access` and `refresh` tokens. Use the access token in the HTTP `Authorization` header:

   ```text
   Authorization: Bearer <access-token>
   ```

3. In Swagger UI, select **Authorize**, enter the access token (the UI supplies the Bearer scheme), then authorize. Do not include `Bearer ` in the token field.

Access tokens last 30 minutes and refresh tokens last 7 days. Obtain a new access token with `POST /api/users/token/refresh/` and a body containing `{"refresh": "<refresh-token>"}`. The API does not use session-cookie authentication for its REST endpoints.
