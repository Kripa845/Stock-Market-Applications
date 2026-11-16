# API getting started

The StockScope API is served by the Django backend. Start it from `Backend/` after completing the [project setup](../README.md#setup):

```powershell
python manage.py runserver
```

Open the [Swagger UI](http://localhost:8000/api/docs/) to browse operations. The OpenAPI document is at `/api/schema/` and ReDoc is at `/api/redoc/`.

The public market snapshot is a simple first request:

```powershell
curl.exe http://localhost:8000/api/market/public/snapshot/
```

For protected operations, obtain a JWT as described in [authentication](authentication.md), then send `Authorization: Bearer <access-token>`. List endpoints may use page-number pagination; query parameters are listed per operation in Swagger UI. Protected endpoints also enforce role and company-access permissions, which can produce `403 Forbidden` even with a valid token.
