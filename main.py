from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from database import SessionLocal, Base, engine
from models import Product
from dotenv import load_dotenv
from collections import Counter
import stripe
import os

load_dotenv()

# Clé test Stripe (remplace par ta propre clé test)
stripe.api_key= os.getenv("STRIPE_SECRET_KEY")
DOMAIN = os.getenv("DOMAIN", "http://127.0.0.1:8000")
Base.metadata.create_all(bind=engine)

app = FastAPI()
# Ajout du middleware pour gérer le panier via les sessions
# On active https_only si on est sur Render (pour que les cookies fonctionnent bien en HTTPS)
is_production = os.getenv("RENDER") == "true"
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "une_cle_secrete_aleatoire"), https_only=is_production, same_site="lax")
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

@app.post("/create-cart-checkout-session")
async def create_cart_checkout_session(request: Request):
    cart = request.session.get("cart", [])
    
    if not cart:
        return RedirectResponse(url="/cart", status_code=303)

    db = SessionLocal()
    cart_counts = Counter(cart)
    products = db.query(Product).filter(Product.id.in_(cart_counts.keys())).all()
    db.close()

    line_items = []
    for product in products:
        quantity = cart_counts[product.id]
        line_items.append({
            "price_data": {
                "currency": "eur",
                "product_data": {"name": product.name},
                "unit_amount": int(product.price * 100),
            },
            "quantity": quantity,
        })

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=line_items,
        mode="payment",
        success_url=f"{DOMAIN}/success",
        cancel_url=f"{DOMAIN}/cancel",
    )
    return RedirectResponse(url=session.url, status_code=303)

@app.post("/add-to-cart")
async def add_to_cart(request: Request):
    form = await request.form()
    product_id = int(form.get("product_id"))
    
    # Récupère le panier actuel ou crée une liste vide
    cart = request.session.get("cart", [])
    cart.append(product_id)
    request.session["cart"] = cart
    
    return RedirectResponse(url="/cart", status_code=303)

@app.get("/cart")
def view_cart(request: Request):
    cart = request.session.get("cart", [])
    db = SessionLocal()
    
    cart_counts = Counter(cart)
    
    cart_items = []
    total = 0
    
    if cart:
        # Récupère les produits qui sont dans le panier
        products = db.query(Product).filter(Product.id.in_(cart_counts.keys())).all()
        for product in products:
            quantity = cart_counts[product.id]
            subtotal = product.price * quantity
            total += subtotal
            cart_items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    
    db.close()
    
    return templates.TemplateResponse("cart.html", {"request": request, "cart_items": cart_items, "total": round(total, 2)})

@app.get("/success")
def payment_success(request: Request):
    # On vide le panier après un paiement réussi
    request.session.pop("cart", None)
    return templates.TemplateResponse("success.html", {"request": request, "message": "Paiement réussi ! Merci pour votre achat."})

@app.get("/cancel")
def payment_cancel():
    return "<h1>Paiement annulé.</h1>"