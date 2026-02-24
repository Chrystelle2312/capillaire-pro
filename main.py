from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import SessionLocal, Base, engine
from models import Product
from dotenv import load_dotenv
import stripe
import os

load_dotenv()

# Clé test Stripe (remplace par ta propre clé test)
stripe.api_key= os.getenv("STRIPE_SECRET_KEY")
DOMAIN = os.getenv("DOMAIN", "http://127.0.0.1:8000")
Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def home(request: Request):
    db = SessionLocal()
    products = db.query(Product).all()
    db.close()
    return templates.TemplateResponse(
        "products.html",
        {"request": request, "products": products, "welcome": "Bienvenue chez Capillaire Pro !"}
    )

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request):
    form = await request.form()
    product_id = int(form.get("product_id"))

    db = SessionLocal()
    product = db.query(Product).filter(Product.id == product_id).first()
    db.close()

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": product.name},
                "unit_amount": int(product.price * 100),
            },
            "quantity": 1,
        }],
        mode="payment",
        success_url=f"{DOMAIN}/success",
        cancel_url=f"{DOMAIN}/cancel",
    )
    
    return RedirectResponse(url=session.url, status_code=303)

@app.get("/success")
def payment_success():
    return templates.TemplateResponse("success.html", {"request": {}, "message": "Paiement réussi ! Merci pour votre achat."})

@app.get("/cancel")
def payment_cancel():
    return "<h1>Paiement annulé.</h1>"