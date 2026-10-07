from csv import Error
import os
from contextlib import asynccontextmanager
from typing import Generator
import boto3
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import URL, String, create_engine, make_url, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "fastapi-app-storage-lanhoang-2026")
AWS_REGION = os.getenv("AWS_REGION", "ap-southeast-1")

# Boto3 tự động nhận quyền từ EC2 IAM Role (không cần truyền access_key/secret_key)
s3_client = boto3.client("s3", region_name=AWS_REGION)


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=False)


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class ItemRead(ItemCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int


def create_app(database_url: str | None = None) -> FastAPI:
    if database_url is None:
        database_url = URL.create(
            drivername="mysql+pymysql",
            username=os.getenv("MYSQL_USER", "app_user"),
            password=os.getenv("MYSQL_PASSWORD", "local_password"),
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            database=os.getenv("MYSQL_DATABASE", "app_db"),
        )

    engine_options = {}
    parsed_url = (
        make_url(database_url) if isinstance(database_url, str) else database_url
    )
    if parsed_url.drivername.startswith("sqlite"):
        engine_options["connect_args"] = {"check_same_thread": False}
        if parsed_url.database in (None, "", ":memory:"):
            engine_options["poolclass"] = StaticPool

    engine = create_engine(parsed_url, pool_pre_ping=True, **engine_options)
    session_factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield
        engine.dispose()

    app = FastAPI(title="FastAPI + MySQL", version="1.0.0", lifespan=lifespan)

    def get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    @app.get("/")
    def read_root():
        return {"status": "ok"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/items", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
    def create_item(item: ItemCreate, db: Session = Depends(get_db)) -> Item:
        db_item = Item(name=item.name, description=item.description)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item

    @app.get("/items", response_model=list[ItemRead])
    def list_items(db: Session = Depends(get_db)) -> list[Item]:
        return list(db.scalars(select(Item).order_by(Item.id)))

    @app.get("/items/{item_id}", response_model=ItemRead)
    def get_item(item_id: int, db: Session = Depends(get_db)) -> Item:
        item = db.get(Item, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
            )
        return item

    @app.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_item(item_id: int, db: Session = Depends(get_db)) -> None:
        item = db.get(Item, item_id)
        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Item not found"
            )
        db.delete(item)
        db.commit()

    @app.post("/upload")
    async def upload_file_to_s3(file: UploadFile = File(...)):
        try:
            # Đường dẫn/tên file lưu trên S3
            s3_key = f"uploads/{file.filename}"

            # Upload luồng file trực tiếp lên S3
            s3_client.upload_fileobj(
                file.file,
                S3_BUCKET_NAME,
                s3_key,
                ExtraArgs={"ContentType": file.content_type},
            )

            return {
                "status": "success",
                "message": "File uploaded successfully!",
                "bucket": S3_BUCKET_NAME,
                "file_key": s3_key,
                "file_url": f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}",
            }
        except Error as e:
            raise HTTPException(status_code=500, detail=f"S3 upload error: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return app


app = create_app()
