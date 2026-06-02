from sqlalchemy import Column, Integer, String, ForeignKey, Table, create_engine
from sqlalchemy.orm import declarative_base, relationship, Mapped, mapped_column
from fastapi import FastAPI
from sqladmin import Admin, ModelView

Base = declarative_base()
engine = create_engine("sqlite:///demo.db", connect_args={"check_same_thread": False})

user_role = Table(
    'user_role',
    Base.metadata,
    Column('user_id', ForeignKey('user.id'), primary_key=True),
    Column('role_id', ForeignKey('role.id'), primary_key=True),
)

class Role(Base):
    __tablename__ = "role"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    users = relationship("User", secondary='user_role', back_populates='roles')
    def __str__(self):
        return self.name

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    email = Column(String)
    roles = relationship("Role", secondary='user_role', back_populates='users')

Base.metadata.create_all(engine)

# popula com 3000 roles
from sqlalchemy.orm import Session
with Session(engine) as s:
    if s.query(Role).count() == 0:
        for i in range(3000):
            s.add(Role(name=f"role-{i}"))
        s.commit()
    if s.query(User).count() == 0:
        user = User(email="test@test.com")
        user.roles = s.query(Role).all()
        s.add(user)
        s.commit()

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email]
    form_ajax_refs = {
        "roles": {
            "fields": ("name",),
            "order_by": "id",
            "page_size": 20,
        }
    }

app = FastAPI()
admin = Admin(app, engine)
admin.add_view(UserAdmin)
