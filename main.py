from fastapi import FastAPI, Request, Depends, APIRouter, HTTPException, Form, UploadFile, File
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session, joinedload
from database import SessionLocal, Base, engine
from models import Product, User, Review, Order, OrderItem
import auth
from dotenv import load_dotenv
from collections import Counter
from pydantic import BaseModel
import stripe
import shutil
import os

load_dotenv()

# Create all tables (including users)
Base.metadata.create_all(bind=engine)

stripe.api_key= os.getenv("STRIPE_SECRET_KEY")
# On récupère le domaine et on enlève le slash à la fin s'il y en a un pour éviter les doubles //
DOMAIN = os.getenv("DOMAIN", "http://127.0.0.1:8000").rstrip("/")

print(f"🚀 Démarrage de l'application pour le domaine : {DOMAIN}")

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
        {"request": request, "products": products, "welcome": "Bienvenue chez Chrystelle & Sleeks !", "user": user}
    )

@app.get("/product/{product_id}")
def product_detail(product_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    
    # Récupérer les avis du produit
    reviews = db.query(Review).filter(Review.product_id == product_id).all()
    
    return templates.TemplateResponse("product_detail.html", {
        "request": request, 
        "product": product, 
        "reviews": reviews,
        "user": user
    })

@app.post("/product/{product_id}/review")
async def add_review(product_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
        
    form = await request.form()
    rating = int(form.get("rating"))
    comment = form.get("comment")
    
    new_review = Review(product_id=product_id, user_id=user.id, rating=rating, comment=comment)
    db.add(new_review)
    db.commit()
    return RedirectResponse(url=f"/product/{product_id}", status_code=303)

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
def payment_success(request: Request, product_id: int = None, quantity: int = 1, db: Session = Depends(get_db), user: User = Depends(get_current_user)):    
    line_items_data = []
    total_price = 0

    if product_id:
        # Cas 1 : Achat direct ou unitaire depuis le panier
        product = db.query(Product).filter(Product.id == product_id).first()
        if product and product.stock >= quantity:
            product.stock -= quantity
            line_items_data.append({"product": product, "quantity": quantity})
            total_price = product.price * quantity
            
            # Si l'article était dans le panier, on le retire (puisqu'il est payé)
            cart = request.session.get("cart", [])
            for _ in range(quantity):
                if product_id in cart:
                    cart.remove(product_id)
            request.session["cart"] = cart
    else:
        # Cas 2 : Achat via le panier
        cart = request.session.get("cart", [])
        if cart:
            cart_counts = Counter(cart)
            products = db.query(Product).filter(Product.id.in_(cart_counts.keys())).all()
            
            for product in products:
                quantity_purchased = cart_counts[product.id]
                if product.stock >= quantity_purchased:
                    product.stock -= quantity_purchased
                    line_items_data.append({"product": product, "quantity": quantity_purchased})
                    total_price += product.price * quantity_purchased
            
            request.session.pop("cart", None)

    # Si un utilisateur est connecté et que des articles ont été traités, on crée une commande.
    if user and line_items_data:
        order_items = [
            OrderItem(product_id=item['product'].id, quantity=item['quantity'], price_at_purchase=item['product'].price) 
            for item in line_items_data
        ]
        new_order = Order(user_id=user.id, total_price=round(total_price, 2), items=order_items)
        db.add(new_order)

    db.commit() # Sauvegarde les changements de stock et la nouvelle commande en une seule fois.
            
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
    request.session.clear() # Vide toute la session (panier + utilisateur)
    return RedirectResponse(url="/", status_code=303)

@app.get("/profile")
def view_profile(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    # Récupère les commandes de l'utilisateur avec les produits associés pour éviter des requêtes multiples
    orders = db.query(Order).filter(Order.user_id == user.id)\
        .options(joinedload(Order.items).joinedload(OrderItem.product))\
        .order_by(Order.created_at.desc())\
        .all()

    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "orders": orders})


# --- Admin Dependencies & Router ---
admin_router = APIRouter(prefix="/admin")

def require_admin(user: User = Depends(get_current_user)):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="Accès refusé. Vous devez être administrateur.")
    return user

# --- Admin Routes ---

@admin_router.get("/", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.id).all()
    return templates.TemplateResponse("admin_dashboard.html", {"request": request, "products": products})

