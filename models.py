from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(String, default="user")  # user, admin
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    name = Column(String, nullable=False)
    brand = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    discount_rate = Column(Integer, default=0)  # 추가
    discounted_price = Column(Integer, nullable=False, default=0)  # 추가
    stock = Column(Integer, default=0)
    image_url = Column(String)
    sku = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CartItem(Base):
    __tablename__ = "cart_items"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    total_price = Column(Integer, nullable=False)
    status = Column(String, default="결제완료")
    order_date = Column(DateTime(timezone=True), server_default=func.now())

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
