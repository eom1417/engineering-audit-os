"""ORM models in three frameworks."""
from sqlalchemy import Column, Integer, String

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True)
    amount = Column(Integer)

class DjangoOrder(models.Model):
    name = models.CharField(max_length=100)

class RailsOrder < ApplicationRecord:
end