@admin_router.get("/products/add", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def add_product_form(request: Request):
    return templates.TemplateResponse("admin_productForm.html", {"request": request, "product": None})

@admin_router.post("/products/add", dependencies=[Depends(require_admin)])
async def add_product(
    db: Session = Depends(get_db),
    name: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    message: str = Form(...),
    image: UploadFile = File(...)
):
    # Sauvegarde de l'image
    image_path = f"static/images/{image.filename}"
    with open(image_path, "wb") as buffer:
        shutil.copyfileobj(image.file, buffer)

    new_product = Product(
        name=name,
        price=price,
        stock=stock,
        message=message,
        image=image.filename
    )
    db.add(new_product)
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@admin_router.get("/products/edit/{product_id}", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def edit_product_form(product_id: int, request: Request, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")
    return templates.TemplateResponse("admin_productForm.html", {"request": request, "product": product})

@admin_router.post("/products/edit/{product_id}", dependencies=[Depends(require_admin)])
async def edit_product(
    product_id: int,
    db: Session = Depends(get_db),
    name: str = Form(...),
    price: float = Form(...),
    stock: int = Form(...),
    message: str = Form(...),
    image: UploadFile = File(None) # Image optionnelle à la modification
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Produit non trouvé")

    product.name = name
    product.price = price
    product.message = message
    product.stock = stock

    if image and image.filename:
        image_path = f"static/images/{image.filename}"
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        product.image = image.filename
    
    db.commit()
    return RedirectResponse(url="/admin", status_code=303)

@admin_router.post("/products/delete/{product_id}", dependencies=[Depends(require_admin)])
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        db.delete(product)
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)

# --- Action Routes ---

@app.post("/create-checkout-session")
async def create_checkout_session(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    product_id = int(form.get("product_id"))
    quantity = int(form.get("quantity", 1)) # Par défaut 1 si non spécifié
    product = db.query(Product).filter(Product.id == product_id).first()

    # On récupère l'URL de base dynamiquement (ex: https://mon-site.onrender.com ou http://127.0.0.1:8000)
    base_url = str(request.base_url).rstrip("/")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "eur",
                "product_data": {"name": product.name if product else "Produit supprimé"},
                "unit_amount": int(product.price * 100),
            },
            "quantity": quantity,
        }],
        mode="payment",
        success_url=f"{base_url}/success?product_id={product.id}&quantity={quantity}",
        cancel_url=f"{base_url}/cancel",
    )
    
    return RedirectResponse(url=session.url, status_code=303)

@app.post("/create-cart-checkout-session")
async def create_cart_checkout_session(request: Request, db: Session = Depends(get_db)):
    cart = request.session.get("cart", [])
    
    if not cart:
        return RedirectResponse(url="/cart", status_code=303)

    cart_counts = Counter(cart)
    products = db.query(Product).filter(Product.id.in_(cart_counts.keys())).all()

    # On récupère l'URL de base dynamiquement
    base_url = str(request.base_url).rstrip("/")

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
        success_url=f"{base_url}/success",
        cancel_url=f"{base_url}/cancel",
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

@app.post("/remove-from-cart")
async def remove_from_cart(request: Request):
    form = await request.form()
    product_id = int(form.get("product_id"))
    
    cart = request.session.get("cart", [])
    if product_id in cart:
        cart.remove(product_id)
        request.session["cart"] = cart
    
    return RedirectResponse(url="/cart", status_code=303)

# --- Chatbot Route ---
class ChatMessage(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(chat_msg: ChatMessage):
    user_message = chat_msg.message.lower()
    response = ""
    
    if "bonjour" in user_message or "salut" in user_message or "hello" in user_message:
        response = "Bonjour ! Bienvenue chez Chrystelle & Sleeks. Comment puis-je vous aider ?"
    elif "livraison" in user_message or "expedition" in user_message or "envoi" in user_message:
        response = "Nous livrons en France métropolitaine sous 3 à 5 jours ouvrés."
    elif "retour" in user_message or "remboursement" in user_message:
        response = "Vous avez 14 jours pour changer d'avis. Contactez-nous pour initier un retour."
    elif "paiement" in user_message or "payer" in user_message:
        response = "Le paiement est 100% sécurisé via Stripe. Nous acceptons les cartes bancaires."
    elif "produit" in user_message or "cheveux" in user_message:
        response = "Nous proposons une gamme complète : shampoings, après-shampoings, masques, huiles... Tout pour des cheveux magnifiques !"
    elif "contact" in user_message or "mail" in user_message:
        response = "Vous pouvez nous écrire à support@chrystelle-sleeks.com."
    else:
        response = "Désolé, je n'ai pas compris votre question. Je peux vous renseigner sur la livraison, les paiements ou nos produits."
        
    return {"response": response}

# Inclure le routeur de l'admin dans l'application principale
app.include_router(admin_router)