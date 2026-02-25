from fastapi import FastAPI, Request, Depends
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine
from models import Product, User
import auth
from dotenv import load_dotenv
from collections import Counter
import stripe
import os

load_dotenv()

# Create all tables (including users)
Base.metadata.create_all(bind=engine)

stripe.api_key= os.getenv("STRIPE_SECRET_KEY")
DOMAIN = os.getenv("DOMAIN", "http://127.0.0.1:8000")

app = FastAPI()
is_production = os.getenv("RENDER") == "true"
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "une_cle_secrete_aleatoire"), https_only=is_production, same_site="lax")
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Dependencies ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.query(User).filter(User.id == user_id).first()

# --- Template Rendering Routes ---

@app.get("/")
def home(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    products = db.query(Product).all()
    return templates.TemplateResponse(
        "products.html",
        {"request": request, "products": products, "welcome": "Bienvenue chez Capillaire Pro !", "user": user}
    )

@app.get("/cart")
def view_cart(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cart = request.session.get("cart", [])
    cart_counts = Counter(cart)
    
    cart_items = []
    total = 0
    
    if cart:
        products = db.query(Product).filter(Product.id.in_(cart_counts.keys())).all()
        for product in products:
            quantity = cart_counts[product.id]
            subtotal = product.price * quantity
            total += subtotal
            cart_items.append({"product": product, "quantity": quantity, "subtotal": subtotal})
    
    return templates.TemplateResponse("cart.html", {"request": request, "cart_items": cart_items, "total": round(total, 2), "user": user})

@app.get("/success")
def payment_success(request: Request, user: User = Depends(get_current_user)):
    # On vide le panier après un paiement réussi
    request.session.pop("cart", None)
    return templates.TemplateResponse("success.html", {"request": request, "message": "Paiement réussi ! Merci pour votre achat.", "user": user})

@app.get("/cancel")
def payment_cancel(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("cancel.html", {"request": request, "user": user})

# --- Authentication Routes ---

@app.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register_user(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")

    if not username or not password:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Veuillez remplir tous les champs."})

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse("register.html", {"request": request, "error": "Ce nom d'utilisateur existe déjà."})

    hashed_password = auth.get_password_hash(password)
    new_user = User(username=username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    request.session["user_id"] = new_user.id
    return RedirectResponse(url="/", status_code=303)

@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login_user(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    username = form.get("username")
    password = form.get("password")
    
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not auth.verify_password(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request": request, "error": "Nom d'utilisateur ou mot de passe incorrect."})

    request.session["user_id"] = user.id
    return RedirectResponse(url="/", status_code=303)

@app.get("/logout")
def logout_user(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(url="/", status_code=303)

# --- Action Routes ---

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    product_id = int(form.get("product_id"))
    product = db.query(Product).filter(Product.id == product_id).first()

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": product.name if product else "Produit supprimé"},
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
async def create_cart_checkout_session(request: Request, db: Session = Depends(get_db)):
    cart = request.session.get("cart", [])
    
    if not cart:
        return RedirectResponse(url="/cart", status_code=303)

    cart_counts = Counter(cart)
    products = db.query(Product).filter(Product.id.in_(cart_counts.keys())).all()

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
    
    cart = request.session.get("cart", [])
    cart.append(product_id)
    request.session["cart"] = cart
    
    return RedirectResponse(url="/cart", status_code=303)