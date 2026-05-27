from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from starlette.applications import Starlette

from sqladmin import Admin, ModelView
from tests.common import async_engine as engine

pytestmark = pytest.mark.anyio

Base = declarative_base()
session_maker = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)

app = Starlette()
admin = Admin(app=app, engine=engine)


class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    name = Column(String(length=32))

    def __str__(self) -> str:
        return f"Tag {self.id}"


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    tag_id = Column(Integer, ForeignKey("tags.id"))
    tag = relationship("Tag")

    def __str__(self) -> str:
        return f"Post {self.id}"


class Label(Base):
    __tablename__ = "labels"
    id = Column(Integer, primary_key=True)
    name = Column(String(length=32))

    def __str__(self) -> str:
        return f"Label {self.id}"


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True)
    label_id = Column(Integer, ForeignKey("labels.id"))
    label = relationship("Label")

    def __str__(self) -> str:
        return f"Article {self.id}"


class PostAdmin(ModelView, model=Post):
    ajax_threshold = 2


class ArticleAdmin(ModelView, model=Article):
    ajax_threshold = 0


admin.add_view(PostAdmin)
admin.add_view(ArticleAdmin)


@pytest.fixture(autouse=True)
async def prepare_database() -> AsyncGenerator[None, None]:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


async def test_auto_ajax_activated_when_above_threshold(client: AsyncClient) -> None:
    async with session_maker() as s:
        for i in range(3):
            s.add(Tag(name=f"tag{i}"))
        await s.commit()

    response = await client.get("/admin/post/create")
    assert response.status_code == 200
    assert 'data-role="select2-ajax"' in response.text
    assert 'data-url="http://testserver/admin/post/ajax/lookup"' in response.text


async def test_auto_ajax_not_activated__below_threshold(client: AsyncClient) -> None:
    async with session_maker() as s:
        s.add(Tag(name="only-one"))
        await s.commit()

    response = await client.get("/admin/post/create")
    assert response.status_code == 200
    assert 'data-url="http://testserver/admin/post/ajax/lookup"' not in response.text


async def test_auto_ajax_disabled_when_threshold_is_zero(client: AsyncClient) -> None:
    async with session_maker() as s:
        for i in range(100):
            s.add(Label(name=f"label{i}"))
        await s.commit()

    response = await client.get("/admin/article/create")
    assert response.status_code == 200
    assert 'data-url="http://testserver/admin/article/ajax/lookup"' not in response.text


async def test_form_submission_works__many_related_records(client: AsyncClient) -> None:
    async with session_maker() as s:
        for i in range(3):
            s.add(Tag(name=f"tag-{i}"))
        await s.commit()

    async with session_maker() as s:
        post = Post(tag_id=1)
        s.add(post)
        await s.commit()

    response = await client.get("/admin/post/edit/1")
    assert response.status_code == 200
    assert 'data-role="select2-ajax"' in response.text

    assert response.text.count("<option") < 10
