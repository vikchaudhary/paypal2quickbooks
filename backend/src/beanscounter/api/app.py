from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from beanscounter.api.routers.invoices import router as invoices_router
from beanscounter.api.routers.settings import router as settings_router
from beanscounter.api.routers.quickbooks import router as quickbooks_router
from beanscounter.api.routers.gmail import router as gmail_router

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite default ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices_router)
app.include_router(settings_router)
app.include_router(quickbooks_router)
app.include_router(gmail_router)
