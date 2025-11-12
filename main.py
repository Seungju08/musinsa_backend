# main.py (업데이트된 전체)
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from jose import jwt, JWTError
from typing import List, Optional
import hashlib, os, shutil
from uuid import uuid4

import models, schemas
from database import Base, engine, get_db

# --------------------------- 초기화 ---------------------------
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Musinsa API Full", version="1.4")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static 이미지 업로드 경로
app.mount("/static", StaticFiles(directory="static"), name="static")
UPLOAD_DIR = "static/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

SECRET_KEY = "musinsa-secret-key"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
url = "172.28.3.51:8000"

# --------------------------- OAuth2 ---------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/signin")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="토큰 인증 실패",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: Optional[str] = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        raise credentials_exception
    return user

def require_admin(user: models.User):
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="관리자 권한 필요")

# --------------------------- 유틸 ---------------------------
def get_password_hash(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest() == hashed_password

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# --------------------------- 사용자 ---------------------------
@app.post("/signup", response_model=schemas.UserResponse)
def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(
        (models.User.username == user.username) | (models.User.email == user.email)
    ).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username 또는 Email 이미 존재")
    hashed_pw = get_password_hash(user.password)
    new_user = models.User(username=user.username, email=user.email, password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/signin")
def signin(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="이메일 또는 비밀번호 오류")
    token = create_access_token({"sub": db_user.email})
    return {"access_token": token, "token_type": "bearer"}

# --------------------------- 카테고리 ---------------------------
@app.get("/categories", response_model=List[schemas.CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    return db.query(models.Category).all()

@app.post("/categories", response_model=schemas.CategoryResponse)
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    new_category = models.Category(name=category.name)
    db.add(new_category)
    db.commit()
    db.refresh(new_category)
    return new_category

# --------------------------- 상품 ---------------------------
@app.post("/products", response_model=schemas.ProductResponse)
async def create_product(
    name: str = Form(...),
    brand: str = Form(...),
    price: int = Form(...),
    discount_rate: int = Form(0),
    stock: int = Form(...),
    category_id: int = Form(...),
    image: UploadFile | None = File(None),
    sku: str = Form(...),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    image_url = None
    if image:
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png"]:
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능")
        file_name = f"{uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        image_url = f"http://{url}/static/images/{file_name}"

    new_product = models.Product(
        name=name,
        brand=brand,
        price=price,
        discount_rate=discount_rate,
        discounted_price=int(price * (100 - discount_rate) / 100),
        stock=stock,
        category_id=category_id,
        image_url=image_url,
        sku=sku
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)
    return schemas.ProductResponse.from_orm(new_product)

@app.get("/products", response_model=List[schemas.ProductResponse])
def get_products(db: Session = Depends(get_db)):
    products = db.query(models.Product).all()
    return [schemas.ProductResponse.from_orm(p) for p in products]

@app.get("/products/{product_id}", response_model=schemas.ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품 없음")
    return schemas.ProductResponse.from_orm(product)

@app.put("/products/{product_id}", response_model=schemas.ProductResponse)
async def update_product(
    product_id: int,
    name: str | None = Form(None),
    brand: str | None = Form(None),
    price: int | None = Form(None),
    discount_rate: int | None = Form(None),
    stock: int | None = Form(None),
    category_id: int | None = Form(None),
    image: UploadFile | None = File(None),
    sku: str | None = Form(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    require_admin(user)
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품 없음")

    if image:
        ext = os.path.splitext(image.filename)[1].lower()
        file_name = f"{uuid4().hex}{ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        product.image_url = f"http://{url}/static/images/{file_name}"

    if name: product.name = name
    if brand: product.brand = brand
    if price is not None:
        product.price = price
        # 가격 바뀌면 할인 적용된 가격 다시 계산
        product.discounted_price = int(product.price * (100 - (product.discount_rate or 0)) / 100)
    if discount_rate is not None:
        product.discount_rate = discount_rate
        product.discounted_price = int(product.price * (100 - product.discount_rate) / 100)
    if stock is not None: product.stock = stock
    if category_id: product.category_id = category_id
    if sku: product.sku = sku

    db.commit()
    db.refresh(product)
    return schemas.ProductResponse.from_orm(product)

@app.delete("/products/{product_id}")
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    require_admin(user)
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품 없음")
    db.delete(product)
    db.commit()
    return {"detail": "삭제 완료"}

# --------------------------- 장바구니 ---------------------------
@app.post("/cart", response_model=schemas.CartItemResponse, status_code=status.HTTP_201_CREATED)
def add_to_cart(
    item: schemas.CartItemCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    """
    장바구니 담기:
      - 재고 확인 후 재고에서 제거(예약)
      - 동일 상품이 이미 장바구니에 있으면 수량 누적 처리
    """
    product = db.query(models.Product).filter(models.Product.id == item.product_id).with_for_update().first()
    if not product:
        raise HTTPException(status_code=404, detail="상품 없음")

    if product.stock < item.quantity:
        raise HTTPException(status_code=400, detail="재고 부족")

    # 이미 장바구니에 동일 상품이 있으면 합산 (사용자, 상품 기준)
    existing = db.query(models.CartItem).filter(
        models.CartItem.user_id == user.id,
        models.CartItem.product_id == item.product_id
    ).first()

    print(f"✅ [DEBUG] Before: {product.name} stock -> {product.stock}")

    if existing:
        existing.quantity += item.quantity
        product.stock -= item.quantity
        db.commit()
        db.refresh(existing)
        return existing
    else:
        product.stock -= item.quantity
        cart_item = models.CartItem(user_id=user.id, product_id=item.product_id, quantity=item.quantity)
        db.add(cart_item)
        db.commit()
        db.refresh(cart_item)
        return cart_item

@app.get("/cart/", status_code=status.HTTP_200_OK)
def get_cart(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    items = db.query(models.CartItem).filter(models.CartItem.user_id == user.id).all()
    # 간단한 응답: 아이템 리스트 + 총 개수
    total_items = sum(i.quantity for i in items)
    return {"items": [ {"product_id": i.product_id, "quantity": i.quantity, "id": i.id} for i in items ], "total_items": total_items}

# --------------------------- 장바구니 총 수량 (기존 요청) ---------------------------
@app.get("/cart/total_quantity")
def get_total_cart_quantity(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    total_quantity = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == user.id)
        .all()
    )
    if not total_quantity:
        return {"total_quantity": 0}
    total = sum(item.quantity for item in total_quantity)
    return {"total_quantity": total}

# --------------------------- 주문 ---------------------------
@app.post("/orders", response_model=schemas.OrderResponse)
def create_order(
    order: schemas.OrderCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    # 본인 계정만 주문 가능
    if user.id != order.user_id:
        raise HTTPException(status_code=403, detail="본인 계정만 주문 가능")

    # 우선: 사용자의 장바구니가 비어있지 않다면, 장바구니 기반으로 주문 생성
    cart_items = db.query(models.CartItem).filter(models.CartItem.user_id == user.id).all()
    if cart_items:
        # 장바구니에 이미 재고가 차감되어 있다고 가정(위 add_to_cart에서 차감)
        new_order = models.Order(user_id=user.id, total_price=order.total_price)
        db.add(new_order)
        db.commit()
        db.refresh(new_order)

        for ci in cart_items:
            # 상품 존재 여부 확인
            product = db.query(models.Product).filter(models.Product.id == ci.product_id).first()
            if not product:
                raise HTTPException(status_code=404, detail=f"{ci.product_id} 상품 없음")
            order_item = models.OrderItem(order_id=new_order.id, product_id=ci.product_id, quantity=ci.quantity, price=product.price)
            db.add(order_item)
            # 장바구니 항목 삭제
            db.delete(ci)
        db.commit()

        items = db.query(models.OrderItem).filter(models.OrderItem.order_id == new_order.id).all()
        response = schemas.OrderResponse.from_orm(new_order)
        response.items = [schemas.OrderItemResponse.from_orm(i) for i in items]
        return response

    # 장바구니가 비어있으면, 요청으로 넘어온 order.items 기준으로 재고 확인 및 차감
    new_order = models.Order(user_id=order.user_id, total_price=order.total_price)
    db.add(new_order)
    db.commit()
    db.refresh(new_order)

    for item in order.items:
        product = db.query(models.Product).filter(models.Product.id == item.product_id).with_for_update().first()
        if not product:
            raise HTTPException(status_code=404, detail=f"{item.product_id} 상품 없음")
        if product.stock < item.quantity:
            raise HTTPException(status_code=400, detail=f"{product.name} 재고 부족")
        product.stock -= item.quantity
        order_item = models.OrderItem(order_id=new_order.id, product_id=item.product_id, quantity=item.quantity, price=item.price)
        db.add(order_item)
    db.commit()

    items = db.query(models.OrderItem).filter(models.OrderItem.order_id == new_order.id).all()
    response = schemas.OrderResponse.from_orm(new_order)
    response.items = [schemas.OrderItemResponse.from_orm(i) for i in items]
    return response

# --------------------------- 관리자: 판매/재고 관련 엔드포인트 ---------------------------
@app.get("/admin/sales/top")
def admin_top_sales(limit: int = 10, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    인기 상품(구매량 기준) 상위 N개 반환:
      - 결과: product_id, name, total_sold
    """
    require_admin(user)

    results = (
        db.query(
            models.Product.id.label("product_id"),
            models.Product.name.label("name"),
            func.coalesce(func.sum(models.OrderItem.quantity), 0).label("total_sold")
        )
        .join(models.OrderItem, models.OrderItem.product_id == models.Product.id)
        .group_by(models.Product.id)
        .order_by(desc("total_sold"))
        .limit(limit)
        .all()
    )

    return [{"product_id": r.product_id, "name": r.name, "total_sold": int(r.total_sold)} for r in results]

@app.get("/admin/sales/history")
def admin_sales_history(product_id: Optional[int] = None, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    주문 히스토리:
      - product_id가 주어지면 해당 상품의 주문(주문 id, 수량, 주문일시) 리스트 반환
      - 없으면 전체 주문아이템 히스토리 반환
    """
    require_admin(user)

    q = db.query(models.OrderItem, models.Order).join(models.Order, models.Order.id == models.OrderItem.order_id)
    if product_id:
        q = q.filter(models.OrderItem.product_id == product_id)

    rows = q.order_by(models.Order.order_date.desc()).all()
    res = []
    for oi, order in rows:
        res.append({
            "order_id": oi.order_id,
            "product_id": oi.product_id,
            "quantity": oi.quantity,
            "price": oi.price,
            "order_date": order.order_date.isoformat()
        })
    return res

@app.get("/admin/products/{product_id}/stats")
def admin_product_stats(product_id: int, db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    특정 상품의 통계:
      - total_sold (총 판매수량)
      - last_purchased (마지막 구매일시, 없으면 None)
      - remaining_stock
    """
    require_admin(user)

    total_sold = db.query(func.coalesce(func.sum(models.OrderItem.quantity), 0)).filter(models.OrderItem.product_id == product_id).scalar() or 0
    last_row = (
        db.query(models.Order.order_date)
        .join(models.OrderItem, models.OrderItem.order_id == models.Order.id)
        .filter(models.OrderItem.product_id == product_id)
        .order_by(models.Order.order_date.desc())
        .first()
    )
    last_purchased = last_row[0].isoformat() if last_row else None
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품 없음")

    return {
        "product_id": product_id,
        "name": product.name,
        "total_sold": int(total_sold),
        "last_purchased": last_purchased,
        "remaining_stock": product.stock
    }

@app.patch("/admin/products/{product_id}/restock")
def admin_restock(product_id: int, amount: int = Form(...), db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    """
    재고 보충: 관리자 전용. amount = 추가할 수량 (음수는 허용하지 않음)
    """
    require_admin(user)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount는 양수여야 합니다")
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품 없음")
    product.stock += amount
    db.commit()
    db.refresh(product)
    return {"product_id": product_id, "new_stock": product.stock}
