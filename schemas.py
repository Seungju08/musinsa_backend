from pydantic import BaseModel
from datetime import datetime

# ----------------- 사용자 -----------------
class UserBase(BaseModel):
    username: str
    email: str

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(UserBase):
    id: int
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}

# ----------------- 카테고리 -----------------
class CategoryBase(BaseModel):
    name: str

class CategoryCreate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    model_config = {"from_attributes": True}

# ----------------- 상품 -----------------
class ProductBase(BaseModel):
    name: str
    brand: str
    price: int
    discount_rate: int = 0
    discounted_price: int | None = None
    stock: int
    image_url: str | None = None
    category_id: int

class ProductCreate(ProductBase):
    pass

class ProductUpdate(ProductBase):
    pass

class ProductResponse(BaseModel):
    id: int
    name: str
    brand: str
    price: int
    discount_rate: int = 0
    stock: int
    image_url: str | None = None
    category_id: int
    created_at: datetime
    sku: str | None = None

    # DB에 저장되지 않는 계산 필드
    @property
    def discounted_price(self) -> int:
        return int(self.price * (100 - self.discount_rate) / 100)

    model_config = {"from_attributes": True}

# ----------------- 장바구니 -----------------
class CartItemBase(BaseModel):
    product_id: int
    quantity: int

class CartItemCreate(CartItemBase):
    pass

class CartItemResponse(CartItemBase):
    id: int
    model_config = {"from_attributes": True}

# ----------------- 주문 -----------------
class OrderItemBase(BaseModel):
    product_id: int
    quantity: int
    price: int

class OrderItemCreate(OrderItemBase):
    pass

class OrderItemResponse(OrderItemBase):
    id: int
    model_config = {"from_attributes": True}

class OrderBase(BaseModel):
    user_id: int
    total_price: int
    status: str = "결제완료"

class OrderCreate(OrderBase):
    items: list[OrderItemCreate]

class OrderResponse(OrderBase):
    id: int
    order_date: datetime
    items: list[OrderItemResponse] = []
    model_config = {"from_attributes": True}
