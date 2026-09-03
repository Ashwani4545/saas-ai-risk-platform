from fastapi import Request

def get_tenant_id(request: Request):
    return request.headers.get("X-Tenant-ID", "default")

def tenant_response(tenant_id, data):
    return {
        "tenant": tenant_id,
        "data": data
    }
