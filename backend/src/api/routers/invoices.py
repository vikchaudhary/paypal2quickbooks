from fastapi import APIRouter

router = APIRouter(prefix="/invoices", tags=["invoices"])

@router.get("/health")
def health():
    return {"status": "ok"}
