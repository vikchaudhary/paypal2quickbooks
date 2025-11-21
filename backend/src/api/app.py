from fastapi import FastAPI
from paypal2quickbooks.api.routers.invoices import router as invoices_router

app = FastAPI()
app.include_router(invoices_router)
